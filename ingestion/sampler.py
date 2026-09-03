from pathlib import Path
from typing import Iterator

from ingestion.schema import ParsedCase
from ingestion.xml_stream_parser import iter_cases


def iter_cases_across_files(
    xml_paths: list[Path],
    delete_ids: set[str],
    max_cases_total: int | None = None,
    max_cases_per_file: int | None = None,
    max_bytes_per_file: int | None = None,
) -> Iterator[ParsedCase]:
    """Stream cases across multiple ADR*.xml files, stopping once max_cases_total is hit.

    Per-file limits (max_cases_per_file / max_bytes_per_file) bound how much of any
    single ~700MB file gets read during a sample run; max_cases_total bounds the
    combined output across all files given.
    """
    total = 0
    for path in xml_paths:
        if max_cases_total is not None and total >= max_cases_total:
            break
        remaining = None
        if max_cases_total is not None:
            remaining = max_cases_total - total
            if max_cases_per_file is not None:
                remaining = min(remaining, max_cases_per_file)
        else:
            remaining = max_cases_per_file

        for parsed in iter_cases(path, delete_ids=delete_ids, max_cases=remaining, max_bytes=max_bytes_per_file):
            yield parsed
            total += 1
            if max_cases_total is not None and total >= max_cases_total:
                break
