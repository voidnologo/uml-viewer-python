"""Python LanguageGraph: modules as classes, imports as edges, Protocol/ABC as interfaces."""

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from umlpy.edn import Keyword, kw

INTERFACE_BASES = frozenset({"Protocol", "ABC", "typing.Protocol", "abc.ABC", "typing_extensions.Protocol"})


@dataclass
class ParsedModule:
    name: str
    path: Path
    is_package: bool
    tree: ast.Module
    # local name -> (module, attribute or None)
    bindings: dict[str, tuple[str, str | None]] = field(default_factory=dict)
    imported: list[str] = field(default_factory=list)
    interfaces: set[str] = field(default_factory=set)


def module_name(src_root: Path, path: Path) -> tuple[str, bool]:
    parts = list(path.relative_to(src_root).with_suffix("").parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]
    return ".".join(parts), is_package


def discover(src_root: Path, prefix: str) -> dict[str, tuple[Path, bool]]:
    """Map every module under `prefix` (excluding the prefix package itself) to its file."""
    base = src_root.joinpath(*prefix.split("."))
    found: dict[str, tuple[Path, bool]] = {}
    for path in sorted(base.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        name, is_package = module_name(src_root, path)
        if name != prefix:
            found[name] = (path, is_package)
    return found


def _package_of(mod: ParsedModule) -> str:
    return mod.name if mod.is_package else mod.name.rpartition(".")[0]


def resolve_relative(mod: ParsedModule, level: int, target: str | None) -> str:
    base = _package_of(mod)
    for _ in range(level - 1):
        base = base.rpartition(".")[0]
    if target:
        return f"{base}.{target}" if base else target
    return base


def _nearest_known(dotted: str, known: set[str]) -> str | None:
    candidate = dotted
    while candidate:
        if candidate in known:
            return candidate
        candidate = candidate.rpartition(".")[0]
    return None


def _record_import(mod: ParsedModule, node: ast.Import) -> None:
    for alias in node.names:
        mod.imported.append(alias.name)
        local = alias.asname or alias.name.split(".")[0]
        bound = alias.name if alias.asname else alias.name.split(".")[0]
        mod.bindings[local] = (bound, None)


def _record_import_from(mod: ParsedModule, node: ast.ImportFrom, known: set[str]) -> None:
    base = resolve_relative(mod, node.level, node.module) if node.level else (node.module or "")
    for alias in node.names:
        submodule = f"{base}.{alias.name}"
        target = submodule if submodule in known else base
        mod.imported.append(target)
        attr = None if target == submodule else alias.name
        mod.bindings[alias.asname or alias.name] = (target, attr)


def _base_names(node: ast.ClassDef) -> list[str]:
    return [ast.unparse(b) for b in node.bases]


def _is_interface(node: ast.ClassDef) -> bool:
    if any(name in INTERFACE_BASES or name.startswith("Protocol[") for name in _base_names(node)):
        return True
    return any(k.arg == "metaclass" and ast.unparse(k.value).endswith("ABCMeta") for k in node.keywords)


def parse(name: str, path: Path, is_package: bool, known: set[str]) -> ParsedModule:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    mod = ParsedModule(name=name, path=path, is_package=is_package, tree=tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            _record_import(mod, node)
        elif isinstance(node, ast.ImportFrom):
            _record_import_from(mod, node, known)
    mod.interfaces = {n.name for n in tree.body if isinstance(n, ast.ClassDef) and _is_interface(n)}
    return mod


def is_private(name: str) -> bool:
    last = name.rpartition(".")[2]
    dunder = last.startswith("__") and last.endswith("__")
    return (name.startswith("_") or last.startswith("_")) and not dunder


def _op(name: str) -> dict[Keyword, Any]:
    # Hierarchical IR is drawn without member normalization, so each member carries its own label.
    op: dict[Keyword, Any] = {kw("name"): name, kw("text"): name}
    if is_private(name):
        op[kw("private")] = True
    return op


def members(tree: ast.Module) -> tuple[list[dict], list[dict]]:
    """Module-level functions and Class.method as ops; module-level classes as fields."""
    ops: list[dict] = []
    fields: list[dict] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ops.append(_op(node.name))
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(_base_names(node)) or "class"
            fields.append({kw("name"): node.name, kw("type"): bases, kw("text"): f"{node.name} : {bases}"})
            ops.extend(_op(f"{node.name}.{m.name}") for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)))
    return ops, fields


