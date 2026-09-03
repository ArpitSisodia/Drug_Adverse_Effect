import re

_WRITE_DENYLIST = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV|CALL\s+apoc\.|CALL\s+db\.index\.fulltext\.create)\b",
    re.IGNORECASE,
)
_LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+|\$\w+)\b", re.IGNORECASE)
DEFAULT_LIMIT = 50


class UnsafeQueryError(Exception):
    pass


def enforce_read_only(cypher: str) -> str:
    """Reject write/schema-mutating keywords; used on any Cypher not sourced
    from our own fixed templates (i.e. the fallback text-to-Cypher path)."""
    if _WRITE_DENYLIST.search(cypher):
        raise UnsafeQueryError("Generated query contains a disallowed write/admin keyword.")
    return cypher


def ensure_limit(cypher: str, default_limit: int = DEFAULT_LIMIT) -> str:
    """Append a LIMIT clause if the query doesn't already have one, so a
    malformed/overly-broad query can't return an unbounded result set."""
    if _LIMIT_RE.search(cypher):
        return cypher
    return f"{cypher.rstrip().rstrip(';')} LIMIT {default_limit}"


def run_safely(session, cypher: str, params: dict, timeout_seconds: float = 10.0) -> list[dict]:
    result = session.run(cypher, params, timeout=timeout_seconds)
    return result.data()
