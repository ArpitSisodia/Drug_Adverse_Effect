python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Write-Host "Done. Copy .env.example to .env and fill in Neo4j + Gemini credentials before running the pipeline."
