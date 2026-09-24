"""Hierarchical policy file: created once, `:order` kept in step with the module tree."""

from pathlib import Path

from umlpy import edn
from umlpy.edn import Keyword, Symbol, Vector, kw

DEFAULT_POLICY = Path(".uml-viewer/policy.edn")
DEFAULT_OUT = ".uml-viewer/diagram.edn"


def new_policy(title: str, src: str, prefix: str, segments: list[str]) -> dict:
    return {
        kw("title"): title,
        kw("src"): src,
        kw("prefix"): prefix,
        kw("lang"): kw("python"),
        kw("out"): DEFAULT_OUT,
        kw("hierarchical"): True,
        kw("order"): Vector(Symbol(s) for s in segments),
        kw("foreign"): Vector(),
        kw("levels"): Vector(),
    }


def _segment_name(item: object) -> str:
    return item.name if isinstance(item, (Keyword, Symbol)) else str(item)


def sync_order(policy: dict, segments: list[str]) -> dict:
    """Keep the user's ordering of segments that still exist; append new ones at the end."""
    current = [_segment_name(i) for i in policy.get(kw("order"), ())]
    live = set(segments)
    kept = [s for s in current if s in live]
    added = [s for s in segments if s not in kept]
    return {**policy, kw("order"): Vector(Symbol(s) for s in kept + added)}


def read(path: Path) -> dict:
    return edn.loads(path.read_text())


def write(path: Path, policy: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(edn.pretty(policy) + "\n")


def src_root(policy: dict, project_root: Path) -> Path:
    return project_root / policy.get(kw("src"), ".")


def prefix(policy: dict) -> str:
    return policy[kw("prefix")]


def out_path(policy: dict) -> str:
    return policy.get(kw("out"), DEFAULT_OUT)
