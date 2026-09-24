"""The `.uml-viewer/` queues shared with the viewer: `{:next-id n :queue [cmd …]}`."""

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from umlpy import edn
from umlpy.edn import Vector, kw

TO_VIEWER = Path(".uml-viewer/to-viewer.edn")
TO_AGENT = Path(".uml-viewer/to-agent.edn")

# Matches the viewer's retention so both writers trim the queue the same way.
KEEP_N = 32


def read(path: Path) -> dict:
    if not path.is_file():
        return {kw("next-id"): 1, kw("queue"): Vector()}
    raw = edn.loads(path.read_text())
    if isinstance(raw.get(kw("queue")), (list, tuple)):
        return {kw("next-id"): raw.get(kw("next-id"), 1), kw("queue"): Vector(raw[kw("queue")])}
    if kw("op") in raw:
        return {kw("next-id"): raw.get(kw("id"), 0) + 1, kw("queue"): Vector([raw])}
    return {kw("next-id"): 1, kw("queue"): Vector()}


def _atomic_write(path: Path, box: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(edn.dumps(box))
    os.replace(tmp, path)


def send(path: Path, op: str, extra: dict[Any, Any]) -> dict:
    """Append a command; returns it with its assigned id."""
    box = read(path)
    cmd_id = box[kw("next-id")]
    cmd = {kw("id"): cmd_id, kw("op"): kw(op), **extra}
    kept = [c for c in box[kw("queue")] if c[kw("id")] > cmd_id - KEEP_N]
    _atomic_write(path, {kw("next-id"): cmd_id + 1, kw("queue"): Vector([*kept, cmd])})
    return cmd


def pop(path: Path) -> dict | None:
    """Remove and return the oldest command, or None when the queue is empty."""
    box = read(path)
    queue = list(box[kw("queue")])
    if not queue:
        return None
    _atomic_write(path, {kw("next-id"): box[kw("next-id")], kw("queue"): Vector(queue[1:])})
    return queue[0]


def parse_value(raw: str) -> Any:
    """CLI `key=value` values are EDN when they parse (`:real`, `42`); bare words and paths stay strings."""
    try:
        value = edn.loads(raw)
    except edn.EdnError:
        return raw
    return raw if isinstance(value, edn.Symbol) else value


def queued(path: Path, cmd_id: int) -> bool:
    return any(c[kw("id")] == cmd_id for c in read(path)[kw("queue")])


def deliver(
    path: Path,
    op: str,
    extra: dict[Any, Any],
    timeout_s: float = 90.0,
    resend_after_s: float = 3.0,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[dict, bool]:
    """Send, then resend while the viewer leaves it queued; returns (last command, delivered?).

    A fresh viewer marks every id already in the queue as seen once its window is up. A command sent
    before that (the companion is fast, the macOS automation prompt is slow) is never taken, so a
    newer copy is sent until one is.
    """
    cmd = send(path, op, extra)
    waited = 0.0
    while waited < timeout_s:
        sleep(resend_after_s)
        waited += resend_after_s
        if not queued(path, cmd[kw("id")]):
            return cmd, True
        cmd = send(path, op, extra)
    return cmd, False
