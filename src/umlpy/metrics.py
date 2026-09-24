"""`.metrics/crap.edn` from radon complexity and a coverage.py JSON report."""

import json
from dataclasses import dataclass
from pathlib import Path

from radon.complexity import cc_visit
from radon.visitors import Class, Function

from umlpy import edn
from umlpy.edn import kw
from umlpy.scan import discover


@dataclass(frozen=True)
class FunctionSpan:
    name: str
    first_line: int
    last_line: int
    complexity: int


def function_spans(source: str) -> list[FunctionSpan]:
    """Module-level functions and `Class.method`, named the way the scanner names ops."""
    spans: list[FunctionSpan] = []
    for block in cc_visit(source):
        if isinstance(block, Function) and not block.is_method:
            spans.append(FunctionSpan(block.name, block.lineno, block.endline, block.complexity))
        elif isinstance(block, Class):
            spans += [FunctionSpan(f"{block.name}.{m.name}", m.lineno, m.endline, m.complexity) for m in block.methods]
    return spans


def crap_score(complexity: int, coverage_pct: float) -> float:
    uncovered = 1.0 - coverage_pct / 100.0
    return complexity**2 * uncovered**3 + complexity


@dataclass(frozen=True)
class FileCoverage:
    """Line hits for one file; `measured=False` is a file the test run never imported."""

    executed: frozenset[int]
    missing: frozenset[int]
    measured: bool = True

    def percent(self, span: FunctionSpan) -> float:
        if not self.measured:
            return 0.0
        lines = range(span.first_line, span.last_line + 1)
        hit = sum(1 for n in lines if n in self.executed)
        statements = hit + sum(1 for n in lines if n in self.missing)
        return 100.0 if statements == 0 else 100.0 * hit / statements


NOT_IMPORTED = FileCoverage(frozenset(), frozenset(), measured=False)


def load_coverage(report: Path, project_root: Path) -> dict[Path, FileCoverage]:
    """coverage.py `coverage json` output, keyed by absolute file path."""
    data = json.loads(report.read_text())
    by_path: dict[Path, FileCoverage] = {}
    for name, entry in data.get("files", {}).items():
        path = Path(name) if Path(name).is_absolute() else project_root / name
        by_path[path.resolve()] = FileCoverage(frozenset(entry["executed_lines"]), frozenset(entry["missing_lines"]))
    return by_path


def _entry(namespace: str, span: FunctionSpan, coverage: FileCoverage | None) -> dict:
    entry = {kw("name"): span.name, kw("namespace"): namespace, kw("complexity"): span.complexity}
    if coverage is not None:
        pct = coverage.percent(span)
        entry[kw("coverage")] = pct
        entry[kw("crap")] = crap_score(span.complexity, pct)
    return entry


def entries(src_root: Path, prefix: str, coverage: dict[Path, FileCoverage] | None) -> list[dict]:
    """One entry per function; coverage-less files get complexity only, which the viewer leaves uncolored."""
    rows: list[dict] = []
    for namespace, (path, _) in discover(src_root, prefix).items():
        file_cov = None if coverage is None else coverage.get(path.resolve(), NOT_IMPORTED)
        rows += [_entry(namespace, span, file_cov) for span in function_spans(path.read_text(encoding="utf-8"))]
    return sorted(rows, key=lambda r: r.get(kw("crap"), r[kw("complexity")]), reverse=True)


def write(project_root: Path, rows: list[dict]) -> Path:
    out = project_root / ".metrics" / "crap.edn"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(edn.dumps({kw("entries"): rows}) + "\n")
    return out
