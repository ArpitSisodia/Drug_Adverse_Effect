"""Batched UNWIND/MERGE loader: DuckDB staging tables -> Neo4j graph.

Intended for the sample/dev cycle (fast to drop-and-reload). The full 422K-case
load uses neo4j-admin database import instead (graph_load/load_bulk_admin_import.py,
not yet built -- sample-first per the plan).

Usage:
    python -m graph_load.load_batched --mode sample --reset
"""

import argparse
import time
from pathlib import Path
from typing import Iterable, Iterator

import duckdb
from neo4j import Driver, GraphDatabase

from config.settings import settings
from ontology import build_graph_records as bgr
from ontology.code_lookups import (
    ACTION_DRUG,
    DECHALLENGE,
    DOSAGE_UNIT,
    DRUG_ADMINISTRATION_ROUTE,
    DRUG_CHARACTERIZATION,
    FULFILL_EXPEDITE_CRITERIA,
    PATIENT_AGE_GROUP,
    PATIENT_SEX,
    QUALIFICATION,
    REACTION_OUTCOME,
    RECHALLENGE,
    REPORT_TYPE,
    label,
)
from ingestion.normalize import date_precision

REL_BATCH = 5000


def _chunked(rows: list[dict], n: int) -> Iterator[list[dict]]:
    for i in range(0, len(rows), n):
        yield rows[i : i + n]


def _enrich_case_row(row: dict) -> dict:
    row = dict(row)
    row["reporttype_label"] = label(row.get("reporttype"), REPORT_TYPE)
    row["fulfillexpeditecriteria_label"] = label(row.get("fulfillexpeditecriteria"), FULFILL_EXPEDITE_CRITERIA)
    row["qualification_label"] = label(row.get("qualification"), QUALIFICATION)
    row["patientagegroup_label"] = label(row.get("patientagegroup"), PATIENT_AGE_GROUP)
    row["patientsex_label"] = label(row.get("patientsex"), PATIENT_SEX)
    return row


def _enrich_drug_rel_row(row: dict) -> dict:
    row = dict(row)
    row["role_label"] = label(row.get("drugcharacterization"), DRUG_CHARACTERIZATION)
    row["dose_unit_label"] = label(row.get("drugstructuredosageunit"), DOSAGE_UNIT)
    row["route_label"] = label(row.get("drugadministrationroute"), DRUG_ADMINISTRATION_ROUTE)
    row["action_taken_label"] = label(row.get("actiondrug"), ACTION_DRUG)
    row["dechallenge_label"] = label(row.get("drugadditional"), DECHALLENGE)
    row["rechallenge_label"] = label(row.get("drugrecurreadministration"), RECHALLENGE)
    row["start_date_precision"] = date_precision(row.get("drugstartdateformat"))
    row["end_date_precision"] = date_precision(row.get("drugenddateformat"))
    return row


def _enrich_reaction_rel_row(row: dict) -> dict:
    row = dict(row)
    row["outcome_label"] = label(row.get("reactionoutcome"), REACTION_OUTCOME)
    return row


