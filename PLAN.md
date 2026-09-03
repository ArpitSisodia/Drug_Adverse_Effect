# Plan: FAERS Drug-Adverse-Event Ontology → Neo4j Knowledge Graph → Streamlit/Gemini Chatbot

## Context

`drug_adverse_ontology` currently contains only raw FDA FAERS data for 2026Q2 (422,459 adverse-event case reports, split across three ~700MB E2B/ICH XML files, plus a deletion list and FDA docs) and one summary file — no code exists yet. The goal is to turn this raw data into a queryable system: extract a drug↔adverse-event ontology, load it into a Neo4j knowledge graph, and expose it through a Streamlit chatbot (powered by a free-tier Gemini API key) so a user can ask natural-language questions and get grounded answers back.

Confirmed decisions from discussion with the user:
1. **Knowledge graph**: Neo4j (property graph / Cypher).
2. **LLM**: Google Gemini, free-tier API key.
3. **Ingestion**: prototype end-to-end on a small sample first, then scale to all 422,459 cases.
4. **Ontology grounding**: custom, built purely from the MedDRA Preferred Term strings and drug-name strings already present in the FAERS extract — no external MedDRA/RxNorm/ATC vocabulary licensing.

The raw XML was inspected directly (`faers_xml_2026q2\XML\1_ADR26Q2.xml`, first 150 lines) to confirm structural assumptions before finalizing this plan — see §2 for the confirmed shape.

## Answering the two open questions

**"Should I store all data in the knowledge graph?"** No — recommend a **two-store split**: Neo4j holds the deduplicated ontology (Drug/Reaction/Indication/Country nodes + Case nodes with per-occurrence relationships, plus precomputed aggregate edges), while a DuckDB staging store holds the full granular per-case/per-drug/per-reaction rows. Rationale in §4. Neo4j alone would work but makes ad hoc statistical breakdowns (age distributions, multi-way group-bys) awkward and makes iterating on ontology/dedup rules expensive (full re-parse of 2.2GB of XML instead of re-deriving from staged Parquet/DuckDB).

**"What kind of questions can be answered?"** See §7 for the full taxonomy. In short: report counts and top-N rankings for drugs/reactions, drug↔reaction co-occurrence ("what reactions are most reported alongside drug X"), demographic subgroup breakdowns (age/sex), outcome/seriousness statistics (death/hospitalization rates as reported counts), and count-based comparisons between drugs. Explicitly **not** answerable: true incidence rates, causality claims, cross-quarter trends (this is single-quarter data), or per-drug-to-per-reaction causal pairing within a case (E2B only gives case-level co-occurrence).

## 1. Repository layout

```
drug_adverse_ontology\
├── faers_xml_2026q2\              # existing raw data — untouched, read-only input
├── PLAN.md                        # this document
├── data\
│   ├── sample\                    # Parquet output of sample ingestion runs
│   ├── staging\                   # full-scale Parquet + DuckDB file (faers_staging.duckdb)
│   └── bulk_import\               # CSVs generated for neo4j-admin database import
├── ingestion\
│   ├── schema.py                  # dataclasses: RawCase, RawDrug, RawReaction
│   ├── delete_list.py             # load_delete_ids(path) -> set[str]
│   ├── xml_stream_parser.py       # iterparse-based case extractor
│   ├── normalize.py               # normalize_drug_name, parse_partial_date, split_active_substances
│   ├── sampler.py                 # max-cases / max-bytes stopping logic
│   └── run_ingest.py              # CLI: python -m ingestion.run_ingest --mode sample|full ...
├── ontology\
│   ├── code_lookups.py            # static dicts: route/age-unit/outcome/qualification/country codes
│   ├── entity_resolution.py       # normalize+key functions shared by ingest & chatbot
│   └── build_graph_records.py     # staging tables -> node/relationship record generators
├── graph_load\
│   ├── schema_ddl.cypher          # constraints + indexes + fulltext indexes
│   ├── load_batched.py            # UNWIND transactional loader (sample mode)
│   ├── load_bulk_admin_import.py  # DuckDB -> CSV, wraps neo4j-admin import (full scale)
│   ├── postload_aggregates.cypher # REPORTED_WITH, INDICATED_FOR, Drug.total_case_count
│   └── verify_queries.cypher      # sanity-check queries used at every milestone
├── chatbot\
│   ├── app.py                     # Streamlit entrypoint
│   ├── gemini_client.py           # google-genai wrapper: retry/backoff, rate limiter
│   ├── schema_context.py          # short hand-written schema description for prompts
│   ├── query_templates.py         # ~15 parametrized Cypher/SQL templates
│   ├── query_router.py            # classify question -> template params, or text-to-Cypher fallback
│   ├── cypher_safety.py           # denylist, LIMIT injection, dry-run, timeout
│   └── answer_synthesis.py        # deterministic templating + optional Gemini summary + caveat
├── config\
│   ├── settings.py                # NEO4J_URI/USER/PASSWORD, GEMINI_API_KEY, paths
│   └── .env.example
├── scripts\                       # setup_env.ps1, run_sample_pipeline.ps1, run_full_pipeline.ps1
├── tests\                         # fixtures + unit tests for parsing/normalization/templates
└── requirements.txt / README.md
```

