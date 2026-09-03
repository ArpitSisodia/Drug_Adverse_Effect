"""Turns the DuckDB staging tables (cases / case_drugs / case_reactions) into
node / relationship record batches ready for UNWIND-based Neo4j loading.

All heavy lifting is pushed into DuckDB SQL (dedup, unnesting combo-drug
ingredients, key normalization) so this scales from the 5,000-case sample to
the full 422,459-case run without needing to hold everything in Python
memory at once -- callers iterate batches via iter_query_batches().
"""

from typing import Iterator

import duckdb

BATCH = 10_000

# --- node queries -----------------------------------------------------------

_DRUG_NODES_SQL = """
WITH candidates AS (
    SELECT trim(x) AS raw_name, 'active_substance' AS name_source
    FROM case_drugs, UNNEST(active_ingredients) AS t(x)
    WHERE trim(x) != ''
    UNION ALL
    SELECT trim(medicinalproduct) AS raw_name, 'medicinalproduct_fallback' AS name_source
    FROM case_drugs
    WHERE len(active_ingredients) = 0 AND medicinalproduct IS NOT NULL AND trim(medicinalproduct) != ''
)
SELECT
    upper(raw_name) AS drug_key,
    any_value(raw_name) AS name,
    any_value(name_source) AS name_source
FROM candidates
GROUP BY upper(raw_name)
"""

_REACTION_NODES_SQL = """
SELECT upper(trim(reactionmeddrapt)) AS pt_key, any_value(trim(reactionmeddrapt)) AS pt
FROM case_reactions
WHERE reactionmeddrapt IS NOT NULL AND trim(reactionmeddrapt) != ''
GROUP BY upper(trim(reactionmeddrapt))
"""

_COUNTRY_NODES_SQL = """
WITH codes AS (
    SELECT primarysourcecountry AS code FROM cases WHERE primarysourcecountry IS NOT NULL
    UNION
    SELECT occurcountry AS code FROM cases WHERE occurcountry IS NOT NULL
    UNION
    SELECT reportercountry AS code FROM cases WHERE reportercountry IS NOT NULL
)
SELECT DISTINCT code FROM codes
"""

_CASE_NODES_SQL = """
SELECT
    safetyreportid, safetyreportversion, primarysourcecountry, occurcountry,
    receivedate, receiptdate, reporttype, serious, seriousnessdeath,
    seriousnesslifethreatening, seriousnesshospitalization, seriousnessdisabling,
    seriousnesscongenitalanomali, seriousnessother, fulfillexpeditecriteria,
    qualification, senderorganization, companynumb, patientonsetage_years,
    patientagegroup, patientweight, patientsex, event_date_from_narrative
FROM cases
"""

_CASE_COUNTRY_REL_SQL = """
SELECT safetyreportid, primarysourcecountry AS code, 'PRIMARY_SOURCE_COUNTRY' AS rel_type
FROM cases WHERE primarysourcecountry IS NOT NULL
UNION ALL
SELECT safetyreportid, occurcountry AS code, 'OCCURRED_IN_COUNTRY' AS rel_type
FROM cases WHERE occurcountry IS NOT NULL
"""

# --- relationship queries -----------------------------------------------------

_INVOLVES_DRUG_REL_SQL = """
WITH exploded AS (
    SELECT
        case_id, drug_seq,
        (case_id || ':' || drug_seq) AS combo_group_id,
        drugcharacterization, medicinalproduct, drugbatchnumb, drugauthorizationnumb,
        drugstructuredosagenumb, drugstructuredosageunit, drugdosagetext, drugdosageform,
        drugadministrationroute, drugindication, drugstartdate, drugstartdateformat,
        drugenddate, drugenddateformat, drugtreatmentduration, drugtreatmentdurationunit,
        actiondrug, drugrecurreadministration, drugrecuraction, drugadditional,
        upper(trim(x)) AS drug_key
    FROM case_drugs, UNNEST(active_ingredients) AS t(x)
    WHERE trim(x) != ''
    UNION ALL
    SELECT
        case_id, drug_seq,
        (case_id || ':' || drug_seq) AS combo_group_id,
        drugcharacterization, medicinalproduct, drugbatchnumb, drugauthorizationnumb,
        drugstructuredosagenumb, drugstructuredosageunit, drugdosagetext, drugdosageform,
        drugadministrationroute, drugindication, drugstartdate, drugstartdateformat,
        drugenddate, drugenddateformat, drugtreatmentduration, drugtreatmentdurationunit,
        actiondrug, drugrecurreadministration, drugrecuraction, drugadditional,
        upper(trim(medicinalproduct)) AS drug_key
    FROM case_drugs
    WHERE len(active_ingredients) = 0 AND medicinalproduct IS NOT NULL AND trim(medicinalproduct) != ''
)
SELECT * FROM exploded
"""

_HAS_REACTION_REL_SQL = """
SELECT case_id, reaction_seq, upper(trim(reactionmeddrapt)) AS pt_key, reactionoutcome
FROM case_reactions
WHERE reactionmeddrapt IS NOT NULL AND trim(reactionmeddrapt) != ''
"""


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def iter_query_batches(con: duckdb.DuckDBPyConnection, sql: str, batch_size: int = BATCH) -> Iterator[list[dict]]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    while True:
        rows = cur.fetchmany(batch_size)
        if not rows:
            return
        yield [dict(zip(cols, row)) for row in rows]


def drug_nodes(con: duckdb.DuckDBPyConnection) -> list[dict]:
    return _rows(con, _DRUG_NODES_SQL)


def reaction_nodes(con: duckdb.DuckDBPyConnection) -> list[dict]:
    return _rows(con, _REACTION_NODES_SQL)


def country_nodes(con: duckdb.DuckDBPyConnection) -> list[dict]:
    return _rows(con, _COUNTRY_NODES_SQL)


def case_node_batches(con: duckdb.DuckDBPyConnection, batch_size: int = BATCH) -> Iterator[list[dict]]:
    return iter_query_batches(con, _CASE_NODES_SQL, batch_size)


def case_country_rel_batches(con: duckdb.DuckDBPyConnection, batch_size: int = BATCH) -> Iterator[list[dict]]:
    return iter_query_batches(con, _CASE_COUNTRY_REL_SQL, batch_size)


def involves_drug_rel_batches(con: duckdb.DuckDBPyConnection, batch_size: int = BATCH) -> Iterator[list[dict]]:
    return iter_query_batches(con, _INVOLVES_DRUG_REL_SQL, batch_size)


def has_reaction_rel_batches(con: duckdb.DuckDBPyConnection, batch_size: int = BATCH) -> Iterator[list[dict]]:
    return iter_query_batches(con, _HAS_REACTION_REL_SQL, batch_size)
