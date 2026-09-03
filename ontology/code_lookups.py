"""Static label lookups for FAERS/E2B coded fields (from XML_NTS.pdf / FAQs.pdf).

All lookups are defensive: label(code, table) returns the raw code string
unchanged if the code is missing/unrecognized, rather than raising or
silently dropping data -- FAERS extracts frequently contain codes outside
the documented example lists (e.g. drugadministrationroute has ~40 ICH
codes, only a handful of which are given as examples in the FDA docs).
"""

YES_NO = {"1": "Yes", "2": "No"}

REPORT_TYPE = {
    "1": "Spontaneous",
    "2": "Report from Study",
    "3": "Other",
    "4": "Not available to sender (unknown)",
}

QUALIFICATION = {
    "1": "Physician",
    "2": "Pharmacist",
    "3": "Other Health Professional",
    "4": "Lawyer",
    "5": "Consumer or non-health professional",
}

FULFILL_EXPEDITE_CRITERIA = {
    "1": "Industry expedited report",
    "2": "Industry non-expedited report",
    "3": "Direct Report",
    "4": "5-Day Report",
    "5": "30-Day Report",
}

PATIENT_AGE_GROUP = {
    "1": "Neonate",
    "2": "Infant",
    "3": "Child",
    "4": "Adolescent",
    "5": "Adult",
    "6": "Elderly",
}

PATIENT_SEX = {
    "0": "Unknown",
    "1": "Male",
    "2": "Female",
}

REACTION_OUTCOME = {
    "1": "Recovered/resolved",
    "2": "Recovering/resolving",
    "3": "Not recovered/not resolved",
    "4": "Recovered/resolved with sequelae",
    "5": "Fatal",
    "6": "Unknown",
}

DRUG_CHARACTERIZATION = {
    "1": "Suspect",
    "2": "Concomitant",
    "3": "Interacting",
    "4": "Drug not administered",
}

ACTION_DRUG = {
    "1": "Drug Withdrawn",
    "2": "Dose reduced",
    "3": "Dose Increased",
    "4": "Dose not changed",
    "5": "Unknown",
    "6": "Not applicable",
}

DECHALLENGE = {  # drugadditional
    "1": "Yes",
    "2": "No",
    "3": "Doesn't Apply",
}

RECHALLENGE = {  # drugrecurreadministration
    "1": "Yes",
    "2": "No",
    "3": "Unknown",
}

# Small, non-exhaustive set of commonly-seen ICH route codes; unmapped codes
# fall back to the raw code (full ~40-code table lives in the ICH ICSR spec,
# not reproduced in FDA's public docs -- out of scope per the "no external
# vocabulary" ontology-grounding decision).
DRUG_ADMINISTRATION_ROUTE = {
    "042": "Intramuscular",
    "047": "Intravenous",
    "048": "Oral",
    "058": "Subcutaneous",
    "061": "Topical",
    "065": "Intramuscular/Subcutaneous (injection, unspecified)",
    "071": "Sublingual",
}

DOSAGE_UNIT = {
    "001": "kg",
    "002": "g",
    "003": "mg",
    "004": "µg",
    "501": "Unknown",
}


def label(code: str | None, table: dict[str, str]) -> str | None:
    if code is None:
        return None
    return table.get(code, code)
