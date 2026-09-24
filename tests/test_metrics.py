import json

import pytest

from umlpy import metrics
from umlpy.edn import kw


def test_function_spans_name_methods_like_the_scanner():
    spans = metrics.function_spans("class A:\n    def m(self, x):\n        if x:\n            return 1\n\ndef f():\n    pass\n")
    assert {(s.name, s.complexity) for s in spans} == {("A.m", 2), ("f", 1)}


@pytest.mark.parametrize(("cc", "cov", "expected"), [(27, 63.99560922063666, 61.02467053220152), (5, 100.0, 5.0), (3, 0.0, 12.0)])
def test_crap_matches_crap4clj(cc, cov, expected):
    assert metrics.crap_score(cc, cov) == pytest.approx(expected)


def test_entries_with_coverage(project):
    report = project / "coverage.json"
    engine = "app/core/rules/engine.py"
    run_lines = [21, 22, 23]
    report.write_text(json.dumps({"files": {engine: {"executed_lines": run_lines[:2], "missing_lines": [24]}}}))
    rows = metrics.entries(project, "app.core", metrics.load_coverage(report, project))
    by_name = {(r[kw("namespace")], r[kw("name")]): r for r in rows}
    run = by_name[("app.core.rules.engine", "run")]
    assert run[kw("complexity")] == 2
    assert run[kw("coverage")] == pytest.approx(200 / 3)
    assert by_name[("app.core.helpers", "helper")][kw("coverage")] == 0.0


def test_entries_without_coverage_have_no_crap(project):
    rows = metrics.entries(project, "app.core", None)
    assert rows and all(kw("crap") not in r and kw("coverage") not in r for r in rows)


def test_write(project):
    out = metrics.write(project, [{kw("name"): "f", kw("namespace"): "m", kw("complexity"): 1}])
    assert out.read_text().startswith("{:entries [")
