# FAERS Drug-Adverse-Event Knowledge Graph + Chatbot

Turns the FDA FAERS 2026Q2 quarterly data extract (`faers_xml_2026q2/`) into a
Neo4j knowledge graph and a Streamlit chatbot (Google Gemini) for asking
natural-language questions about reported drug/adverse-event data.

See [PLAN.md](PLAN.md) for the full architecture, ontology schema, and phased
build plan this project follows.

## Prerequisites

- **Python 3.12+** on PATH (`python --version`).
- **Neo4j Desktop**, with a local DBMS created (any name) and its **bolt
  connection details** (URI/user/password) noted down. Neo4j Desktop -> your
  DBMS -> "..." menu -> **Connection details**.
- A **free Gemini API key**: https://aistudio.google.com/apikey.

All commands below are PowerShell, run from the repo root
(`c:\Users\2919234\Documents\drug_adverse_ontology`).

## 1. Start Neo4j

1. Open **Neo4j Desktop**.
2. Click your DBMS (create one first if you haven't: "Add" -> "Local DBMS",
   set a password) and click **Start**. Wait until its status shows
   "Active"/green.
3. Note the bolt URI (default `bolt://localhost:7687`), the username
   (default `neo4j`), and the password you set.

Everything else in this project connects to Neo4j over that bolt URI, so it
must be running (green) before you run ingestion/graph-load/chatbot steps.

## 2. Set up the Python environment (one-time)

```powershell
.\scripts\setup_env.ps1
copy .env.example .env
notepad .env
```

Fill in `.env` with:
- `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` / `NEO4J_DATABASE` from step 1
  (`NEO4J_DATABASE` is usually just `neo4j`).
- `GEMINI_API_KEY` from https://aistudio.google.com/apikey.
- `GEMINI_MODEL` -- if you get a `404 NOT_FOUND ... no longer available`
  error later, the API error message tells you the current replacement model
  name; update this value to match.

This creates a `.venv` virtual environment and installs everything in
`requirements.txt` into it. `.env` is gitignored -- it's never committed.

## 3. Run the sample pipeline (parse -> stage -> graph -> chat)

With Neo4j running (step 1) and `.env` filled in (step 2):

```powershell
.\scripts\run_sample_pipeline.ps1
```

This runs, in order:
1. `ingestion.run_ingest` -- parses 5,000 cases from `1_ADR26Q2.xml` into
   Parquet under `data\sample\`.
2. `ingestion.staging_db` -- loads that Parquet into a DuckDB file at
   `data\sample\faers_sample.duckdb`.
3. `graph_load.load_batched --reset` -- wipes and reloads the Neo4j graph
   from that staging DB (nodes, relationships, precomputed aggregates).
4. `streamlit run chatbot/app.py` -- starts the chatbot web app and blocks
   in that terminal.

Once step 4 starts, Streamlit prints a **Local URL** (default
`http://localhost:8501`) -- open that in a browser to use the chatbot. Leave
the terminal window running; closing it stops the app.

> If port 8501 is already taken (you'll see `Port 8501 is not available`),
> run Streamlit directly on a different port instead:
> ```powershell
> $env:PYTHONPATH = "."
> .\.venv\Scripts\python.exe -m streamlit run chatbot\app.py --server.port 8531
> ```
> then open `http://localhost:8531`.

## 4. Explore the graph directly in Neo4j Browser

In Neo4j Desktop, click your DBMS -> **Open** (opens Neo4j Browser at
`http://localhost:7474`, already connected). Useful queries:

```cypher
// the ontology/schema itself, as a diagram
CALL db.schema.visualization()

// a sample of real data
MATCH (n) RETURN n LIMIT 50
```

More example queries are in `graph_load\verify_queries.cypher`.

## 5. Scale to the full 422,459-case dataset

Once you're happy with the sample results:

```powershell
.\scripts\run_full_pipeline.ps1
```

This parses all 3 XML files (~9 min) and reloads the full graph
(~30 min with the current batched loader). It does **not** relaunch
Streamlit automatically -- start it yourself afterward the same way as in
step 3 (either re-run `run_sample_pipeline.ps1`'s last line manually, or the
`streamlit run` command directly), and it will now be serving from the
full-scale graph instead of the sample.

## 6. Everyday restart (Neo4j/Streamlit already set up once)

Each time you come back to work on this (e.g., after a reboot or a new AVD
session):

```powershell
# 1. Start your DBMS in Neo4j Desktop (must show "Active")
# 2. Launch the chatbot against the already-loaded graph -- no need to
#    re-run ingestion/graph-load unless the data should change:
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe -m streamlit run chatbot\app.py --server.port 8531
```

## Tests

```powershell
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

## Troubleshooting

- **`Port 8501 is not available`**: something else is already using it --
  pass `--server.port <other-port>` to `streamlit run` (see step 3).
- **Neo4j connection errors** (`ServiceUnavailable`, `Unauthorized`): make
  sure the DBMS shows "Active" in Neo4j Desktop, and that `.env`'s
  `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD` match its connection details
  exactly.
- **Gemini `404 NOT_FOUND ... no longer available`**: the model name in
  `.env`'s `GEMINI_MODEL` has been deprecated; the error message names the
  current replacement -- update `.env` to that value.
- **`staging db not found` when running `graph_load.load_batched`**: run
  `ingestion.run_ingest` then `ingestion.staging_db` first (step 3's script
  does this in order automatically).
- Any `python -m ingestion...` / `python -m graph_load...` / `python -m
  chatbot...` command must be run with `$env:PYTHONPATH = "."` set first (the
  provided scripts already do this) and with `.\.venv\Scripts\python.exe`,
  not a bare `python`, so it uses the project's virtual environment.

## What the chatbot can answer

Report counts and top-N rankings for drugs/reactions, drug<->reaction
co-occurrence, demographic (age/sex) breakdowns, seriousness/outcome counts,
and count-based comparisons between two drugs. It explicitly refuses
incidence-rate, causality, cross-quarter-trend, and per-drug-to-per-reaction
causal-pairing questions -- FAERS spontaneous-report data cannot support
those. See PLAN.md section 7 for the full taxonomy.
