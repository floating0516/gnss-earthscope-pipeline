#!/usr/bin/env python3
"""Validate completed PGD release starter annotations before import."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_RELEASE_DIR = Path("reports/pgd_magnitude/release/latest")
KEY_FIELDS = ["event_id", "formula"]
ALLOWED_MANUAL_STATUSES = {
    "",
    "UNREVIEWED",
    "REVIEWED",
    "ACCEPTED",
    "EXCLUDED",
    "NEEDS_DATA_CHECK",
    "NEEDS_METADATA_CHECK",
    "NEEDS_FORMULA_REVIEW",
}
TERMINAL_MANUAL_STATUSES = {"REVIEWED", "ACCEPTED", "EXCLUDED"}
INCOMPLETE_MANUAL_STATUSES = {"", "UNREVIEWED", "NEEDS_DATA_CHECK", "NEEDS_METADATA_CHECK", "NEEDS_FORMULA_REVIEW"}
TRUE_VALUES = {"1", "true", "yes", "y", "accepted"}
FALSE_VALUES = {"0", "false", "no", "n", "excluded"}

VALIDATION_FIELDS = [
    "event_id",
    "formula",
    "release_blocking",
    "validation_status",
    "manual_review_status",
    "accepted_for_release",
    "manual_review_cause",
    "reviewer",
    "reviewed_at",
    "error_codes",
    "error_messages",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE_DIR)
    parser.add_argument("--base-starter", type=Path, default=None)
    parser.add_argument("--completed-starter", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, default=None)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-md", type=Path, default=None)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def resolve_paths(args: argparse.Namespace) -> dict[str, Path]:
    release_dir = args.release_dir
    return {
        "release_dir": release_dir,
        "base_starter": args.base_starter or release_dir / "release_blocking_review_starter.csv",
        "completed_starter": args.completed_starter,
        "out_csv": args.out_csv or release_dir / "release_starter_validation.csv",
        "out_json": args.out_json or release_dir / "release_starter_validation.json",
        "out_md": args.out_md or release_dir / "release_starter_validation.md",
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def key(row: dict[str, str]) -> tuple[str, str]:
    return tuple(str(row.get(field) or "").strip() for field in KEY_FIELDS)  # type: ignore[return-value]


def is_yes(value: object) -> bool:
    return str(value or "").strip().lower() in {"yes", "true", "1", "y"}


def normalized_status(row: dict[str, str] | None) -> str:
    if row is None:
        return ""
    return str(row.get("manual_review_status") or "").strip().upper()


def normalized_accepted(row: dict[str, str] | None) -> str:
    if row is None:
        return ""
    value = str(row.get("accepted_for_release") or "").strip().lower()
    if value in TRUE_VALUES:
        return "yes"
    if value in FALSE_VALUES:
        return "no"
    return ""


def error(code: str, message: str, row: dict[str, str] | None = None, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"code": code, "message": message}
    if row is not None:
        row_key = key(row)
        payload.update({"event_id": row_key[0], "formula": row_key[1]})
    payload.update(extra)
    return payload


def row_errors(row: dict[str, str] | None) -> list[dict[str, object]]:
    if row is None:
        return [
            {
                "code": "INCOMPLETE_RELEASE_BLOCKING_DECISION",
                "message": "Release-blocking row has no completed starter decision.",
            }
        ]
    status = normalized_status(row)
    accepted = normalized_accepted(row)
    errors: list[dict[str, object]] = []
    if status not in ALLOWED_MANUAL_STATUSES:
        errors.append(error("UNKNOWN_MANUAL_STATUS", f"manual_review_status is not recognized: {status}", row))
        return errors
    if status in INCOMPLETE_MANUAL_STATUSES:
        errors.append(error("INCOMPLETE_RELEASE_BLOCKING_DECISION", "Release-blocking row does not have a terminal manual decision.", row))
        if accepted:
            errors.append(error("INCONSISTENT_ACCEPTED_FOR_RELEASE", "accepted_for_release is filled before a terminal manual decision.", row))
        return errors
    if status == "ACCEPTED" and accepted != "yes":
        errors.append(error("INCONSISTENT_ACCEPTED_FOR_RELEASE", "manual_review_status=ACCEPTED requires accepted_for_release=yes.", row))
    elif status == "EXCLUDED" and accepted != "no":
        errors.append(error("INCONSISTENT_ACCEPTED_FOR_RELEASE", "manual_review_status=EXCLUDED requires accepted_for_release=no.", row))
    elif status == "REVIEWED" and accepted not in {"yes", "no"}:
        errors.append(error("INCONSISTENT_ACCEPTED_FOR_RELEASE", "manual_review_status=REVIEWED requires accepted_for_release=yes or no.", row))
    return errors


def validation_row(base_row: dict[str, str], completed_row: dict[str, str] | None, errors: list[dict[str, object]]) -> dict[str, str]:
    source = completed_row or base_row
    if not completed_row:
        status = "MISSING"
    elif not errors and normalized_status(completed_row) in TERMINAL_MANUAL_STATUSES:
        status = "COMPLETE"
    elif any(item["code"] == "INCOMPLETE_RELEASE_BLOCKING_DECISION" for item in errors):
        status = "INCOMPLETE"
    else:
        status = "INVALID"
    return {
        "event_id": base_row.get("event_id", ""),
        "formula": base_row.get("formula", ""),
        "release_blocking": base_row.get("release_blocking", ""),
        "validation_status": status,
        "manual_review_status": normalized_status(completed_row),
        "accepted_for_release": normalized_accepted(completed_row),
        "manual_review_cause": source.get("manual_review_cause", ""),
        "reviewer": source.get("reviewer", ""),
        "reviewed_at": source.get("reviewed_at", ""),
        "error_codes": ";".join(str(item["code"]) for item in errors),
        "error_messages": ";".join(str(item["message"]) for item in errors),
    }


def unknown_validation_row(row: dict[str, str], errors: list[dict[str, object]]) -> dict[str, str]:
    return {
        "event_id": row.get("event_id", ""),
        "formula": row.get("formula", ""),
        "release_blocking": row.get("release_blocking", ""),
        "validation_status": "UNKNOWN_KEY",
        "manual_review_status": normalized_status(row),
        "accepted_for_release": normalized_accepted(row),
        "manual_review_cause": row.get("manual_review_cause", ""),
        "reviewer": row.get("reviewer", ""),
        "reviewed_at": row.get("reviewed_at", ""),
        "error_codes": ";".join(str(item["code"]) for item in errors),
        "error_messages": ";".join(str(item["message"]) for item in errors),
    }


def build_validation(
    paths: dict[str, Path],
    *,
    require_complete: bool,
    strict: bool,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    base_rows = [row for row in read_csv(paths["base_starter"]) if is_yes(row.get("release_blocking"))]
    completed_rows = read_csv(paths["completed_starter"])
    completed_by_key = {key(row): row for row in completed_rows}
    base_keys = {key(row) for row in base_rows}
    rows: list[dict[str, str]] = []
    errors: list[dict[str, object]] = []
    invalid_count = 0
    missing_decision_count = 0
    complete_decision_count = 0

    for base_row in base_rows:
        row_key = key(base_row)
        completed_row = completed_by_key.get(row_key)
        row_error_items = row_errors(completed_row)
        is_incomplete = any(item["code"] == "INCOMPLETE_RELEASE_BLOCKING_DECISION" for item in row_error_items)
        if is_incomplete:
            missing_decision_count += 1
            if require_complete:
                errors.extend({**item, "event_id": row_key[0], "formula": row_key[1]} for item in row_error_items)
        else:
            non_incomplete_errors = row_error_items
            if non_incomplete_errors:
                invalid_count += 1
                errors.extend(non_incomplete_errors)
            else:
                complete_decision_count += 1
        rows.append(validation_row(base_row, completed_row, row_error_items))

    unknown_key_count = 0
    for completed_row in completed_rows:
        row_key = key(completed_row)
        if row_key in base_keys:
            continue
        unknown_key_count += 1
        unknown_errors = [
            error(
                "UNKNOWN_STARTER_KEY",
                "Completed starter row does not match any release-blocking starter row.",
                completed_row,
            )
        ]
        if strict:
            errors.extend(unknown_errors)
        rows.append(unknown_validation_row(completed_row, unknown_errors if strict else []))

    completion_status = "COMPLETE" if missing_decision_count == 0 and invalid_count == 0 else "INCOMPLETE"
    validation_status_counts = Counter(row["validation_status"] for row in rows)
    payload = {
        "status": "INVALID" if errors else "OK",
        "completion_status": completion_status,
        "release_dir": str(paths["release_dir"]),
        "base_starter": str(paths["base_starter"]),
        "completed_starter": str(paths["completed_starter"]),
        "out_csv": str(paths["out_csv"]),
        "out_json": str(paths["out_json"]),
        "out_md": str(paths["out_md"]),
        "require_complete": require_complete,
        "strict": strict,
        "base_release_blocking_count": len(base_rows),
        "completed_starter_row_count": len(completed_rows),
        "complete_decision_count": complete_decision_count,
        "missing_decision_count": missing_decision_count,
        "invalid_count": invalid_count,
        "unknown_key_count": unknown_key_count,
        "validation_status_counts": {name: validation_status_counts[name] for name in sorted(validation_status_counts)},
        "errors": errors,
    }
    return rows, payload


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=VALIDATION_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in VALIDATION_FIELDS} for row in rows)


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def markdown_escape(value: object) -> str:
    return str(value if value is not None else "").replace("|", "\\|")


def markdown_table(rows: list[dict[str, object]], fields: list[str]) -> list[str]:
    lines = ["| " + " | ".join(fields) + " |", "|" + "|".join("---" for _field in fields) + "|"]
    if not rows:
        lines.append("| " + " | ".join("none" if index == 0 else "" for index, _field in enumerate(fields)) + " |")
        return lines
    for row in rows:
        lines.append("| " + " | ".join(markdown_escape(row.get(field, "")) for field in fields) + " |")
    return lines


def write_markdown(path: Path, payload: dict[str, Any], rows: list[dict[str, str]]) -> None:
    lines = [
        "# PGD Release Starter Validation",
        "",
        f"- Status: `{payload.get('status', '')}`",
        f"- Completion: `{payload.get('completion_status', '')}`",
        f"- Release-blocking base rows: {payload.get('base_release_blocking_count', 0)}",
        f"- Complete decisions: {payload.get('complete_decision_count', 0)}",
        f"- Missing decisions: {payload.get('missing_decision_count', 0)}",
        f"- Invalid decisions: {payload.get('invalid_count', 0)}",
        f"- Unknown keys: {payload.get('unknown_key_count', 0)}",
        "",
    ]
    errors = payload.get("errors") or []
    if errors:
        lines.extend(["## Errors", "", *markdown_table(errors, ["code", "event_id", "formula", "message"]), ""])
    lines.extend(
        [
            "## Rows",
            "",
            *markdown_table(rows, VALIDATION_FIELDS),
            "",
            "This report is read-only. It validates a completed starter before importing it with `run_pgd_science_bundle.py --starter-annotations`.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = resolve_paths(args)
    rows, payload = build_validation(paths, require_complete=args.require_complete, strict=args.strict)
    write_csv(paths["out_csv"], rows)
    write_json(paths["out_json"], payload)
    write_markdown(paths["out_md"], payload, rows)
    print(json.dumps({"status": payload["status"], "completion_status": payload["completion_status"], "missing_decision_count": payload["missing_decision_count"]}, sort_keys=True))
    return 1 if payload["status"] == "INVALID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
