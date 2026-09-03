from neo4j import Session

from ingestion.normalize import normalize_key

# Re-exported so both ingestion and the chatbot use exactly one normalization rule.
drug_key = normalize_key
reaction_key = normalize_key
indication_key = normalize_key


def resolve_drug_name(session: Session, user_text: str, limit: int = 5) -> list[dict]:
    """Fuzzy-resolve free-text drug name to graph Drug nodes via the fulltext index.

    Returns [{"drug_key", "name", "score"}, ...] best match first. Exact
    normalized-key match (if any) is always ranked first regardless of
    fulltext score, since it's a strictly better match than any fuzzy hit.
    """
    exact_key = normalize_key(user_text)
    results = session.run(
        """
        CALL db.index.fulltext.queryNodes('drugNameFulltext', $q) YIELD node, score
        RETURN node.drug_key AS drug_key, node.name AS name, score
        ORDER BY score DESC LIMIT $limit
        """,
        q=user_text,
        limit=limit,
    ).data()
    results.sort(key=lambda r: r["drug_key"] != exact_key)
    return results


def resolve_reaction_name(session: Session, user_text: str, limit: int = 5) -> list[dict]:
    exact_key = normalize_key(user_text)
    results = session.run(
        """
        CALL db.index.fulltext.queryNodes('reactionPtFulltext', $q) YIELD node, score
        RETURN node.pt_key AS pt_key, node.pt AS pt, score
        ORDER BY score DESC LIMIT $limit
        """,
        q=user_text,
        limit=limit,
    ).data()
    results.sort(key=lambda r: r["pt_key"] != exact_key)
    return results
