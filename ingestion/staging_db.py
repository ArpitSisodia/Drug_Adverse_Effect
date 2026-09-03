from pathlib import Path

import duckdb


def build_staging_db(parquet_root: Path, db_path: Path) -> None:
    """(Re)build a DuckDB file with cases / case_drugs / case_reactions tables
    from the Parquet parts written by run_ingest.py.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    con = duckdb.connect(str(db_path))
    for table in ("cases", "case_drugs", "case_reactions"):
        glob_path = str(parquet_root / table / "part-*.parquet")
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_parquet('{glob_path}')")
    con.close()


if __name__ == "__main__":
    import argparse

    from config.settings import settings

    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["sample", "full"], required=True)
    args = ap.parse_args()

    root = settings.sample_dir if args.mode == "sample" else settings.staging_dir
    db_file = root / ("faers_sample.duckdb" if args.mode == "sample" else "faers_staging.duckdb")
    build_staging_db(root, db_file)
    print(f"staging DB built at {db_file}")
