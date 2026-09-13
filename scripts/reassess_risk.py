"""
scripts/reassess_risk.py
-------------------------
Standalone tool to re-evaluate table risk flags across existing JSON output files.

Does NOT re-run Docling conversion or LLM metadata extraction.
Re-applies the current heuristic in pensieve.risk_flagger to the 'tables' array
of all generated JSON documents and updates risk_flag / risk_reasons in place.

Usage:
    python scripts/reassess_risk.py [--output-dir ./output] [--manifest ./manifest.csv]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from pensieve.config import DEFAULT_MANIFEST_PATH, DEFAULT_OUTPUT_DIR, JSON_INDENT
from pensieve.risk_flagger import assess_table_risk


def reassess_json_files(output_dir: Path, manifest_path: Path | None = None) -> None:
    """Re-evaluate risk flags for all JSON files in output_dir and print summary."""
    output_dir = Path(output_dir)
    json_files = sorted(output_dir.glob("*.json"))

    if not json_files:
        print(f"No JSON files found in {output_dir}")
        return

    print(f"Re-assessing table risk flags across {len(json_files)} file(s) in {output_dir} ...\n")

    overall_total = 0
    overall_before = 0
    overall_after = 0
    manifest_updates: dict[str, int] = {}  # doc_id -> new_flagged_count

    for jf in json_files:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            print(f"Error reading {jf.name}: {exc}", file=sys.stderr)
            continue

        tables = data.get("tables", [])
        total_tables = len(tables)
        if total_tables == 0:
            continue

        before_count = sum(1 for t in tables if t.get("risk_flag"))
        after_count = 0

        for t in tables:
            grid = t.get("grid", [])
            num_rows = t.get("rows", len(grid))
            num_cols = t.get("cols", max((len(r) for r in grid), default=0))

            risk_flag, risk_reasons = assess_table_risk(grid, num_rows, num_cols)
            t["risk_flag"] = risk_flag
            t["risk_reasons"] = risk_reasons
            if risk_flag:
                after_count += 1

        overall_total += total_tables
        overall_before += before_count
        overall_after += after_count

        doc_id = data.get("doc_id", jf.stem)
        manifest_updates[doc_id] = after_count

        # Write updated file back
        with open(jf, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=JSON_INDENT, ensure_ascii=False)

        before_pct = (before_count / total_tables) * 100 if total_tables else 0.0
        after_pct = (after_count / total_tables) * 100 if total_tables else 0.0
        diff = after_count - before_count

        print(f"File: {jf.name} (doc_id: {doc_id})")
        print(f"  Total tables:  {total_tables}")
        print(f"  Before:        {before_count:3d} flagged ({before_pct:5.1f}%)")
        print(f"  After:         {after_count:3d} flagged ({after_pct:5.1f}%)  [{diff:+d}]")
        print()

    # Update manifest.csv if present
    if manifest_path and Path(manifest_path).exists():
        _update_manifest(Path(manifest_path), manifest_updates)

    # Print overall summary table
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    b_pct = (overall_before / overall_total) * 100 if overall_total else 0.0
    a_pct = (overall_after / overall_total) * 100 if overall_total else 0.0
    reduction = overall_before - overall_after
    reduction_pct = (reduction / overall_before) * 100 if overall_before else 0.0

    print(f"Total tables evaluated:   {overall_total}")
    print(f"Previously flagged:       {overall_before:4d} ({b_pct:.1f}%)")
    print(f"Newly flagged:            {overall_after:4d} ({a_pct:.1f}%)")
    print(f"False positives removed:  {reduction:4d} (-{reduction_pct:.1f}% drop in flags)")
    print("=" * 60)


def _update_manifest(manifest_path: Path, updates: dict[str, int]) -> None:
    """Update tables_flagged column in manifest.csv."""
    try:
        rows: list[dict[str, str]] = []
        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            if not fieldnames:
                return
            for r in reader:
                doc_id = r.get("doc_id", "")
                if doc_id in updates:
                    r["tables_flagged"] = str(updates[doc_id])
                rows.append(r)

        with open(manifest_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Updated {manifest_path} with new table flag counts.")
    except Exception as exc:
        print(f"Note: Could not update manifest.csv: {exc}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-assess table risk flags across existing JSON output files."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory containing document JSON files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help=f"Manifest CSV path to sync (default: {DEFAULT_MANIFEST_PATH})",
    )
    args = parser.parse_args()
    reassess_json_files(args.output_dir, args.manifest)


if __name__ == "__main__":
    main()
