from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = REPO_ROOT / "faers_xml_2026q2"
XML_DIR = RAW_DATA_DIR / "XML"
DELETE_LIST_PATH = RAW_DATA_DIR / "Deleted" / "DELETE26Q2.txt"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"

    sample_dir: Path = REPO_ROOT / "data" / "sample"
    staging_dir: Path = REPO_ROOT / "data" / "staging"
    bulk_import_dir: Path = REPO_ROOT / "data" / "bulk_import"


settings = Settings()
