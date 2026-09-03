# Phases 1-4: parse a sample, stage it in DuckDB, load it into Neo4j, then launch the chatbot.
$env:PYTHONPATH = "."

.\.venv\Scripts\python.exe -m ingestion.run_ingest --mode sample --files 1 --max-cases 5000
.\.venv\Scripts\python.exe -m ingestion.staging_db --mode sample
.\.venv\Scripts\python.exe -m graph_load.load_batched --mode sample --reset
.\.venv\Scripts\python.exe -m streamlit run chatbot/app.py
