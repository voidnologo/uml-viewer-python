import pytest

from umlpy import edn
from umlpy.edn import EList, Keyword, Symbol, Vector, kw


def test_scalars():
    assert edn.loads("nil") is None
    assert edn.loads("true") is True
    assert edn.loads("-12") == -12
    assert edn.loads("1.5e2") == 150.0
    assert edn.loads(':a.b/c') == Keyword("a.b/c")
    assert edn.loads("sym-1") == Symbol("sym-1")


def test_string_escapes():
    assert edn.loads(r'"a\"b\\c\nd\u0041"') == 'a"b\\c\ndA'


def test_collections_keep_vector_and_list_distinct():
    value = edn.loads("{:v [1 2], :l (1 2), :s #{:x}}")
    assert isinstance(value[kw("v")], Vector)
    assert isinstance(value[kw("l")], EList)
    assert value[kw("s")] == frozenset({kw("x")})


def test_vector_map_keys_round_trip():
    text = "{:edge-kinds {[:engine.compose :engine.layout] :association}}"
    assert edn.loads(edn.dumps(edn.loads(text))) == edn.loads(text)


def test_comments_commas_and_discard():
    assert edn.loads("; head\n[1, #_2 3 ; tail\n]") == Vector([1, 3])


def test_dumps_policy_shape_round_trips():
    policy = {kw("order"): Vector([Symbol("rules"), Symbol("generic")]), kw("title"): "T", kw("n"): 2.5}
    assert edn.loads(edn.dumps(policy)) == policy
    assert edn.loads(edn.pretty(policy)) == policy


def test_clojure_pprint_output_parses():
    text = '{:proposals\n [{:id :ccp,\n   :name "2026-09-18 10:30:00",\n   :layers [{:id :core, :nses [a b.c]}]}]}'
    parsed = edn.loads(text)
    assert parsed[kw("proposals")][0][kw("layers")][0][kw("nses")] == Vector([Symbol("a"), Symbol("b.c")])


@pytest.mark.parametrize("bad", ["[1 2", "{:a}", '"open', "#inst \"2020\"", "\\a"])
def test_malformed_input_raises(bad):
    with pytest.raises(edn.EdnError):
        edn.loads(bad)
