// Run after all Case/Drug/Reaction nodes and INVOLVES_DRUG/HAS_REACTION relationships
// are loaded. Builds precomputed aggregates so common chatbot questions ("top reactions
// for drug X") are a single indexed lookup instead of a live multi-relationship
// aggregation on every chat turn. REPORTED_WITH/INDICATED_FOR are co-occurrence counts,
// never causal claims.

MATCH (d:Drug)<-[:INVOLVES_DRUG]-(c:Case)
WITH d, count(DISTINCT c) AS n
SET d.total_case_count = n;

MATCH (c:Case)-[:INVOLVES_DRUG]->(d:Drug)
MATCH (c)-[:HAS_REACTION]->(r:Reaction)
WITH d, r, count(DISTINCT c) AS case_count
MERGE (d)-[rel:REPORTED_WITH]->(r)
SET rel.case_count = case_count;

MATCH (c:Case)-[inv:INVOLVES_DRUG]->(d:Drug)
WHERE inv.indication_pt IS NOT NULL AND trim(inv.indication_pt) <> ''
WITH d, toUpper(trim(inv.indication_pt)) AS ind_key, trim(inv.indication_pt) AS ind_pt, c
MERGE (i:Indication {pt_key: ind_key})
ON CREATE SET i.pt = ind_pt
WITH d, i, count(DISTINCT c) AS case_count
MERGE (d)-[rel:INDICATED_FOR]->(i)
SET rel.case_count = case_count;