## 2. Confirmed raw XML shape

Root `<ichicsr>` → repeated `<safetyreport>` elements (this is the case boundary for streaming). Inside each `<safetyreport>`, top-level case fields (`safetyreportid`, `serious*` flags, `receivedate`, etc.) sit alongside one `<patient>` block, and **`<reaction>` and `<drug>` are children of `<patient>`**, not of `<safetyreport>` directly. Each `<drug>` nests `activesubstance/activesubstancename` two levels deep (not a flat child) — confirmed live in the file. The DOCTYPE references `ich-icsr-v2.1.dtd`, which is **not present** in the folder, so the parser must be configured with `load_dtd=False, no_network=True` or parsing will hang trying to resolve it.

## 3. Ontology / Graph schema (Neo4j)

**Nodes**: `Case` (key `safetyreportid`; carries all case-level + patient-demographic-snapshot properties — no separate Patient node since FAERS has no persistent cross-report patient identity), `Drug` (key = normalized active-substance name, falling back to `medicinalproduct` when substance is absent), `Reaction` (key = normalized MedDRA PT string), `Indication` (same normalization, since it's also a MedDRA PT string), `Country`.

**Relationships**: `(Case)-[:INVOLVES_DRUG {role, dose, route, dates, action_taken, dechallenge, rechallenge, combo_group_id}]->(Drug)`, `(Case)-[:HAS_REACTION {outcome_code, outcome_label}]->(Reaction)`, `(Case)-[:PRIMARY_SOURCE_COUNTRY / OCCURRED_IN_COUNTRY]->(Country)`, plus two **precomputed** aggregate edges built once after load: `(Drug)-[:REPORTED_WITH {case_count}]->(Reaction)` and `(Drug)-[:INDICATED_FOR {case_count}]->(Indication)`, and `Drug.total_case_count`. These precomputed aggregates are the key reason common chatbot questions ("top reactions for drug X") resolve as a single indexed lookup instead of a live multi-million-relationship aggregation on every chat turn.

Combination-drug products are split into one `Drug` node per distinct active ingredient (not one composite node per ingredient-set), with a shared `combo_group_id` on the relationships so "administered together" is still recoverable — this keeps simple ingredient lookups exact-match instead of substring search.

**Known limitation to surface in the UI**: no synonym table means true synonyms (brand vs. generic, alternate spellings) won't be merged — a direct consequence of the "no external vocabulary" decision.

## 4. Storage split: Neo4j (ontology) + DuckDB (staging)

Neo4j holds the deduplicated graph + precomputed aggregates and answers most chatbot questions in one call. DuckDB (`data/staging/faers_staging.duckdb`, mirroring three Parquet tables — `cases`, `case_drugs`, `case_reactions`) holds the full granular rows and is used for (a) demographic/statistical breakdowns needing GROUP BY/percentile-style SQL, (b) case-level drill-down/examples, and (c) regenerating the graph cheaply when ontology/dedup rules change during development, without re-parsing 2.2GB of XML. Both stores share `safetyreportid` as the join key.

## 5. Loading strategy

Constraints/indexes (`schema_ddl.cypher`) created before any load: uniqueness constraints on `Case.safetyreportid`, `Drug.drug_key`, `Reaction.pt_key`, `Indication.pt_key`, `Country.code`, plus fulltext indexes on `Drug.name` and `Reaction.pt` (needed so the chatbot can resolve fuzzy/misspelled user-typed drug and reaction names). Two loader modes: batched transactional `UNWIND ... MERGE` writes via the `neo4j` Python driver for the sample/dev cycle, and a DuckDB→CSV export feeding `neo4j-admin database import` for the full 422K-case load (10-100x faster at that scale; requires the target DB stopped first on Windows). Aggregate edges are computed in a separate post-load Cypher pass in both modes.

## 6. Chatbot architecture (Streamlit + Gemini free tier)

**Template-first router with a constrained text-to-Cypher fallback** — not raw free-form text-to-Cypher as the primary path, to keep it reliable on a free-tier quota/rate-limit budget:
1. One Gemini call (JSON/structured-output mode) classifies the question into a category + extracts entities (drug/reaction names, demographic filter, top_n).
2. If it matches one of ~15 pre-built parametrized Cypher/SQL templates, resolve entity names via the fulltext indexes and execute directly — no second LLM call needed.
3. Only unmatched questions fall back to a second, constrained Gemini call that generates Cypher against a short hand-written schema description, with explicit read-only instructions and few-shot examples.
4. Every query (templated or fallback) passes through a safety layer: write-keyword denylist, forced `LIMIT`, dry-run syntax check, and a query timeout.
5. Simple results get a deterministic Python-templated answer (saves quota); only multi-row/comparative results get a third, instructed Gemini call for a natural-language summary. The no-causality/no-incidence caveat is appended deterministically in Python (not left to the LLM) and shown persistently in the sidebar.
6. Client-side rate limiting/backoff and per-question response caching guard the free-tier RPM ceiling.

Explicitly-unsupported question types (incidence rates, causality, cross-quarter trends, per-drug-per-reaction causal pairing) are detected at classification and refused with an explanation, rather than silently routed to a template.

## 7. Example question taxonomy (answerable)

- **Descriptive/aggregate**: "How many reports mention ibuprofen?", "Top 10 most-reported reactions overall", "Top 10 drugs by report count."
- **Relationship/co-occurrence**: "What reactions are most often reported for patients taking POMALYST?", "Which drugs are most often reported alongside Hypotension?"
- **Demographic subgroup**: "Age/sex breakdown of reports involving drug X", "Median patient age for serious reports of drug Y."
- **Outcome/seriousness**: "How many reports involving drug X resulted in death?", "Outcome distribution for reaction Z."
- **Comparative (counts only, with caveat)**: "Compare serious-report counts between drug A and drug B" — always framed as report volume, never risk.

**Not answerable from this data**: true incidence/prevalence, causality, cross-quarter trends, statistical risk comparisons, or exact per-drug-to-per-reaction pairing within a case.

## 8. Phased build plan (each phase has a concrete verification step)

| Phase | Work | Verify |
|---|---|---|
| 0 | Install Neo4j, Python deps, `.env` | imports succeed; `cypher-shell` connects |
| 1 | Streaming parser + normalization on a ~5,000-case sample from file 1 | manifest counts sane; manually cross-check one known case's fields against raw XML |
| 2 | Load sample Parquet into DuckDB | row counts match; point-lookup a known case |
| 3 | Build ontology records, load into fresh Neo4j, run aggregate pass | node/relationship counts match sample size; spot-check a `REPORTED_WITH` count against a manual aggregation |
| 4 | Minimal Streamlit chatbot on the sample (5-6 templates) | manually ask ~10-15 taxonomy questions, confirm against direct Cypher/SQL; confirm unsupported questions are refused |
| 5 | Harden chatbot (fallback text-to-Cypher, safety layer, rate limiting) | prompt-injection/write-query attempt is blocked; ambiguous drug names handled gracefully |
| 6 | Scale ingestion to all 3 XML files / 422,459 cases | kept-case count reconciles with `XML26Q2.pdf`'s 422,459; log `DELETE26Q2.txt` overlap count |
| 7 | Full-scale Neo4j load via `neo4j-admin database import` + aggregates | counts match Phase 6 staging; re-run Phase 4's validation questions at scale |
| 8 | Point chatbot at full DB, polish, tune slow queries/indexes | full taxonomy re-run end-to-end; rapid-fire questions degrade gracefully under rate limiting |

## 9. Key risks to keep in mind

Most XML fields are optional and frequently absent (must code defensively, null-aware aggregation). Dates can be partial (YYYY/YYYYMM/YYYYMMDD) — never do date arithmetic across mismatched precisions. The DTD reference must not be resolved (parser config). Drug↔reaction co-occurrence is not causal and every answer (template or LLM) must be phrased as "reported alongside," never "caused by." Gemini's free tier has a low RPM ceiling that will be visibly felt during rapid testing — mitigated by the template-first design, caching, and minimizing calls per question. All commands/scripts are PowerShell-only (no bash); `neo4j-admin database import` requires the target database stopped first on Windows.
