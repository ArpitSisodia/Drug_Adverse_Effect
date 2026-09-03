from pathlib import Path


def load_delete_ids(path: Path) -> set[str]:
    """Load the FAERS DELETE*.txt case-id exclusion list.

    File is one bare numeric safetyreportid per line (a leading blank line
    is common in FDA's export). Returns an empty set if the file is missing.
    """
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and line.isdigit():
            ids.add(line)
    return ids
