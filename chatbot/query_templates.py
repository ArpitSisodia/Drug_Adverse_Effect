"""Pre-built, parametrized Cypher templates for the ~8 core question categories.

Template-first design: the LLM only classifies the question + extracts entity
names/params (see query_router.py); the actual Cypher is fixed here, never
LLM-generated, for every category except UNSUPPORTED/OTHER. This keeps answers
reliable on a Gemini free-tier budget and makes "never causal" phrasing a
property of the template, not something the LLM has to remember every time.
"""

from dataclasses import dataclass


@dataclass
class Template:
    name: str
    description: str
    cypher: str
    required_entities: list[str]  # subset of {"drug", "drug_b", "reaction"}
    needs_top_n: bool = False


TEMPLATES: dict[str, Template] = {
    "drug_report_count": Template(
        name="drug_report_count",
        description="How many reports mention a given drug.",
        cypher="MATCH (d:Drug {drug_key: $drug_key}) RETURN d.name AS drug, d.total_case_count AS report_count",
        required_entities=["drug"],
    ),
    "top_drugs_overall": Template(
        name="top_drugs_overall",
        description="Top-N drugs by total report count.",
        cypher="""
            MATCH (d:Drug) WHERE d.total_case_count IS NOT NULL
            RETURN d.name AS drug, d.total_case_count AS report_count
            ORDER BY report_count DESC LIMIT $top_n
        """,
        required_entities=[],
        needs_top_n=True,
    ),
    "top_reactions_overall": Template(
        name="top_reactions_overall",
        description="Top-N most-reported reactions overall.",
        cypher="""
            MATCH ()-[rel:HAS_REACTION]->(r:Reaction)
            RETURN r.pt AS reaction, count(rel) AS report_count
            ORDER BY report_count DESC LIMIT $top_n
        """,
        required_entities=[],
        needs_top_n=True,
    ),
    "drug_top_reactions": Template(
        name="drug_top_reactions",
        description="Reactions most often co-reported with a given drug (not causal).",
        cypher="""
            MATCH (d:Drug {drug_key: $drug_key})-[rel:REPORTED_WITH]->(r:Reaction)
            RETURN r.pt AS reaction, rel.case_count AS report_count
            ORDER BY report_count DESC LIMIT $top_n
        """,
        required_entities=["drug"],
        needs_top_n=True,
    ),
    "reaction_top_drugs": Template(
        name="reaction_top_drugs",
        description="Drugs most often co-reported with a given reaction (not causal).",
        cypher="""
            MATCH (d:Drug)-[rel:REPORTED_WITH]->(r:Reaction {pt_key: $reaction_key})
            RETURN d.name AS drug, rel.case_count AS report_count
            ORDER BY report_count DESC LIMIT $top_n
        """,
        required_entities=["reaction"],
        needs_top_n=True,
    ),
    "drug_seriousness_breakdown": Template(
        name="drug_seriousness_breakdown",
        description="Seriousness/outcome flag counts (death, hospitalization, etc.) among reports for a drug.",
        cypher="""
            MATCH (c:Case)-[:INVOLVES_DRUG]->(d:Drug {drug_key: $drug_key})
            RETURN
                count(DISTINCT c) AS total_reports,
                count(DISTINCT CASE WHEN c.seriousnessdeath = '1' THEN c END) AS death_reports,
                count(DISTINCT CASE WHEN c.seriousnesshospitalization = '1' THEN c END) AS hospitalization_reports,
                count(DISTINCT CASE WHEN c.seriousnesslifethreatening = '1' THEN c END) AS life_threatening_reports,
                count(DISTINCT CASE WHEN c.serious = '1' THEN c END) AS serious_reports
        """,
        required_entities=["drug"],
    ),
    "drug_demographic_breakdown": Template(
        name="drug_demographic_breakdown",
        description="Age/sex breakdown of reports for a given drug.",
        cypher="""
            MATCH (c:Case)-[:INVOLVES_DRUG]->(d:Drug {drug_key: $drug_key})
            RETURN c.patientsex_label AS sex, count(DISTINCT c) AS n, avg(c.patientonsetage_years) AS mean_age_years
            ORDER BY n DESC
        """,
        required_entities=["drug"],
    ),
    "compare_drugs_report_counts": Template(
        name="compare_drugs_report_counts",
        description="Compare total and serious report counts between two drugs (counts only, not risk).",
        cypher="""
            MATCH (c:Case)-[:INVOLVES_DRUG]->(d:Drug)
            WHERE d.drug_key IN [$drug_key, $drug_key_b]
            RETURN d.name AS drug, count(DISTINCT c) AS total_reports,
                   count(DISTINCT CASE WHEN c.serious = '1' THEN c END) AS serious_reports
        """,
        required_entities=["drug", "drug_b"],
    ),
}

CAVEAT = (
    "This reflects counts of spontaneous FAERS reports for 2026Q2 only -- it does not "
    "establish causality, incidence, or risk, and comparisons between drugs are not "
    "statistically controlled."
)

UNSUPPORTED_EXPLANATIONS = {
    "incidence": "FAERS has no exposure denominator (how many people took the drug), so true incidence/prevalence rates can't be calculated -- only report counts.",
    "causality": "Spontaneous adverse-event reports cannot establish that a drug caused a reaction -- I can only tell you how often they were reported together.",
    "trend": "This dataset covers 2026Q2 only, so I can't answer questions about trends over time or across other quarters.",
    "drug_reaction_pairing": "FAERS reports don't link a specific reaction to a specific drug within a multi-drug case -- I can only tell you which drugs and reactions were reported together in the same case.",
}
