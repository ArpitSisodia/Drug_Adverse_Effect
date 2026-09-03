from pathlib import Path
from typing import IO, Iterator

from lxml import etree

from ingestion.normalize import (
    age_to_years,
    clean_text,
    extract_narrative_event_date,
    split_active_substances,
)
from ingestion.schema import ParsedCase, RawCase, RawDrug, RawReaction


def _text(elem, path: str) -> str | None:
    if elem is None:
        return None
    val = elem.findtext(path)
    return clean_text(val) if val is not None else None


def _extract_drug(drug_elem, case_id: str, seq: int) -> RawDrug:
    active_names = [t.text for t in drug_elem.findall("activesubstance/activesubstancename") if t.text]
    return RawDrug(
        case_id=case_id,
        drug_seq=seq,
        drugcharacterization=_text(drug_elem, "drugcharacterization"),
        medicinalproduct=_text(drug_elem, "medicinalproduct"),
        active_ingredients=split_active_substances(active_names),
        drugbatchnumb=_text(drug_elem, "drugbatchnumb"),
        drugauthorizationnumb=_text(drug_elem, "drugauthorizationnumb"),
        drugstructuredosagenumb=_text(drug_elem, "drugstructuredosagenumb"),
        drugstructuredosageunit=_text(drug_elem, "drugstructuredosageunit"),
        drugdosagetext=_text(drug_elem, "drugdosagetext"),
        drugdosageform=_text(drug_elem, "drugdosageform"),
        drugadministrationroute=_text(drug_elem, "drugadministrationroute"),
        drugindication=_text(drug_elem, "drugindication"),
        drugstartdate=_text(drug_elem, "drugstartdate"),
        drugstartdateformat=_text(drug_elem, "drugstartdateformat"),
        drugenddate=_text(drug_elem, "drugenddate"),
        drugenddateformat=_text(drug_elem, "drugenddateformat"),
        drugtreatmentduration=_text(drug_elem, "drugtreatmentduration"),
        drugtreatmentdurationunit=_text(drug_elem, "drugtreatmentdurationunit"),
        actiondrug=_text(drug_elem, "actiondrug"),
        drugrecurreadministration=_text(drug_elem, "drugrecurreadministration"),
        drugrecuraction=_text(drug_elem, "drugrecuraction"),
        drugadditional=_text(drug_elem, "drugadditional"),
    )


def _extract_reaction(reaction_elem, case_id: str, seq: int) -> RawReaction:
    return RawReaction(
        case_id=case_id,
        reaction_seq=seq,
        reactionmeddraversionpt=_text(reaction_elem, "reactionmeddraversionpt"),
        reactionmeddrapt=_text(reaction_elem, "reactionmeddrapt"),
        reactionoutcome=_text(reaction_elem, "reactionoutcome"),
    )


def _extract_case(report_elem, source_file: str) -> ParsedCase | None:
    case_id = _text(report_elem, "safetyreportid")
    if not case_id:
        return None

    patient_elem = report_elem.find("patient")
    onset_age = _text(patient_elem, "patientonsetage")
    onset_unit = _text(patient_elem, "patientonsetageunit")
    # narrativeincludeclinical's exact nesting varies by submission path (paper vs E2B);
    # search any descendant of <patient> rather than assuming a fixed depth.
    narrative = patient_elem.findtext(".//narrativeincludeclinical") if patient_elem is not None else None

    case = RawCase(
        safetyreportid=case_id,
        safetyreportversion=_text(report_elem, "safetyreportversion"),
        primarysourcecountry=_text(report_elem, "primarysourcecountry"),
        occurcountry=_text(report_elem, "occurcountry"),
        receivedate=_text(report_elem, "receivedate"),
        receiptdate=_text(report_elem, "receiptdate"),
        reporttype=_text(report_elem, "reporttype"),
        serious=_text(report_elem, "serious"),
        seriousnessdeath=_text(report_elem, "seriousnessdeath"),
        seriousnesslifethreatening=_text(report_elem, "seriousnesslifethreatening"),
        seriousnesshospitalization=_text(report_elem, "seriousnesshospitalization"),
        seriousnessdisabling=_text(report_elem, "seriousnessdisabling"),
        seriousnesscongenitalanomali=_text(report_elem, "seriousnesscongenitalanomali"),
        seriousnessother=_text(report_elem, "seriousnessother"),
        fulfillexpeditecriteria=_text(report_elem, "fulfillexpeditecriteria"),
        reportercountry=_text(report_elem, "primarysource/reportercountry"),
        qualification=_text(report_elem, "primarysource/qualification"),
        senderorganization=_text(report_elem, "sender/senderorganization"),
        companynumb=_text(report_elem, "companynumb"),
        patientonsetage=onset_age,
        patientonsetageunit=onset_unit,
        patientonsetage_years=age_to_years(onset_age, onset_unit),
        patientagegroup=_text(patient_elem, "patientagegroup"),
        patientweight=_text(patient_elem, "patientweight"),
        patientsex=_text(patient_elem, "patientsex"),
        event_date_from_narrative=extract_narrative_event_date(narrative),
        source_file=source_file,
    )

    drugs: list[RawDrug] = []
    reactions: list[RawReaction] = []
    if patient_elem is not None:
        drugs = [_extract_drug(d, case_id, i) for i, d in enumerate(patient_elem.findall("drug"), start=1)]
        reactions = [
            _extract_reaction(r, case_id, i) for i, r in enumerate(patient_elem.findall("reaction"), start=1)
        ]

    return ParsedCase(case=case, drugs=drugs, reactions=reactions)


class _ByteLimitedReader:
    """Wraps a binary file object; read() returns b'' once a byte budget is exceeded.

    lxml's iterparse accepts any file-like object with .read(size), so this lets
    --max-bytes sampling stop early without reading the whole multi-hundred-MB file.
    """

    def __init__(self, fileobj: IO[bytes], max_bytes: int | None):
        self._f = fileobj
        self._max_bytes = max_bytes
        self.exceeded = False

    def read(self, size: int = -1) -> bytes:
        if self._max_bytes is not None and self._f.tell() >= self._max_bytes:
            self.exceeded = True
            return b""
        return self._f.read(size)


def iter_cases(
    xml_path: Path,
    delete_ids: set[str] | None = None,
    max_cases: int | None = None,
    max_bytes: int | None = None,
) -> Iterator[ParsedCase]:
    """Stream-parse one ADR*.xml FAERS file, yielding one ParsedCase per <safetyreport>.

    Memory-safe for multi-hundred-MB files: after each report is processed, both the
    element itself and its now-dead preceding siblings under <ichicsr> are cleared, so
    peak memory stays roughly constant regardless of how many cases have been seen.
    Never resolves the file's DOCTYPE (no_network/load_dtd off) since the referenced
    ich-icsr-v2.1.dtd is not shipped alongside the data and would otherwise stall parsing.
    """
    delete_ids = delete_ids or set()

    with open(xml_path, "rb") as fileobj:
        source = _ByteLimitedReader(fileobj, max_bytes) if max_bytes else fileobj
        context = etree.iterparse(
            source,
            events=("end",),
            tag="safetyreport",
            load_dtd=False,
            no_network=True,
            huge_tree=True,
        )
        kept = 0
        for _, elem in context:
            parsed = _extract_case(elem, source_file=xml_path.name)
            if parsed is not None and parsed.case.safetyreportid not in delete_ids:
                yield parsed
                kept += 1
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
            if max_cases is not None and kept >= max_cases:
                break
            if max_bytes is not None and getattr(source, "exceeded", False):
                break