def class_id(name: str, prefix: str) -> Keyword:
    return kw(name.removeprefix(prefix + "."))


def _project_class(mod: ParsedModule, prefix: str) -> dict:
    ops, fields = members(mod.tree)
    entry: dict[Keyword, Any] = {
        kw("id"): class_id(mod.name, prefix),
        kw("name"): mod.name.rpartition(".")[2],
        kw("ns"): mod.name,
    }
    if mod.interfaces:
        entry[kw("stereotype")] = kw("interface")
    if ops:
        entry[kw("ops")] = ops
    if fields:
        entry[kw("fields")] = fields
    return entry


def _dependency_targets(mod: ParsedModule, known: set[str], prefix: str) -> tuple[set[str], set[str]]:
    project: set[str] = set()
    foreign: set[str] = set()
    for dotted in mod.imported:
        if not dotted:
            continue
        hit = _nearest_known(dotted, known)
        if hit:
            project.add(hit)
        elif dotted != prefix and not dotted.startswith(prefix + "."):
            foreign.add(dotted)
    project.discard(mod.name)
    return project, foreign


def _resolve_base(mod: ParsedModule, base: str) -> tuple[str, str] | None:
    head, _, rest = base.partition(".")
    if head not in mod.bindings:
        return None
    target, attr = mod.bindings[head]
    if attr is not None:
        return (target, attr) if not rest else None
    module, _, cls = f"{target}.{rest}".rpartition(".") if rest else ("", "", "")
    return (module, cls) if module else None


def implements_targets(mod: ParsedModule, modules: dict[str, ParsedModule]) -> set[str]:
    targets: set[str] = set()
    for node in mod.tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for base in _base_names(node):
            resolved = _resolve_base(mod, base)
            if resolved and resolved[0] in modules and resolved[1] in modules[resolved[0]].interfaces:
                targets.add(resolved[0])
    targets.discard(mod.name)
    return targets


def _edge(src: str, dst: Keyword, kind: str, prefix: str) -> dict:
    return {kw("from"): class_id(src, prefix), kw("to"): dst, kw("kind"): kw(kind)}


def _edges_for(mod: ParsedModule, modules: dict[str, ParsedModule], prefix: str) -> tuple[list[dict], set[str]]:
    known = set(modules)
    project, foreign = _dependency_targets(mod, known, prefix)
    edges = [_edge(mod.name, class_id(t, prefix), "dependency", prefix) for t in sorted(project)]
    edges += [_edge(mod.name, kw(t), "dependency", prefix) for t in sorted(foreign)]
    edges += [_edge(mod.name, class_id(t, prefix), "implements", prefix) for t in sorted(implements_targets(mod, modules))]
    return edges, foreign


def _foreign_class(dotted: str) -> dict:
    return {kw("id"): kw(dotted), kw("name"): dotted, kw("ns"): dotted, kw("foreign"): True}


def scan(src_root: Path, prefix: str) -> dict:
    """Return `{:classes :edges}` for every module under `prefix`, in LanguageGraph shape."""
    found = discover(src_root, prefix)
    known = set(found)
    modules = {name: parse(name, path, pkg, known) for name, (path, pkg) in found.items()}
    classes = [_project_class(m, prefix) for m in modules.values()]
    edges: list[dict] = []
    foreigns: set[str] = set()
    for mod in modules.values():
        mod_edges, mod_foreign = _edges_for(mod, modules, prefix)
        edges += mod_edges
        foreigns |= mod_foreign
    classes += [_foreign_class(f) for f in sorted(foreigns)]
    return {kw("classes"): classes, kw("edges"): edges}


def top_segments(src_root: Path, prefix: str) -> list[str]:
    """First dotted segment after `prefix` for every module, in source order."""
    seen: dict[str, None] = {}
    for name in discover(src_root, prefix):
        seen.setdefault(name.removeprefix(prefix + ".").split(".")[0], None)
    return list(seen)
