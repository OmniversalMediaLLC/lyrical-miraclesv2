#!/usr/bin/env python3
"""Convert dist/manifest.json into SQL statements for Cloudflare D1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def q(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def rows_for_section(section: List[Dict[str, Any]], columns: List[str]) -> List[str]:
    statements: List[str] = []
    for entry in section:
        values = [q(entry.get(col)) for col in columns]
        statements.append(f"VALUES ({', '.join(values)})")
    return statements


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate D1 SQL from manifest")
    parser.add_argument("--manifest", type=Path, default=Path("dist/manifest.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    statements: List[str] = []

    sections = (
        ("content_assets", data.get("content", []), ["path", "release", "title", "type", "checksum"]),
        ("media_assets", data.get("media", []), ["path", "size", "checksum"]),
        ("catalog_assets", data.get("catalogs", []), ["path", "size"]),
    )

    for table, rows, cols in sections:
        statements.append(f"DELETE FROM {table};")
        if not rows:
            continue
        chunk: List[str] = []
        for entry in rows:
            chunk.append(f"INSERT INTO {table} ({', '.join(cols)}) {rows_for_section([entry], cols)[0]};")
        statements.extend(chunk)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(statements) + "\n", encoding="utf-8")

    print(f"[manifest_to_sql] Wrote SQL with {len(statements)} statements → {args.output}")


if __name__ == "__main__":
    main()
