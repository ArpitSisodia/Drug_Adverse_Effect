from dataclasses import dataclass, field


@dataclass
class RawCase:
    safetyreportid: str
    safetyreportversion: str | None
    primarysourcecountry: str | None
    occurcountry: str | None
    receivedate: str | None
    receiptdate: str | None
    reporttype: str | None
    serious: str | None
    seriousnessdeath: str | None
    seriousnesslifethreatening: str | None
    seriousnesshospitalization: str | None
    seriousnessdisabling: str | None
    seriousnesscongenitalanomali: str | None
    seriousnessother: str | None
    fulfillexpeditecriteria: str | None
    reportercountry: str | None
    qualification: str | None
    senderorganization: str | None
    companynumb: str | None
    patientonsetage: str | None
    patientonsetageunit: str | None
    patientonsetage_years: float | None
    patientagegroup: str | None
    patientweight: str | None
    patientsex: str | None
    event_date_from_narrative: str | None
    source_file: str


@dataclass
class RawDrug:
    case_id: str
    drug_seq: int
    drugcharacterization: str | None
    medicinalproduct: str | None
    active_ingredients: list[str] = field(default_factory=list)
    drugbatchnumb: str | None = None
    drugauthorizationnumb: str | None = None
    drugstructuredosagenumb: str | None = None
    drugstructuredosageunit: str | None = None
    drugdosagetext: str | None = None
    drugdosageform: str | None = None
    drugadministrationroute: str | None = None
    drugindication: str | None = None
    drugstartdate: str | None = None
    drugstartdateformat: str | None = None
    drugenddate: str | None = None
    drugenddateformat: str | None = None
    drugtreatmentduration: str | None = None
    drugtreatmentdurationunit: str | None = None
    actiondrug: str | None = None
    drugrecurreadministration: str | None = None
    drugrecuraction: str | None = None
    drugadditional: str | None = None


@dataclass
class RawReaction:
    case_id: str
    reaction_seq: int
    reactionmeddraversionpt: str | None
    reactionmeddrapt: str | None
    reactionoutcome: str | None


@dataclass
class ParsedCase:
    case: RawCase
    drugs: list[RawDrug]
    reactions: list[RawReaction]
