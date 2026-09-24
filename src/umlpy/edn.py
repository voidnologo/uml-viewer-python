"""Minimal EDN reader/writer for the files uml-viewer and its companion exchange.

Covers nil, booleans, numbers, strings, keywords, symbols, vectors, lists, maps, sets,
comments and `#_` discard. Vectors and lists are distinct tuple subclasses so policy
files written by the Clojure viewer round-trip without turning `[...]` into `(...)`.
"""

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, order=True)
class Keyword:
    name: str

    def __repr__(self) -> str:
        return f":{self.name}"


@dataclass(frozen=True, order=True)
class Symbol:
    name: str

    def __repr__(self) -> str:
        return self.name


class Vector(tuple):
    """EDN `[...]`."""


class EList(tuple):
    """EDN `(...)`."""


def kw(name: str) -> Keyword:
    return Keyword(name)


class EdnError(ValueError):
    pass


_DELIMS = set("()[]{}\"; \t\r\n,")
_NUMBER = re.compile(r"^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?M?N?$")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "b": "\b", "f": "\f"}
_CLOSERS = {"(": ")", "[": "]", "{": "}"}


class _Reader:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def skip_ws(self) -> None:
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch in " \t\r\n,":
                self.pos += 1
            elif ch == ";":
                end = self.text.find("\n", self.pos)
                self.pos = len(self.text) if end < 0 else end + 1
            else:
                return

    def read(self) -> Any:
        self.skip_ws()
        if self.pos >= len(self.text):
            raise EdnError("unexpected end of input")
        ch = self.text[self.pos]
        if ch in _CLOSERS:
            return self.read_coll(ch)
        if ch == '"':
            return self.read_string()
        if ch == "#":
            return self.read_dispatch()
        if ch in ")]}":
            raise EdnError(f"unexpected {ch!r} at {self.pos}")
        return self.read_atom()

    def read_seq(self, closer: str) -> list[Any]:
        items: list[Any] = []
        while True:
            self.skip_ws()
            if self.pos >= len(self.text):
                raise EdnError(f"missing {closer!r}")
            if self.text[self.pos] == closer:
                self.pos += 1
                return items
            item = self.read_maybe_discard()
            if item is not _DISCARDED:
                items.append(item)

    def read_maybe_discard(self) -> Any:
        if self.text.startswith("#_", self.pos):
            self.pos += 2
            self.read()
            return _DISCARDED
        return self.read()

    def read_coll(self, opener: str) -> Any:
        self.pos += 1
        items = self.read_seq(_CLOSERS[opener])
        if opener == "[":
            return Vector(items)
        if opener == "(":
            return EList(items)
        if len(items) % 2:
            raise EdnError("map literal has an odd number of forms")
        return dict(zip(items[::2], items[1::2]))

    def read_dispatch(self) -> Any:
        nxt = self.text[self.pos + 1 : self.pos + 2]
        if nxt == "{":
            self.pos += 1
            self.pos += 1
            return frozenset(self.read_seq("}"))
        if nxt == "_":
            self.pos += 2
            self.read()
            return self.read()
        raise EdnError(f"unsupported dispatch #{nxt} at {self.pos}")

    def read_string(self) -> str:
        self.pos += 1
        out: list[str] = []
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch == '"':
                self.pos += 1
                return "".join(out)
            if ch == "\\":
                out.append(self.read_escape())
                continue
            out.append(ch)
            self.pos += 1
        raise EdnError("unterminated string")

    def read_escape(self) -> str:
        code = self.text[self.pos + 1 : self.pos + 2]
        if code == "u":
            hex_digits = self.text[self.pos + 2 : self.pos + 6]
            self.pos += 6
            return chr(int(hex_digits, 16))
        if code not in _ESCAPES:
            raise EdnError(f"bad escape \\{code}")
        self.pos += 2
        return _ESCAPES[code]

    def read_atom(self) -> Any:
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in _DELIMS:
            self.pos += 1
        token = self.text[start : self.pos]
        return _atom(token)


_DISCARDED = object()


def _atom(token: str) -> Any:
    if token == "nil":
        return None
    if token in ("true", "false"):
        return token == "true"
    if token.startswith(":"):
        return Keyword(token[1:])
    if _NUMBER.match(token):
        return _number(token.rstrip("MN"))
    if token.startswith("\\"):
        raise EdnError(f"character literals are not supported: {token}")
    return Symbol(token)


def _number(token: str) -> int | float:
    if any(c in token for c in ".eE"):
        return float(token)
    return int(token)


def loads(text: str) -> Any:
    """Parse the first EDN form in `text`."""
    return _Reader(text).read()


def loads_all(text: str) -> list[Any]:
    reader = _Reader(text)
    forms: list[Any] = []
    reader.skip_ws()
    while reader.pos < len(reader.text):
        forms.append(reader.read())
        reader.skip_ws()
    return forms


def _string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    return f'"{escaped}"'


def dumps(value: Any) -> str:
    """Serialize `value`; Python lists become vectors, plain tuples become lists."""
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, (Keyword, Symbol)):
        return repr(value)
    return _dump_coll(value)


def _dump_coll(value: Any) -> str:
    if isinstance(value, dict):
        return "{" + ", ".join(f"{dumps(k)} {dumps(v)}" for k, v in value.items()) + "}"
    if isinstance(value, (frozenset, set)):
        return "#{" + " ".join(dumps(v) for v in value) + "}"
    if isinstance(value, EList):
        return "(" + " ".join(dumps(v) for v in value) + ")"
    if isinstance(value, (Vector, list, tuple)):
        return "[" + " ".join(dumps(v) for v in value) + "]"
    raise EdnError(f"cannot serialize {type(value).__name__}")


def pretty(value: Any, indent: int = 0) -> str:
    """Multi-line form for maps of collections, so generated files diff well."""
    if not isinstance(value, dict) or not value:
        return dumps(value)
    pad = " " * (indent + 1)
    lines = [f"{dumps(k)} {pretty(v, indent + 2 + len(dumps(k)))}" for k, v in value.items()]
    return "{" + ("\n" + pad).join(lines) + "}"
