from umlpy import scan
from umlpy.edn import kw


def _by_id(facts):
    return {c[kw("id")].name: c for c in facts[kw("classes")]}


def _edges(facts):
    return {(e[kw("from")].name, e[kw("to")].name, e[kw("kind")].name) for e in facts[kw("edges")]}


def test_modules_become_classes_keyed_below_prefix(project):
    classes = _by_id(scan.scan(project, "app.core"))
    assert {"ports", "rules", "rules.engine", "rules.compiler", "helpers"} <= set(classes)
    assert classes["rules.engine"][kw("name")] == "engine"
    assert classes["rules.engine"][kw("ns")] == "app.core.rules.engine"


def test_prefix_package_itself_is_not_a_class(project):
    assert "app.core" not in {c[kw("ns")] for c in scan.scan(project, "app.core")[kw("classes")]}


def test_imports_resolve_to_modules(project):
    edges = _edges(scan.scan(project, "app.core"))
    assert ("rules.engine", "ports", "dependency") in edges
    assert ("rules.engine", "helpers", "dependency") in edges
    assert ("rules.engine", "rules.compiler", "dependency") in edges


def test_externals_are_foreign(project):
    facts = scan.scan(project, "app.core")
    foreign = {c[kw("id")].name for c in facts[kw("classes")] if c.get(kw("foreign"))}
    assert {"sqlalchemy.orm", "app.other", "typing"} <= foreign
    assert ("rules.engine", "sqlalchemy.orm", "dependency") in _edges(facts)


def test_protocol_module_is_interface_and_subclass_implements(project):
    facts = scan.scan(project, "app.core")
    assert _by_id(facts)["ports"][kw("stereotype")] == kw("interface")
    assert ("rules.engine", "ports", "implements") in _edges(facts)


def test_members_and_privacy(project):
    engine = _by_id(scan.scan(project, "app.core"))["rules.engine"]
    ops = {o[kw("name")]: o.get(kw("private"), False) for o in engine[kw("ops")]}
    assert ops == {"MemoryStore.get": False, "MemoryStore._cache": True, "run": False, "_private": True}
    assert engine[kw("fields")] == [{kw("name"): "MemoryStore", kw("type"): "Store", kw("text"): "MemoryStore : Store"}]


def test_every_member_has_display_text(project):
    for cls in scan.scan(project, "app.core")[kw("classes")]:
        for member in [*cls.get(kw("ops"), []), *cls.get(kw("fields"), [])]:
            assert member[kw("text")]


def test_dunder_methods_are_public():
    assert not scan.is_private("Model.__init__")
    assert scan.is_private("_Hidden.method")


def test_no_self_edges(project):
    assert all(src != dst for src, dst, _ in _edges(scan.scan(project, "app.core")))


def test_top_segments(project):
    assert set(scan.top_segments(project, "app.core")) == {"helpers", "ports", "rules"}
