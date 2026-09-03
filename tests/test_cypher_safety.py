import pytest

from chatbot.cypher_safety import UnsafeQueryError, ensure_limit, enforce_read_only


def test_ensure_limit_leaves_literal_limit_untouched():
    q = "MATCH (n) RETURN n LIMIT 10"
    assert ensure_limit(q) == q


def test_ensure_limit_leaves_parametrized_limit_untouched():
    q = "MATCH (n) RETURN n ORDER BY n.x DESC LIMIT $top_n"
    assert ensure_limit(q) == q


def test_ensure_limit_appends_when_missing():
    q = "MATCH (n) RETURN n"
    result = ensure_limit(q, default_limit=25)
    assert result.strip().endswith("LIMIT 25")


def test_enforce_read_only_blocks_write_keywords():
    for bad in ["MATCH (n) DETACH DELETE n", "CREATE (n:Foo)", "MATCH (n) SET n.x = 1", "CALL apoc.periodic.iterate('','',{})"]:
        with pytest.raises(UnsafeQueryError):
            enforce_read_only(bad)


def test_enforce_read_only_allows_plain_match_return():
    q = "MATCH (n:Drug) RETURN n.name LIMIT 10"
    assert enforce_read_only(q) == q
