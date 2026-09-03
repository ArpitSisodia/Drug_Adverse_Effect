"""Turns raw Cypher result rows into a natural-language answer.

Deterministic string templating only (no LLM call) -- every phrase here is
hand-written to say "reported"/"co-reported", never "caused"/"risk", so the
no-causality guarantee doesn't depend on an LLM remembering the instruction
on every turn. The caveat line is always appended in Python, never left to
an LLM to include or omit.
"""

from chatbot.query_templates import CAVEAT


def _fmt_int(n) -> str:
    return f"{int(n):,}" if n is not None else "0"


def synthesize(category: str, rows: list[dict], params: dict) -> str:
    if not rows:
        return f"No matching data found in this dataset.\n\n_{CAVEAT}_"

    if category == "drug_report_count":
        r = rows[0]
        body = f"**{r['drug']}** appears in **{_fmt_int(r['report_count'])}** FAERS reports in this dataset."

    elif category == "top_drugs_overall":
        lines = [f"{i+1}. {r['drug']} -- {_fmt_int(r['report_count'])} reports" for i, r in enumerate(rows)]
        body = "Top drugs by report count:\n\n" + "\n".join(lines)

    elif category == "top_reactions_overall":
        lines = [f"{i+1}. {r['reaction']} -- {_fmt_int(r['report_count'])} reports" for i, r in enumerate(rows)]
        body = "Most-reported reactions overall:\n\n" + "\n".join(lines)

    elif category == "drug_top_reactions":
        drug = params.get("_drug_display", "this drug")
        lines = [f"{i+1}. {r['reaction']} -- co-reported in {_fmt_int(r['report_count'])} reports" for i, r in enumerate(rows)]
        body = f"Reactions most often co-reported alongside **{drug}**:\n\n" + "\n".join(lines)

    elif category == "reaction_top_drugs":
        reaction = params.get("_reaction_display", "this reaction")
        lines = [f"{i+1}. {r['drug']} -- co-reported in {_fmt_int(r['report_count'])} reports" for i, r in enumerate(rows)]
        body = f"Drugs most often co-reported alongside **{reaction}**:\n\n" + "\n".join(lines)

    elif category == "drug_seriousness_breakdown":
        drug = params.get("_drug_display", "this drug")
        r = rows[0]
        body = (
            f"Of **{_fmt_int(r['total_reports'])}** reports involving **{drug}**:\n\n"
            f"- Marked overall serious: {_fmt_int(r['serious_reports'])}\n"
            f"- Death: {_fmt_int(r['death_reports'])}\n"
            f"- Hospitalization: {_fmt_int(r['hospitalization_reports'])}\n"
            f"- Life-threatening: {_fmt_int(r['life_threatening_reports'])}"
        )

    elif category == "drug_demographic_breakdown":
        drug = params.get("_drug_display", "this drug")
        lines = []
        for r in rows:
            age = f", mean age {r['mean_age_years']:.1f} yrs" if r.get("mean_age_years") is not None else ""
            lines.append(f"- {r['sex'] or 'Unknown'}: {_fmt_int(r['n'])} reports{age}")
        body = f"Demographic breakdown of reports involving **{drug}**:\n\n" + "\n".join(lines)

    elif category == "compare_drugs_report_counts":
        lines = [f"- {r['drug']}: {_fmt_int(r['total_reports'])} total reports, {_fmt_int(r['serious_reports'])} marked serious" for r in rows]
        body = "Report-count comparison (counts only, not a risk comparison):\n\n" + "\n".join(lines)

    else:
        body = str(rows)

    return f"{body}\n\n_{CAVEAT}_"
