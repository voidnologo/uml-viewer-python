"""`umlpy`: point unclebob/uml-viewer at a Python project."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from umlpy import companion, edn, launch, mailbox, metrics, policy, scan
from umlpy.edn import kw

FACTS_FILE = Path(".uml-viewer/python-graph.edn")
IGNORED = (".uml-viewer/", ".metrics/", launch.LOG_FILE)


def _load_policy(args: argparse.Namespace) -> dict:
    if not args.policy.is_file():
        raise SystemExit(f"umlpy: no policy at {args.policy}; run `umlpy init --prefix <package>` first")
    return policy.read(args.policy)


def _exclude_from_git(root: Path) -> None:
    """Hide generated files via .git/info/exclude so the project's .gitignore is untouched."""
    done = subprocess.run(["git", "rev-parse", "--git-path", "info/exclude"], cwd=root, capture_output=True, text=True)
    if done.returncode != 0:
        return
    exclude = (root / done.stdout.strip()).resolve()
    existing = exclude.read_text().splitlines() if exclude.is_file() else []
    missing = [p for p in IGNORED if p not in existing]
    if missing:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a") as fh:
            fh.write("".join(f"{p}\n" for p in missing))
        print(f"Added {', '.join(missing)} to {exclude}")


def cmd_init(args: argparse.Namespace) -> None:
    if args.policy.exists() and not args.force:
        raise SystemExit(f"umlpy: {args.policy} exists; pass --force to overwrite")
    root = Path.cwd()
    segments = scan.top_segments(root / args.src, args.prefix)
    if not segments:
        raise SystemExit(f"umlpy: no modules under {args.prefix} in {args.src}")
    title = args.title or args.prefix
    policy.write(args.policy, policy.new_policy(title, args.src, args.prefix, segments))
    _exclude_from_git(root)
    print(f"Wrote {args.policy} ({len(segments)} top-level segments)")


def _scan_facts(pol: dict) -> dict:
    return scan.scan(policy.src_root(pol, Path.cwd()), policy.prefix(pol))


def cmd_scan(args: argparse.Namespace) -> None:
    print(edn.dumps(_scan_facts(_load_policy(args))))


def cmd_ir(args: argparse.Namespace) -> None:
    pol = _load_policy(args)
    synced = policy.sync_order(pol, scan.top_segments(policy.src_root(pol, Path.cwd()), policy.prefix(pol)))
    if synced != pol:
        policy.write(args.policy, synced)
    FACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    FACTS_FILE.write_text(edn.dumps(_scan_facts(synced)))
    written = launch.run_ir(args.policy, FACTS_FILE)
    print(f"Wrote {written}")
    if args.display:
        _display(written)


def _display(path: str) -> None:
    extra = {kw("path"): path}
    if not os.environ.get(companion.COMPANION_ENV):
        cmd = mailbox.send(mailbox.TO_VIEWER, "display", extra)
        print(f"Queued :display #{cmd[kw('id')]}")
        return
    cmd, delivered = mailbox.deliver(mailbox.TO_VIEWER, "display", extra)
    state = "shown" if delivered else "still queued; is the viewer running?"
    print(f":display #{cmd[kw('id')]} {state}")


def _run_tests(pol: dict) -> Path:
    config = pol.get(kw("coverage")) or {}
    if kw("command") not in config or kw("json") not in config:
        raise SystemExit("umlpy: --run-tests needs policy :coverage {:command \"…\" :json \"…\"}")
    done = subprocess.run(config[kw("command")], shell=True, cwd=Path.cwd())
    if done.returncode != 0:
        print(f"umlpy: test command exited {done.returncode}; using whatever coverage it wrote", file=sys.stderr)
    return Path(config[kw("json")])


def cmd_metrics(args: argparse.Namespace) -> None:
    pol = _load_policy(args)
    report = _run_tests(pol) if args.run_tests else args.coverage_json
    root = Path.cwd()
    coverage = metrics.load_coverage(report, root) if report else None
    rows = metrics.entries(policy.src_root(pol, root), policy.prefix(pol), coverage)
    out = metrics.write(root, rows)
    mode = "complexity + coverage" if coverage is not None else "complexity only"
    print(f"Wrote {out} ({len(rows)} functions, {mode})")


def cmd_mail(args: argparse.Namespace) -> None:
    if args.action == "pop":
        print(edn.dumps(mailbox.pop(mailbox.TO_AGENT)))
        return
    if not args.op:
        raise SystemExit("umlpy: mail send needs an OP")
    extra = {}
    for pair in args.pairs:
        key, _, value = pair.partition("=")
        extra[kw(key)] = mailbox.parse_value(value)
    print(edn.dumps(mailbox.send(mailbox.TO_VIEWER, args.op, extra)))


def cmd_view(args: argparse.Namespace) -> None:
    pol = _load_policy(args)
    pid = launch.start_viewer(Path.cwd(), policy.out_path(pol), pol.get(kw("src"), "."), args.restart)
    print(f"UML viewer started (pid {pid}). Log: {launch.LOG_FILE}")


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="umlpy", description=__doc__)
    top.add_argument("--policy", type=Path, default=policy.DEFAULT_POLICY)
    sub = top.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="write a hierarchical policy for a package")
    p.add_argument("--prefix", required=True, help="dotted package to diagram, e.g. myapp.billing")
    p.add_argument("--src", default=".", help="directory that contains the top-level package")
    p.add_argument("--title")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    sub.add_parser("scan", help="print the scanned graph facts as EDN").set_defaults(func=cmd_scan)

    p = sub.add_parser("ir", help="regenerate the diagram from the policy")
    p.add_argument("--display", action="store_true", help="tell the viewer to show it")
    p.set_defaults(func=cmd_ir)

    p = sub.add_parser("metrics", help="write .metrics/crap.edn")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--coverage-json", type=Path, help="coverage.py JSON report")
    group.add_argument("--run-tests", action="store_true", help="run policy :coverage :command first")
    p.set_defaults(func=cmd_metrics)

    p = sub.add_parser("mail", help="viewer mailbox")
    p.add_argument("action", choices=["pop", "send"])
    p.add_argument("op", nargs="?")
    p.add_argument("pairs", nargs="*", metavar="key=value")
    p.set_defaults(func=cmd_mail)

    p = sub.add_parser("view", help="launch the viewer (fresh start also starts the Claude companion)")
    p.add_argument("--restart", action="store_true", help="companion only: new JVM, same session")
    p.set_defaults(func=cmd_view)
    return top


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    try:
        args.func(args)
    except launch.LaunchError as err:
        raise SystemExit(f"umlpy: {err}") from err
