CREATE CONSTRAINT case_id_unique IF NOT EXISTS FOR (c:Case) REQUIRE c.safetyreportid IS UNIQUE;
CREATE CONSTRAINT drug_key_unique IF NOT EXISTS FOR (d:Drug) REQUIRE d.drug_key IS UNIQUE;
CREATE CONSTRAINT reaction_key_unique IF NOT EXISTS FOR (r:Reaction) REQUIRE r.pt_key IS UNIQUE;
CREATE CONSTRAINT indication_key_unique IF NOT EXISTS FOR (i:Indication) REQUIRE i.pt_key IS UNIQUE;
CREATE CONSTRAINT country_code_unique IF NOT EXISTS FOR (co:Country) REQUIRE co.code IS UNIQUE;
CREATE INDEX case_serious_idx IF NOT EXISTS FOR (c:Case) ON (c.serious);
CREATE INDEX case_receivedate_idx IF NOT EXISTS FOR (c:Case) ON (c.receivedate);
CREATE FULLTEXT INDEX drugNameFulltext IF NOT EXISTS FOR (d:Drug) ON EACH [d.name];
CREATE FULLTEXT INDEX reactionPtFulltext IF NOT EXISTS FOR (r:Reaction) ON EACH [r.pt];
