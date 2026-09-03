# Phases 6-7: parse all 422,459 cases and reload the graph at full scale.
# Run scripts\setup_env.ps1 and fill in .env first if you haven't already.
$env:PYTHONPATH = "."

.\.venv\Scripts\python.exe -m ingestion.run_ingest --mode full --files 1,2,3
.\.venv\Scripts\python.exe -m ingestion.staging_db --mode full
.\.venv\Scripts\python.exe -m graph_load.load_batched --mode full --reset
