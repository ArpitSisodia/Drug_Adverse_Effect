from dataclasses import dataclass

from neo4j import Session
from pydantic import BaseModel

from chatbot.gemini_client import generate_structured
from chatbot.query_templates import TEMPLATES, UNSUPPORTED_EXPLANATIONS, Template
from ontology.entity_resolution import resolve_drug_name, resolve_reaction_name

_CATEGORY_NAMES = list(TEMPLATES.keys()) + ["unsupported", "other"]


class Classification(BaseModel):
    category: str
    drug_names: list[str]
    reaction_names: list[str]
    top_n: int
    unsupported_reason: str | None


_CLASSIFY_PROMPT = """You are a query classifier for a drug-adverse-event chatbot backed by
FDA FAERS spontaneous adverse-event report data (2026Q2 only).

Classify the user's question into exactly one category from this list:
{categories}

Category meanings:
- drug_report_count: how many reports mention one drug
- top_drugs_overall: top-N drugs by report count
- top_reactions_overall: top-N most-reported reactions overall
- drug_top_reactions: what reactions are most reported alongside one drug
- reaction_top_drugs: what drugs are most reported alongside one reaction
- drug_seriousness_breakdown: death/hospitalization/serious counts for one drug
- drug_demographic_breakdown: age/sex breakdown of reports for one drug
- compare_drugs_report_counts: compare report counts between exactly two drugs
- unsupported: the question asks for something FAERS data cannot answer -- true
  incidence/prevalence rates (reason: "incidence"), causality claims (reason:
  "causality"), trends over time / other quarters (reason: "trend"), or linking a
  SPECIFIC reaction to a SPECIFIC drug within one multi-drug case (reason:
  "drug_reaction_pairing")
- other: anything else / doesn't fit the above categories

Extract any drug names and reaction/adverse-event names mentioned, verbatim as the
user typed them (do not normalize/correct spelling). Default top_n to 10 if the
question doesn't specify a number.

Question: {question}
"""


def classify(question: str) -> Classification:
    prompt = _CLASSIFY_PROMPT.format(categories=", ".join(_CATEGORY_NAMES), question=question)
    return generate_structured(prompt, Classification)


@dataclass
class RoutedQuery:
    template: Template | None
    cypher: str | None
    params: dict
    error: str | None = None  # user-facing message when routing fails / is unsupported


def route(session: Session, classification: Classification) -> RoutedQuery:
    if classification.category == "unsupported":
        reason = classification.unsupported_reason or "other"
        explanation = UNSUPPORTED_EXPLANATIONS.get(
            reason, "This question asks for something FAERS report data can't reliably answer."
        )
        return RoutedQuery(template=None, cypher=None, params={}, error=explanation)

    template = TEMPLATES.get(classification.category)
    if template is None:
        return RoutedQuery(
            template=None,
            cypher=None,
            params={},
            error=(
                "I couldn't match that to a question type I currently support. Try asking about "
                "report counts, co-reported reactions/drugs, seriousness, demographics, or a "
                "two-drug comparison."
            ),
        )

    params: dict = {"top_n": max(1, min(classification.top_n or 10, 50))}

    if "drug" in template.required_entities:
        if not classification.drug_names:
            return RoutedQuery(template, None, {}, error="I need a drug name to answer that -- which drug?")
        matches = resolve_drug_name(session, classification.drug_names[0])
        if not matches:
            return RoutedQuery(
                template, None, {}, error=f"I couldn't find a drug matching '{classification.drug_names[0]}' in this dataset."
            )
        params["drug_key"] = matches[0]["drug_key"]
        params["_drug_display"] = matches[0]["name"]

    if "drug_b" in template.required_entities:
        if len(classification.drug_names) < 2:
            return RoutedQuery(template, None, {}, error="I need two drug names to compare -- which two drugs?")
        matches_b = resolve_drug_name(session, classification.drug_names[1])
        if not matches_b:
            return RoutedQuery(
                template, None, {}, error=f"I couldn't find a drug matching '{classification.drug_names[1]}' in this dataset."
            )
        params["drug_key_b"] = matches_b[0]["drug_key"]
        params["_drug_b_display"] = matches_b[0]["name"]

    if "reaction" in template.required_entities:
        if not classification.reaction_names:
            return RoutedQuery(template, None, {}, error="I need a reaction/adverse-event name to answer that -- which one?")
        matches = resolve_reaction_name(session, classification.reaction_names[0])
        if not matches:
            return RoutedQuery(
                template,
                None,
                {},
                error=f"I couldn't find a reaction matching '{classification.reaction_names[0]}' in this dataset.",
            )
        params["reaction_key"] = matches[0]["pt_key"]
        params["_reaction_display"] = matches[0]["pt"]

    return RoutedQuery(template=template, cypher=template.cypher, params=params)
