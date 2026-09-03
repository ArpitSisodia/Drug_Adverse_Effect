// Ad hoc sanity-check queries, run manually or via scripts during each milestone.

MATCH (c:Case) RETURN count(c) AS case_count;
MATCH (d:Drug) RETURN count(d) AS drug_count;
MATCH (r:Reaction) RETURN count(r) AS reaction_count;
MATCH ()-[rel:INVOLVES_DRUG]->() RETURN count(rel) AS involves_drug_count;
MATCH ()-[rel:HAS_REACTION]->() RETURN count(rel) AS has_reaction_count;

// known sample case: POMALYST/POMALIDOMIDE, 3 reactions
MATCH (c:Case {safetyreportid: '26461578'})-[:INVOLVES_DRUG]->(d:Drug)
RETURN d.name, d.drug_key;
MATCH (c:Case {safetyreportid: '26461578'})-[rel:HAS_REACTION]->(r:Reaction)
RETURN r.pt, rel.outcome_label ORDER BY rel.reaction_seq;

// top reactions reported alongside POMALIDOMIDE
MATCH (d:Drug {drug_key: 'POMALIDOMIDE'})-[rel:REPORTED_WITH]->(r:Reaction)
RETURN r.pt, rel.case_count ORDER BY rel.case_count DESC LIMIT 10;

MATCH (d:Drug {drug_key: 'POMALIDOMIDE'}) RETURN d.total_case_count;
