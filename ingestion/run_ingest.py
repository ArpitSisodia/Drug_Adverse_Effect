"""CLI to parse FAERS ADR*.xml files into staged Parquet tables.

Usage (from repo root, with .venv active / PYTHONPATH=.):
    python -m ingestion.run_ingest --mode sample --files 1 --max-cases 5000
    python -m ingestion.run_ingest --mode full --files 1,2,3
"""

import argparse
import dataclasses
import json
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from config.settings import DELETE_LIST_PATH, XML_DIR, settings
from ingestion.delete_list import load_delete_ids
from ingestion.sampler import iter_cases_across_files

BATCH_SIZE = 5000


def _file_path_for_index(i: int) -> Path:
    return XML_DIR / f"{i}_ADR26Q2.xml"


def _write_batch(rows: list[dict], out_dir: Path, part_idx: int) -> int:
    if not rows:
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, out_dir / f"part-{part_idx:05d}.parquet")
    return len(rows)


def run(mode: str, files: list[int], max_cases_total: int | None, max_cases_per_file: int | None) -> None:
    out_dir = settings.sample_dir if mode == "sample" else settings.staging_dir
    cases_dir = out_dir / "cases"
    drugs_dir = out_dir / "case_drugs"
    reactions_dir = out_dir / "case_reactions"
    for d in (cases_dir, drugs_dir, reactions_dir):
        if d.exists():
            for f in d.glob("part-*.parquet"):
                f.unlink()

    delete_ids = load_delete_ids(DELETE_LIST_PATH)
    xml_paths = [_file_path_for_index(i) for i in files]
    for p in xml_paths:
        if not p.exists():
            raise FileNotFoundError(p)

    started = time.time()
    case_rows, drug_rows, reaction_rows = [], [], []
    part_idx = 0
    kept = 0
    delete_matches = 0
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()

    source = iter_cases_across_files(
        xml_paths,
        delete_ids=delete_ids,
        max_cases_total=max_cases_total,
        max_cases_per_file=max_cases_per_file,
    )

    for parsed in source:
        case_id = parsed.case.safetyreportid
        if case_id in seen_ids:
            duplicate_ids.add(case_id)
        seen_ids.add(case_id)

        case_rows.append(dataclasses.asdict(parsed.case))
        drug_rows.extend(dataclasses.asdict(d) for d in parsed.drugs)
        reaction_rows.extend(dataclasses.asdict(r) for r in parsed.reactions)
        kept += 1

        if len(case_rows) >= BATCH_SIZE:
            _write_batch(case_rows, cases_dir, part_idx)
            _write_batch(drug_rows, drugs_dir, part_idx)
            _write_batch(reaction_rows, reactions_dir, part_idx)
            case_rows, drug_rows, reaction_rows = [], [], []
            part_idx += 1
            print(f"...{kept} cases processed")

    # flush remainder (also handles the all-empty edge case for drugs/reactions safely)
    if case_rows:
        _write_batch(case_rows, cases_dir, part_idx)
        _write_batch(drug_rows, drugs_dir, part_idx)
        _write_batch(reaction_rows, reactions_dir, part_idx)

    elapsed = time.time() - started
    manifest = {
        "mode": mode,
        "files_processed": [p.name for p in xml_paths],
        "delete_ids_loaded": len(delete_ids),
        "cases_kept": kept,
        "duplicate_case_ids_seen": len(duplicate_ids),
        "duplicate_case_id_examples": sorted(duplicate_ids)[:20],
        "elapsed_seconds": round(elapsed, 1),
        "max_cases_total": max_cases_total,
        "max_cases_per_file": max_cases_per_file,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["sample", "full"], required=True)
    ap.add_argument("--files", default="1,2,3", help="comma-separated file indices, e.g. 1,2,3")
    ap.add_argument("--max-cases", type=int, default=None, help="global cap across all files (sample mode)")
    ap.add_argument("--max-cases-per-file", type=int, default=None)
    args = ap.parse_args()

    files = [int(x) for x in args.files.split(",") if x.strip()]
    run(mode=args.mode, files=files, max_cases_total=args.max_cases, max_cases_per_file=args.max_cases_per_file)


if __name__ == "__main__":
    main()