def _run_ddl_file(driver: Driver, path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    # strip full-line comments *before* splitting on ';' -- a leading multi-line
    # comment block otherwise merges with the first real statement and both get
    # dropped by a naive "does the whole chunk start with //" check.
    code_only = "\n".join(line for line in text.splitlines() if not line.strip().startswith("//"))
    statements = [s.strip() for s in code_only.split(";") if s.strip()]
    with driver.session(database=settings.neo4j_database) as session:
        for stmt in statements:
            session.run(stmt)


def _reset_db(driver: Driver) -> None:
    with driver.session(database=settings.neo4j_database) as session:
        session.run("MATCH (n) DETACH DELETE n")


def load(mode: str) -> None:
    staging_dir = settings.sample_dir if mode == "sample" else settings.staging_dir
    db_path = staging_dir / ("faers_sample.duckdb" if mode == "sample" else "faers_staging.duckdb")
    if not db_path.exists():
        raise FileNotFoundError(f"staging db not found: {db_path} (run ingestion.staging_db first)")

    con = duckdb.connect(str(db_path), read_only=True)
    driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    started = time.time()

    try:
        with driver.session(database=settings.neo4j_database) as session:
            # --- dedup node sets: countries, drugs, reactions ---
            for rows in _chunked(bgr.country_nodes(con), REL_BATCH):
                session.run("UNWIND $rows AS row MERGE (co:Country {code: row.code})", rows=rows)

            drug_node_rows = bgr.drug_nodes(con)
            for rows in _chunked(drug_node_rows, REL_BATCH):
                session.run(
                    "UNWIND $rows AS row MERGE (d:Drug {drug_key: row.drug_key}) "
                    "SET d.name = row.name, d.name_source = row.name_source",
                    rows=rows,
                )
            print(f"drug nodes: {len(drug_node_rows)}")

            reaction_node_rows = bgr.reaction_nodes(con)
            for rows in _chunked(reaction_node_rows, REL_BATCH):
                session.run(
                    "UNWIND $rows AS row MERGE (r:Reaction {pt_key: row.pt_key}) SET r.pt = row.pt",
                    rows=rows,
                )
            print(f"reaction nodes: {len(reaction_node_rows)}")

            # --- case nodes ---
            case_count = 0
            for batch in bgr.case_node_batches(con, batch_size=REL_BATCH):
                rows = [_enrich_case_row(r) for r in batch]
                session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (c:Case {safetyreportid: row.safetyreportid})
                    SET c.safetyreportversion = row.safetyreportversion,
                        c.primarysourcecountry = row.primarysourcecountry,
                        c.occurcountry = row.occurcountry,
                        c.receivedate = row.receivedate,
                        c.receiptdate = row.receiptdate,
                        c.reporttype = row.reporttype,
                        c.reporttype_label = row.reporttype_label,
                        c.serious = row.serious,
                        c.seriousnessdeath = row.seriousnessdeath,
                        c.seriousnesslifethreatening = row.seriousnesslifethreatening,
                        c.seriousnesshospitalization = row.seriousnesshospitalization,
                        c.seriousnessdisabling = row.seriousnessdisabling,
                        c.seriousnesscongenitalanomali = row.seriousnesscongenitalanomali,
                        c.seriousnessother = row.seriousnessother,
                        c.fulfillexpeditecriteria = row.fulfillexpeditecriteria,
                        c.fulfillexpeditecriteria_label = row.fulfillexpeditecriteria_label,
                        c.qualification = row.qualification,
                        c.qualification_label = row.qualification_label,
                        c.senderorganization = row.senderorganization,
                        c.companynumb = row.companynumb,
                        c.patientonsetage_years = row.patientonsetage_years,
                        c.patientagegroup = row.patientagegroup,
                        c.patientagegroup_label = row.patientagegroup_label,
                        c.patientweight = row.patientweight,
                        c.patientsex = row.patientsex,
                        c.patientsex_label = row.patientsex_label,
                        c.event_date_from_narrative = row.event_date_from_narrative
                    """,
                    rows=rows,
                )
                case_count += len(rows)
            print(f"case nodes: {case_count}")

            # --- case -> country relationships (split by rel_type; Cypher can't parametrize rel type) ---
            for batch in bgr.case_country_rel_batches(con, batch_size=REL_BATCH):
                primary = [r for r in batch if r["rel_type"] == "PRIMARY_SOURCE_COUNTRY"]
                occur = [r for r in batch if r["rel_type"] == "OCCURRED_IN_COUNTRY"]
                if primary:
                    session.run(
                        "UNWIND $rows AS row MATCH (c:Case {safetyreportid: row.safetyreportid}) "
                        "MATCH (co:Country {code: row.code}) MERGE (c)-[:PRIMARY_SOURCE_COUNTRY]->(co)",
                        rows=primary,
                    )
                if occur:
                    session.run(
                        "UNWIND $rows AS row MATCH (c:Case {safetyreportid: row.safetyreportid}) "
                        "MATCH (co:Country {code: row.code}) MERGE (c)-[:OCCURRED_IN_COUNTRY]->(co)",
                        rows=occur,
                    )

            # --- INVOLVES_DRUG relationships ---
            drug_rel_count = 0
            for batch in bgr.involves_drug_rel_batches(con, batch_size=REL_BATCH):
                rows = [_enrich_drug_rel_row(r) for r in batch]
                session.run(
                    """
                    UNWIND $rows AS row
                    MATCH (c:Case {safetyreportid: row.case_id})
                    MATCH (d:Drug {drug_key: row.drug_key})
                    CREATE (c)-[rel:INVOLVES_DRUG {
                        drug_seq: row.drug_seq,
                        combo_group_id: row.combo_group_id,
                        role: row.drugcharacterization,
                        role_label: row.role_label,
                        medicinalproduct: row.medicinalproduct,
                        drugbatchnumb: row.drugbatchnumb,
                        drugauthorizationnumb: row.drugauthorizationnumb,
                        dose_amount: row.drugstructuredosagenumb,
                        dose_unit: row.dose_unit_label,
                        dose_text: row.drugdosagetext,
                        dose_form: row.drugdosageform,
                        route_code: row.drugadministrationroute,
                        route_label: row.route_label,
                        indication_pt: row.drugindication,
                        start_date: row.drugstartdate,
                        start_date_precision: row.start_date_precision,
                        end_date: row.drugenddate,
                        end_date_precision: row.end_date_precision,
                        duration: row.drugtreatmentduration,
                        duration_unit: row.drugtreatmentdurationunit,
                        action_taken_code: row.actiondrug,
                        action_taken_label: row.action_taken_label,
                        dechallenge_code: row.drugadditional,
                        dechallenge_label: row.dechallenge_label,
                        rechallenge_code: row.drugrecurreadministration,
                        rechallenge_label: row.rechallenge_label
                    }]->(d)
                    """,
                    rows=rows,
                )
                drug_rel_count += len(rows)
            print(f"INVOLVES_DRUG relationships: {drug_rel_count}")

            # --- HAS_REACTION relationships ---
            reaction_rel_count = 0
            for batch in bgr.has_reaction_rel_batches(con, batch_size=REL_BATCH):
                rows = [_enrich_reaction_rel_row(r) for r in batch]
                session.run(
                    """
                    UNWIND $rows AS row
                    MATCH (c:Case {safetyreportid: row.case_id})
                    MATCH (r:Reaction {pt_key: row.pt_key})
                    CREATE (c)-[rel:HAS_REACTION {
                        reaction_seq: row.reaction_seq,
                        outcome_code: row.reactionoutcome,
                        outcome_label: row.outcome_label
                    }]->(r)
                    """,
                    rows=rows,
                )
                reaction_rel_count += len(rows)
            print(f"HAS_REACTION relationships: {reaction_rel_count}")

        # --- post-load aggregates ---
        ddl_dir = Path(__file__).parent
        _run_ddl_file(driver, ddl_dir / "postload_aggregates.cypher")
        print("post-load aggregates computed")

    finally:
        con.close()
        driver.close()

    print(f"done in {time.time() - started:.1f}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["sample", "full"], required=True)
    ap.add_argument("--reset", action="store_true", help="DETACH DELETE all nodes before loading")
    args = ap.parse_args()

    driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    try:
        if args.reset:
            print("resetting database...")
            _reset_db(driver)
        _run_ddl_file(driver, Path(__file__).parent / "schema_ddl.cypher")
        print("schema/constraints applied")
    finally:
        driver.close()

    load(args.mode)


if __name__ == "__main__":
    main()
