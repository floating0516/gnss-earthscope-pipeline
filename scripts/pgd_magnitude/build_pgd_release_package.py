#!/usr/bin/env python3
"""Build a compact PGD release package from generated PGD science products."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import evaluate_pgd_magnitude as pgd
import pgd_contract


DEFAULT_REPORT_DIR = Path("reports/pgd_magnitude/latest")
DEFAULT_SENSITIVITY_DIR = Path("reports/pgd_magnitude/sensitivity/latest")
DEFAULT_OUT_DIR = Path("reports/pgd_magnitude/release/latest")
STATION_AGGREGATION = pgd_contract.STATION_AGGREGATION_METHOD
LEGACY_FORMULA_NOTE = "formula_method_note.md"
FORMULA_AGGREGATION_NOTE = "formula_aggregation_note.md"

PACKAGE_MANIFEST_FIELDS = ["product", "path", "source_path", "role", "row_count"]
TRIAGE_TOP_FIELDS = ["event_id", "formula", "abs_residual_mw", "triage_status_suggestion", "triage_cause_suggestion"]
RESIDUAL_EVIDENCE_FIELDS = [
    "triage_priority",
    "event_id",
    "formula",
    "review_status",
    "abs_residual_mw",
    "pgd_reliability",
    "usable_station_count",
    "median_pgd_snr",
    "median_distance_km",
    "triage_status_suggestion",
    "triage_cause_suggestion",
    "triage_reason",
    "next_review_action",
    "best_formula_for_event",
    "best_formula_abs_residual_mw",
    "formula_residuals_for_event",
    "formula_limitation_suggested",
    "release_status",
    "release_failure_reasons",
    "release_review_reasons",
]
MANUAL_REVIEW_FIELDS = [
    "manual_review_status",
    "manual_review_cause",
    "manual_review_notes",
    "accepted_for_release",
    "reviewer",
    "reviewed_at",
]
RESIDUAL_ANNOTATION_STARTER_FIELDS = RESIDUAL_EVIDENCE_FIELDS + MANUAL_REVIEW_FIELDS
RESIDUAL_PACKET_INDEX_FIELDS = [
    "triage_priority",
    "event_id",
    "formula",
    "packet_path",
    "triage_status_suggestion",
    "triage_cause_suggestion",
    "next_review_action",
    "abs_residual_mw",
    "release_status",
    "manual_review_status",
]
DATA_DICTIONARY_FIELDS = ["product", "field", "description", "unit", "allowed_values", "notes"]
FORMULAS = [law.name for law in pgd.SCALING_LAWS]
FORMULA_COEFFICIENT_FIELDS = [
    "formula",
    "coefficient_a",
    "coefficient_b",
    "coefficient_c",
    "pgd_unit",
    "distance_unit",
    "equation",
    "inverted_equation",
    "citation_key",
    "citation",
    "doi",
    "source_url",
]
FORMULA_REFERENCE_METADATA = {
    "melgar_2015": {
        "citation_key": "Melgar et al. (2015)",
        "citation": "Melgar et al. (2015), Reliable earthquake magnitude estimation from high-rate GPS data.",
        "doi": "10.1002/2015GL064568",
        "source_url": "https://doi.org/10.1002/2015GL064568",
    },
    "crowell_2016_gfast": {
        "citation_key": "Crowell et al. (2016)",
        "citation": "Crowell et al. (2016), Demonstration of the Cascadia G-FAST geodetic earthquake early warning system.",
        "doi": "10.1785/0120150255",
        "source_url": "https://doi.org/10.1785/0120150255",
    },
    "ruhl_2019": {
        "citation_key": "Ruhl et al. (2019)",
        "citation": "Ruhl et al. (2019), A global database of strong-motion displacement GNSS recordings and an example application to PGD scaling.",
        "doi": "10.1785/0220180177",
        "source_url": "https://doi.org/10.1785/0220180177",
    },
}

FIELD_DEFINITIONS = {
    "event_id": ("Normalized event identifier.", "", "", ""),
    "event_time": ("Event origin time in UTC.", "UTC timestamp", "", ""),
    "country": ("Country bucket used by the PGD report.", "", "", ""),
    "region": ("Region label used by the PGD report.", "", "", ""),
    "place": ("Human-readable event location label.", "", "", ""),
    "formula": ("PGD scaling formula used for the row.", "", "|".join(FORMULAS), ""),
    "usgs_magnitude": ("Reference USGS moment magnitude where available.", "Mw", "", ""),
    "estimated_mw_median": ("Event magnitude estimate from median station aggregation.", "Mw", "", "Uses the single PGD station aggregation method: median."),
    "residual_mw": ("Estimated magnitude minus reference magnitude.", "Mw", "", ""),
    "abs_residual_mw": ("Absolute magnitude residual.", "Mw", "", ""),
    "pgd_reliability": ("Event-level PGD reliability class.", "", "HIGH|MEDIUM|LOW", ""),
    "usable_station_count": ("Number of stations used by the event-level PGD estimate.", "stations", "", ""),
    "median_pgd_snr": ("Median station PGD signal-to-noise ratio.", "ratio", "", ""),
    "median_distance_km": ("Median event-station distance for usable stations.", "km", "", ""),
    "release_status": ("Release gate status for the event.", "", "INCLUDED_RELEASE_SET|NEEDS_RESIDUAL_REVIEW|EXCLUDED_RELEASE_SET", ""),
    "comparison_group": ("Grouping dimension for a formula comparison row.", "", "", ""),
    "comparison_value": ("Value within the comparison group.", "", "", ""),
    "station_aggregation": ("Station aggregation method.", "", STATION_AGGREGATION, "Fixed to median; mean and trimmed-mean are not PGD release methods."),
    "event_count": ("Number of events included in the metric row.", "events", "", ""),
    "high_medium_reliability_events": ("Count of HIGH or MEDIUM PGD reliability events.", "events", "", ""),
    "low_reliability_events": ("Count of LOW PGD reliability events.", "events", "", ""),
    "residual_outlier_count": ("Count of rows exceeding the residual review threshold.", "events", "", ""),
    "bias_mw": ("Mean signed magnitude residual.", "Mw", "", ""),
    "mae_mw": ("Mean absolute magnitude error.", "Mw", "", ""),
    "rmse_mw": ("Root mean square magnitude error.", "Mw", "", ""),
    "median_abs_error_mw": ("Median absolute magnitude error.", "Mw", "", ""),
    "scenario_id": ("Sensitivity scenario identifier.", "", "", ""),
    "scenario_label": ("Human-readable sensitivity scenario label.", "", "", ""),
    "pgd_component": ("PGD component used by the sensitivity scenario.", "", "3d|horizontal", ""),
    "distance_mode": ("Distance metric used by the sensitivity scenario.", "", "hypocentral|epicentral", ""),
    "calibration": ("Calibration mode used by the sensitivity scenario.", "", "none|leave-one-out-country-linear", ""),
    "recommended_formula": ("Formula recommended under the scenario or report.", "", "|".join(FORMULAS), ""),
    "criterion": ("Recommendation criterion.", "", "", ""),
    "matches_baseline": ("Whether the scenario recommendation matches the baseline recommendation.", "", "yes|no", ""),
    "triage_status_suggestion": ("Automatic residual-review status suggestion.", "", "", ""),
    "triage_cause_suggestion": ("Automatic residual-review cause suggestion.", "", "", ""),
    "triage_priority": ("Residual review queue priority; lower numbers are reviewed first.", "", "", ""),
    "review_status": ("Manual residual-review status copied from the annotated review queue.", "", "", ""),
    "triage_reason": ("Machine-generated explanation for the residual-review suggestion.", "", "", ""),
    "next_review_action": ("Suggested next manual review action.", "", "", ""),
    "best_formula_for_event": ("Formula with the lowest absolute residual for the same event.", "", "|".join(FORMULAS), ""),
    "best_formula_abs_residual_mw": ("Lowest absolute residual among formulas for the same event.", "Mw", "", ""),
    "formula_residuals_for_event": ("Semicolon-separated formula residual context for the same event.", "Mw", "", ""),
    "formula_limitation_suggested": ("Whether formula choice appears to contribute to the residual.", "", "yes|no", ""),
    "release_failure_reasons": ("Hard release-gate failure reasons copied from the release set.", "", "", ""),
    "release_review_reasons": ("Release-gate review reasons copied from the release set.", "", "", ""),
    "manual_review_status": ("Manual reviewer status to fill in after inspecting the evidence row.", "", "UNREVIEWED|REVIEWED|ACCEPTED|EXCLUDED|NEEDS_DATA_CHECK|NEEDS_METADATA_CHECK|NEEDS_FORMULA_REVIEW", "Blank in the starter file."),
    "manual_review_cause": ("Manual reviewer cause or category.", "", "", "Blank in the starter file."),
    "manual_review_notes": ("Free-text notes from the reviewer.", "", "", "Blank in the starter file."),
    "accepted_for_release": ("Manual yes/no release decision for the row or event after review.", "", "yes|no", "Blank in the starter file."),
    "reviewer": ("Reviewer name, initials, or identifier.", "", "", "Blank in the starter file."),
    "reviewed_at": ("Review completion time.", "UTC timestamp", "", "Blank in the starter file."),
    "packet_path": ("Relative path to a per-row residual review packet Markdown file.", "", "", ""),
    "figure_type": ("Figure type identifier.", "", "", ""),
    "path": ("Path to a release package product or referenced figure.", "", "", ""),
    "role": ("Role of the product or figure in the release package.", "", "", ""),
    "product": ("Release package product name.", "", "", ""),
    "source_path": ("Source product used to build the release product.", "", "", ""),
    "row_count": ("Number of data rows in the product.", "rows", "", ""),
    "coefficient_a": ("Intercept coefficient in log10(PGD) = a + b*Mw + c*Mw*log10(R).", "", "", ""),
    "coefficient_b": ("Magnitude coefficient in the PGD scaling equation.", "", "", ""),
    "coefficient_c": ("Magnitude-distance interaction coefficient in the PGD scaling equation.", "", "", ""),
    "pgd_unit": ("PGD unit expected by the formula before estimating Mw.", "", "m|cm", ""),
    "distance_unit": ("Distance unit used for R in the formula.", "", "km", ""),
    "equation": ("Forward PGD scaling equation.", "", "", ""),
    "inverted_equation": ("Magnitude equation used by the evaluator.", "", "", ""),
    "citation_key": ("Short reference label for the formula.", "", "", ""),
    "citation": ("Human-readable reference label for the formula.", "", "", ""),
    "doi": ("Digital Object Identifier for the formula reference where available.", "", "", ""),
    "source_url": ("Reference URL for the formula provenance.", "", "", ""),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR, help="PGD latest report directory.")
    parser.add_argument("--sensitivity-dir", type=Path, default=DEFAULT_SENSITIVITY_DIR, help="PGD sensitivity report directory.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output release package directory.")
    return parser.parse_args(argv)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


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


def field_definition(field: str) -> tuple[str, str, str, str]:
    return FIELD_DEFINITIONS.get(field, ("Field copied from the source PGD product.", "", "", ""))


def required_inputs(report_dir: Path, sensitivity_dir: Path) -> dict[str, Path]:
    return {
        "report_summary": report_dir / "summary.json",
        "release_events": report_dir / "science_release_events.csv",
        "formula_comparison": report_dir / "science_formula_summary.csv",
        "figure_manifest": report_dir / "science_figure_manifest.csv",
        "interpretation": report_dir / "pgd_interpretation.json",
        "residual_triage_summary": report_dir / "residual_review_triage_summary.json",
        "residual_triage": report_dir / "residual_review_triage.csv",
        "bundle_summary": report_dir / "pgd_science_bundle_summary.json",
        "sensitivity_summary": sensitivity_dir / "summary.json",
        "sensitivity_recommendations": sensitivity_dir / "sensitivity_recommendations.csv",
    }


def missing_inputs(inputs: dict[str, Path]) -> list[dict[str, str]]:
    return [
        {"code": "MISSING_INPUT", "message": f"Missing required PGD release input: {name}", "path": str(path)}
        for name, path in inputs.items()
        if not path.exists()
    ]


def int_value(value: object) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def top_triage_rows(summary: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for row in list(summary.get("top_priority_rows") or []):
        rows.append({field: str(row.get(field, "")) for field in TRIAGE_TOP_FIELDS})
    return rows


def count_by(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "").strip()
        if key:
            counts[key] = counts.get(key, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def residual_evidence_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output = [{field: str(row.get(field, "")) for field in RESIDUAL_EVIDENCE_FIELDS} for row in rows]
    return sorted(output, key=lambda row: (int_value(row.get("triage_priority")) or 10**9, row.get("event_id", ""), row.get("formula", "")))


def residual_evidence_payload(rows: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema_version": "pgd-residual-review-evidence/v1",
        "row_count": len(rows),
        "suggested_status_counts": count_by(rows, "triage_status_suggestion"),
        "suggested_cause_counts": count_by(rows, "triage_cause_suggestion"),
        "release_status_counts": count_by(rows, "release_status"),
        "rows": rows,
    }


def write_residual_evidence_markdown(path: Path, payload: dict[str, Any]) -> None:
    rows = list(payload.get("rows") or [])
    lines = [
        "# PGD Residual Review Evidence",
        "",
        f"- Rows: {payload.get('row_count', 0)}",
        f"- Suggested statuses: {json.dumps(payload.get('suggested_status_counts', {}), sort_keys=True)}",
        f"- Suggested causes: {json.dumps(payload.get('suggested_cause_counts', {}), sort_keys=True)}",
        f"- Release statuses: {json.dumps(payload.get('release_status_counts', {}), sort_keys=True)}",
        "",
        "These rows are review evidence, not final manual scientific decisions.",
        "",
        *markdown_table(rows, RESIDUAL_EVIDENCE_FIELDS),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def residual_annotation_starter_rows(evidence_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in evidence_rows:
        starter_row = {field: row.get(field, "") for field in RESIDUAL_EVIDENCE_FIELDS}
        starter_row.update({field: "" for field in MANUAL_REVIEW_FIELDS})
        rows.append(starter_row)
    return rows


def safe_slug(value: str) -> str:
    chars = []
    for char in value:
        if char.isalnum() or char in {"_", "-", "."}:
            chars.append(char)
        else:
            chars.append("-")
    slug = "".join(chars).strip("-")
    return slug or "unknown"


def residual_packet_filename(row: dict[str, str], index: int) -> str:
    event_id = safe_slug(row.get("event_id", ""))
    formula = safe_slug(row.get("formula", ""))
    return f"{index:03d}-{event_id}-{formula}.md"


def residual_packet_index_rows(evidence_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, row in enumerate(evidence_rows, start=1):
        packet_path = f"residual_review_packets/{residual_packet_filename(row, index)}"
        rows.append(
            {
                "triage_priority": row.get("triage_priority", ""),
                "event_id": row.get("event_id", ""),
                "formula": row.get("formula", ""),
                "packet_path": packet_path,
                "triage_status_suggestion": row.get("triage_status_suggestion", ""),
                "triage_cause_suggestion": row.get("triage_cause_suggestion", ""),
                "next_review_action": row.get("next_review_action", ""),
                "abs_residual_mw": row.get("abs_residual_mw", ""),
                "release_status": row.get("release_status", ""),
                "manual_review_status": "",
            }
        )
    return rows


def write_residual_annotation_starter_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    preview_fields = [
        "triage_priority",
        "event_id",
        "formula",
        "triage_status_suggestion",
        "triage_cause_suggestion",
        "next_review_action",
        "manual_review_status",
        "accepted_for_release",
        "reviewer",
        "reviewed_at",
    ]
    lines = [
        "# PGD Residual Review Annotation Starter",
        "",
        f"- Rows: {len(rows)}",
        f"- Manual fields: {', '.join(f'`{field}`' for field in MANUAL_REVIEW_FIELDS)}",
        "",
        "Manual fields are intentionally blank. Fill them after reviewing the machine evidence, then merge the completed CSV through the residual review annotation workflow.",
        "",
        *markdown_table(rows, preview_fields),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_residual_packet_index_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        "# PGD Residual Review Packet Index",
        "",
        f"- Packets: {len(rows)}",
        "- Each packet is a one-row review brief derived from residual review evidence.",
        "- Manual decisions should still be recorded in `residual_review_annotations_starter.csv` or a copy of it.",
        "",
        *markdown_table(rows, RESIDUAL_PACKET_INDEX_FIELDS),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def residual_packet_markdown(row: dict[str, str]) -> str:
    event_id = row.get("event_id", "")
    formula = row.get("formula", "")
    lines = [
        f"# PGD Residual Review Packet: {event_id} / {formula}",
        "",
        "## Identity",
        "",
        f"- Event ID: `{event_id}`",
        f"- Formula: `{formula}`",
        f"- Triage priority: `{row.get('triage_priority', '')}`",
        "",
        "## Residual Context",
        "",
        f"- Abs residual Mw: `{row.get('abs_residual_mw', '')}`",
        f"- PGD reliability: `{row.get('pgd_reliability', '')}`",
        f"- Usable station count: `{row.get('usable_station_count', '')}`",
        f"- Median PGD SNR: `{row.get('median_pgd_snr', '')}`",
        f"- Median distance km: `{row.get('median_distance_km', '')}`",
        "",
        "## Triage Suggestion",
        "",
        f"- Suggested status: `{row.get('triage_status_suggestion', '')}`",
        f"- Suggested cause: `{row.get('triage_cause_suggestion', '')}`",
        f"- Reason: {row.get('triage_reason', '')}",
        f"- Next review action: `{row.get('next_review_action', '')}`",
        "",
        "## Formula Context",
        "",
        f"- Best formula for event: `{row.get('best_formula_for_event', '')}`",
        f"- Best formula abs residual Mw: `{row.get('best_formula_abs_residual_mw', '')}`",
        f"- Formula residuals for event: `{row.get('formula_residuals_for_event', '')}`",
        f"- Formula limitation suggested: `{row.get('formula_limitation_suggested', '')}`",
        "",
        "## Release Gate Context",
        "",
        f"- Release status: `{row.get('release_status', '')}`",
        f"- Release failure reasons: `{row.get('release_failure_reasons', '')}`",
        f"- Release review reasons: `{row.get('release_review_reasons', '')}`",
        "",
        "## Manual Review Fields",
        "",
        "- `manual_review_status`: ",
        "- `manual_review_cause`: ",
        "- `manual_review_notes`: ",
        "- `accepted_for_release`: ",
        "- `reviewer`: ",
        "- `reviewed_at`: ",
        "",
        "Record final decisions in `residual_review_annotations_starter.csv` or a reviewed copy, then merge with `manage_residual_review.py --starter-annotations`.",
        "",
    ]
    return "\n".join(lines)


def write_residual_review_packets(packet_dir: Path, evidence_rows: list[dict[str, str]]) -> None:
    if packet_dir.exists():
        shutil.rmtree(packet_dir)
    packet_dir.mkdir(parents=True, exist_ok=True)
    for index, row in enumerate(evidence_rows, start=1):
        packet_path = packet_dir / residual_packet_filename(row, index)
        packet_path.write_text(residual_packet_markdown(row), encoding="utf-8")


def write_residual_review_checklist(path: Path, row_count: int) -> None:
    lines = [
        "# PGD Residual Review Checklist",
        "",
        f"- Starter rows: {row_count}",
        "- Manual fields are intentionally blank in `residual_review_annotations_starter.csv`.",
        "- Use the machine fields as review context, not as final scientific decisions.",
        "",
        "## Per-row Checks",
        "",
        "- Confirm the event and formula identifiers match the row being reviewed.",
        "- Inspect `triage_status_suggestion`, `triage_cause_suggestion`, `triage_reason`, and `next_review_action`.",
        "- For `NEEDS_DATA_CHECK`, inspect usable station count, SNR, distance, waveform quality, and release-gate failure reasons.",
        "- For `NEEDS_FORMULA_REVIEW`, compare `best_formula_for_event`, `best_formula_abs_residual_mw`, and `formula_residuals_for_event`.",
        "- Decide whether the row should be accepted, excluded, or sent to another review category.",
        "- Fill `manual_review_status`, `manual_review_cause`, `manual_review_notes`, `accepted_for_release`, `reviewer`, and `reviewed_at`.",
        "",
        "## Manual Status Values",
        "",
        "- `REVIEWED`: evidence inspected, no stronger status needed.",
        "- `ACCEPTED`: row/event accepted for release use after review.",
        "- `EXCLUDED`: row/event excluded after review.",
        "- `NEEDS_DATA_CHECK`: unresolved waveform, station, SNR, distance, or release-gate concern.",
        "- `NEEDS_METADATA_CHECK`: unresolved event or station metadata concern.",
        "- `NEEDS_FORMULA_REVIEW`: unresolved formula behavior concern.",
        "",
        "## Handoff",
        "",
        "Keep `residual_review_evidence.csv` unchanged. Put manual decisions in the starter CSV copy and merge them with `manage_residual_review.py --starter-annotations <completed-starter.csv> --strict`.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_data_dictionary(product_fields: dict[str, list[str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for product, fields in product_fields.items():
        for field in fields:
            description, unit, allowed_values, notes = field_definition(field)
            rows.append(
                {
                    "product": product,
                    "field": field,
                    "description": description,
                    "unit": unit,
                    "allowed_values": allowed_values,
                    "notes": notes,
                }
            )
    return rows


def fmt_number(value: float) -> str:
    return f"{value:.6g}"


def formula_coefficient_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    equation = "log10(PGD) = a + b*Mw + c*Mw*log10(R)"
    inverted = "Mw = (log10(PGD) - a) / (b + c * log10(R))"
    for law in pgd.SCALING_LAWS:
        reference = FORMULA_REFERENCE_METADATA.get(law.name, {})
        rows.append(
            {
                "formula": law.name,
                "coefficient_a": fmt_number(law.a),
                "coefficient_b": fmt_number(law.b),
                "coefficient_c": fmt_number(law.c),
                "pgd_unit": law.pgd_unit,
                "distance_unit": "km",
                "equation": equation,
                "inverted_equation": inverted,
                "citation_key": str(reference.get("citation_key", "")),
                "citation": str(reference.get("citation", "")),
                "doi": str(reference.get("doi", "")),
                "source_url": str(reference.get("source_url", "")),
            }
        )
    return rows


def write_formula_coefficients_json(path: Path, rows: list[dict[str, str]]) -> None:
    payload = {
        "schema_version": "pgd-formula-provenance/v1",
        "station_aggregation": STATION_AGGREGATION,
        "formula_count": len(rows),
        "formulas": rows,
    }
    write_json(path, payload)


def write_formula_provenance_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        "# PGD Formula Provenance",
        "",
        f"- Station aggregation method: `{STATION_AGGREGATION}`",
        "- Distance unit: `km`",
        "- Forward equation: `log10(PGD) = a + b*Mw + c*Mw*log10(R)`",
        "- Inverted evaluator equation: `Mw = (log10(PGD) - a) / (b + c * log10(R))`",
        "",
        "The formulas below are PGD scaling formulas. They are not station aggregation methods.",
        "",
        *markdown_table(rows, FORMULA_COEFFICIENT_FIELDS),
        "",
        "The coefficient values are read from `evaluate_pgd_magnitude.py` at package-build time so the release documentation stays aligned with the evaluator.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_data_dictionary_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        "# PGD Release Data Dictionary",
        "",
        "This dictionary documents the compact PGD release package products. The PGD station aggregation method is fixed to `median`.",
        "",
    ]
    products = sorted({row["product"] for row in rows})
    for product in products:
        product_rows = [row for row in rows if row["product"] == product]
        lines.extend([f"## {product}", "", *markdown_table(product_rows, DATA_DICTIONARY_FIELDS[1:]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_formula_aggregation_note(path: Path, payload: dict[str, Any], formula_rows: list[dict[str, str]], sensitivity_rows: list[dict[str, str]]) -> None:
    observed_formulas = sorted({row.get("formula", "") for row in formula_rows if row.get("formula")})
    sensitivity_formulas = sorted({row.get("recommended_formula", "") for row in sensitivity_rows if row.get("recommended_formula")})
    caveat = "required" if payload.get("requires_sensitivity_caveat") else "not required"
    lines = [
        "# PGD Formula And Aggregation Note",
        "",
        f"- Station aggregation method: `{STATION_AGGREGATION}`",
        f"- Recommended baseline formula: `{payload.get('recommended_formula', '')}`",
        f"- Sensitivity caveat: `{caveat}`",
        "",
        "## Aggregation Scope",
        "",
        "The PGD release uses one event-level station aggregation method: the median of usable station-level magnitude estimates. Mean and trimmed-mean aggregation are not release methods in this package.",
        "",
        "## Formula Scope",
        "",
        "The three compared PGD formulas are not station aggregation methods:",
        "",
        *[f"- `{formula}`" for formula in FORMULAS],
        "",
        f"Observed formulas in `formula_comparison.csv`: {', '.join(f'`{formula}`' for formula in observed_formulas) or 'none'}.",
        f"Recommended formulas appearing in sensitivity scenarios: {', '.join(f'`{formula}`' for formula in sensitivity_formulas) or 'none'}.",
        "",
        "## Interpretation",
        "",
        "The baseline recommendation is selected from formula residual metrics under median station aggregation. Sensitivity rows vary PGD component, distance mode, or calibration while keeping station aggregation fixed to median.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def station_aggregation_error(path: Path, field: str, value: object) -> dict[str, str] | None:
    text = str(value or "").strip()
    if text == STATION_AGGREGATION:
        return None
    code = "MISSING_STATION_AGGREGATION" if not text else "NON_MEDIAN_STATION_AGGREGATION"
    return {
        "code": code,
        "message": f"PGD release products must use station_aggregation={STATION_AGGREGATION}.",
        "path": str(path),
        "field": field,
        "value": text,
    }


def station_aggregation_errors(
    inputs: dict[str, Path],
    report_summary: dict[str, Any],
    interpretation: dict[str, Any],
    formula_rows: list[dict[str, str]],
    sensitivity_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    checks = [
        (
            inputs["report_summary"],
            "formula_recommendation.station_aggregation",
            dict(report_summary.get("formula_recommendation") or {}).get("station_aggregation"),
        ),
        (
            inputs["interpretation"],
            "baseline.station_aggregation",
            dict(interpretation.get("baseline") or {}).get("station_aggregation"),
        ),
    ]
    for path, field, value in checks:
        error = station_aggregation_error(path, field, value)
        if error:
            errors.append(error)

    for index, row in enumerate(formula_rows, start=2):
        error = station_aggregation_error(inputs["formula_comparison"], f"row_{index}.station_aggregation", row.get("station_aggregation"))
        if error:
            errors.append(error)
    for index, row in enumerate(sensitivity_rows, start=2):
        error = station_aggregation_error(inputs["sensitivity_recommendations"], f"row_{index}.station_aggregation", row.get("station_aggregation"))
        if error:
            errors.append(error)
    return errors


def build_package(args: argparse.Namespace) -> dict[str, Any]:
    inputs = required_inputs(args.report_dir, args.sensitivity_dir)
    errors = missing_inputs(inputs)
    output_summary = args.out_dir / "release_package_summary.json"
    output_md = args.out_dir / "release_package.md"
    if errors:
        payload = {
            "status": "INVALID",
            "report_dir": str(args.report_dir),
            "sensitivity_dir": str(args.sensitivity_dir),
            "out_dir": str(args.out_dir),
            "ready_event_count": 0,
            "errors": errors,
        }
        write_json(output_summary, payload)
        write_markdown(output_md, payload, [], [], [], [], [])
        return payload

    report_summary = read_json(inputs["report_summary"])
    interpretation = read_json(inputs["interpretation"])
    residual_triage = read_json(inputs["residual_triage_summary"])
    bundle_summary = read_json(inputs["bundle_summary"])
    sensitivity_summary = read_json(inputs["sensitivity_summary"])
    release_events, release_fields = read_csv(inputs["release_events"])
    formula_rows, formula_fields = read_csv(inputs["formula_comparison"])
    figure_rows, figure_fields = read_csv(inputs["figure_manifest"])
    sensitivity_rows, sensitivity_fields = read_csv(inputs["sensitivity_recommendations"])
    residual_triage_rows, residual_triage_fields = read_csv(inputs["residual_triage"])
    triage_rows = top_triage_rows(residual_triage)
    errors.extend(station_aggregation_errors(inputs, report_summary, interpretation, formula_rows, sensitivity_rows))

    recommendation = dict(report_summary.get("formula_recommendation") or {})
    interpretation_flags = dict(interpretation.get("interpretation_flags") or {})
    sensitivity = dict(interpretation.get("sensitivity") or {})
    switch_scenarios = list(sensitivity.get("formula_switch_scenarios") or [])
    ready_event_count = len(release_events)
    status = "OK" if ready_event_count > 0 else "NO_READY_EVENTS"

    outputs = {
        "summary": str(output_summary),
        "markdown": str(output_md),
        "release_events": str(args.out_dir / "release_events.csv"),
        "formula_comparison": str(args.out_dir / "formula_comparison.csv"),
        "sensitivity_recommendations": str(args.out_dir / "sensitivity_recommendations.csv"),
        "residual_triage_top": str(args.out_dir / "residual_triage_top.csv"),
        "residual_review_evidence": str(args.out_dir / "residual_review_evidence.csv"),
        "residual_review_evidence_json": str(args.out_dir / "residual_review_evidence.json"),
        "residual_review_evidence_md": str(args.out_dir / "residual_review_evidence.md"),
        "residual_review_annotations_starter": str(args.out_dir / "residual_review_annotations_starter.csv"),
        "residual_review_annotations_starter_md": str(args.out_dir / "residual_review_annotations_starter.md"),
        "residual_review_checklist": str(args.out_dir / "residual_review_checklist.md"),
        "residual_review_packet_index": str(args.out_dir / "residual_review_packet_index.csv"),
        "residual_review_packet_index_md": str(args.out_dir / "residual_review_packet_index.md"),
        "residual_review_packets_dir": str(args.out_dir / "residual_review_packets"),
        "figure_manifest": str(args.out_dir / "figure_manifest.csv"),
        "package_manifest": str(args.out_dir / "package_manifest.csv"),
        "data_dictionary_csv": str(args.out_dir / "data_dictionary.csv"),
        "data_dictionary_md": str(args.out_dir / "data_dictionary.md"),
        "formula_aggregation_note": str(args.out_dir / FORMULA_AGGREGATION_NOTE),
        "formula_coefficients": str(args.out_dir / "formula_coefficients.csv"),
        "formula_coefficients_json": str(args.out_dir / "formula_coefficients.json"),
        "formula_provenance": str(args.out_dir / "formula_provenance.md"),
    }
    if errors:
        payload = {
            "status": "INVALID",
            "report_dir": str(args.report_dir),
            "sensitivity_dir": str(args.sensitivity_dir),
            "out_dir": str(args.out_dir),
            "ready_event_count": ready_event_count,
            "pgd_event_count": int_value(dict(report_summary.get("counts") or {}).get("unique_events")),
            "recommended_formula": str(recommendation.get("recommended_formula") or ""),
            "station_aggregation": STATION_AGGREGATION,
            "requires_sensitivity_caveat": True,
            "sensitivity_switch_scenarios": switch_scenarios,
            "bundle_status": bundle_summary.get("status", ""),
            "outputs": outputs,
            "errors": errors,
        }
        write_json(output_summary, payload)
        write_markdown(output_md, payload, [], [], [], [], [])
        return payload

    coefficient_rows = formula_coefficient_rows()
    evidence_rows = residual_evidence_rows(residual_triage_rows)
    evidence_payload = residual_evidence_payload(evidence_rows)
    annotation_starter_rows = residual_annotation_starter_rows(evidence_rows)
    packet_index_rows = residual_packet_index_rows(evidence_rows)
    data_dictionary_rows = build_data_dictionary(
        {
            "release_events": release_fields,
            "formula_comparison": formula_fields,
            "formula_coefficients": FORMULA_COEFFICIENT_FIELDS,
            "sensitivity_recommendations": sensitivity_fields,
            "residual_triage_top": TRIAGE_TOP_FIELDS,
            "residual_review_evidence": RESIDUAL_EVIDENCE_FIELDS,
            "residual_review_annotations_starter": RESIDUAL_ANNOTATION_STARTER_FIELDS,
            "residual_review_packet_index": RESIDUAL_PACKET_INDEX_FIELDS,
            "figure_manifest": figure_fields,
            "package_manifest": PACKAGE_MANIFEST_FIELDS,
        }
    )
    manifest_rows = [
        {"product": "release_package_summary", "path": outputs["summary"], "source_path": "", "role": "machine summary", "row_count": "1"},
        {"product": "release_package", "path": outputs["markdown"], "source_path": "", "role": "human report", "row_count": "1"},
        {"product": "release_events", "path": outputs["release_events"], "source_path": str(inputs["release_events"]), "role": "ready event table", "row_count": str(len(release_events))},
        {"product": "formula_comparison", "path": outputs["formula_comparison"], "source_path": str(inputs["formula_comparison"]), "role": "baseline formula comparison", "row_count": str(len(formula_rows))},
        {"product": "sensitivity_recommendations", "path": outputs["sensitivity_recommendations"], "source_path": str(inputs["sensitivity_recommendations"]), "role": "sensitivity caveat source", "row_count": str(len(sensitivity_rows))},
        {"product": "residual_triage_top", "path": outputs["residual_triage_top"], "source_path": str(inputs["residual_triage_summary"]), "role": "top residual triage rows", "row_count": str(len(triage_rows))},
        {"product": "residual_review_evidence", "path": outputs["residual_review_evidence"], "source_path": str(inputs["residual_triage"]), "role": "full residual review evidence queue", "row_count": str(len(evidence_rows))},
        {"product": "residual_review_annotations_starter", "path": outputs["residual_review_annotations_starter"], "source_path": outputs["residual_review_evidence"], "role": "blank manual residual review annotation worksheet", "row_count": str(len(annotation_starter_rows))},
        {"product": "residual_review_annotations_starter_md", "path": outputs["residual_review_annotations_starter_md"], "source_path": outputs["residual_review_annotations_starter"], "role": "human-readable residual review annotation worksheet", "row_count": "1"},
        {"product": "residual_review_checklist", "path": outputs["residual_review_checklist"], "source_path": outputs["residual_review_evidence"], "role": "manual residual review checklist", "row_count": "1"},
        {"product": "residual_review_packet_index", "path": outputs["residual_review_packet_index"], "source_path": outputs["residual_review_evidence"], "role": "residual review packet index", "row_count": str(len(packet_index_rows))},
        {"product": "residual_review_packets", "path": outputs["residual_review_packets_dir"], "source_path": outputs["residual_review_packet_index"], "role": "one markdown packet per residual evidence row", "row_count": str(len(packet_index_rows))},
        {"product": "figure_manifest", "path": outputs["figure_manifest"], "source_path": str(inputs["figure_manifest"]), "role": "figure manifest", "row_count": str(len(figure_rows))},
        {"product": "data_dictionary", "path": outputs["data_dictionary_csv"], "source_path": "", "role": "field dictionary", "row_count": str(len(data_dictionary_rows))},
        {"product": "formula_aggregation_note", "path": outputs["formula_aggregation_note"], "source_path": "", "role": "PGD formula and median aggregation note", "row_count": "1"},
        {"product": "formula_coefficients", "path": outputs["formula_coefficients"], "source_path": "scripts/pgd_magnitude/evaluate_pgd_magnitude.py", "role": "PGD formula coefficients", "row_count": str(len(coefficient_rows))},
        {"product": "formula_provenance", "path": outputs["formula_provenance"], "source_path": "scripts/pgd_magnitude/evaluate_pgd_magnitude.py", "role": "PGD formula equation and citation provenance", "row_count": "1"},
    ]
    payload = {
        "status": status,
        "report_dir": str(args.report_dir),
        "sensitivity_dir": str(args.sensitivity_dir),
        "out_dir": str(args.out_dir),
        "ready_event_count": ready_event_count,
        "pgd_event_count": int_value(dict(report_summary.get("counts") or {}).get("unique_events")),
        "recommended_formula": str(recommendation.get("recommended_formula") or ""),
        "station_aggregation": STATION_AGGREGATION,
        "requires_sensitivity_caveat": bool(interpretation_flags.get("requires_sensitivity_caveat")) or str(sensitivity_summary.get("recommendation_stable") or "").lower() != "yes",
        "sensitivity_switch_scenarios": switch_scenarios,
        "release_set": report_summary.get("pgd_release_set", {}),
        "residual_triage": {
            "row_count": int_value(residual_triage.get("row_count")),
            "suggested_status_counts": residual_triage.get("suggested_status_counts", {}),
            "suggested_cause_counts": residual_triage.get("suggested_cause_counts", {}),
        },
        "residual_review_evidence": {
            "row_count": evidence_payload["row_count"],
            "suggested_status_counts": evidence_payload["suggested_status_counts"],
            "suggested_cause_counts": evidence_payload["suggested_cause_counts"],
            "release_status_counts": evidence_payload["release_status_counts"],
        },
        "residual_review_annotations_starter": {
            "row_count": len(annotation_starter_rows),
            "manual_fields": MANUAL_REVIEW_FIELDS,
        },
        "residual_review_packets": {
            "row_count": len(packet_index_rows),
            "index_csv": outputs["residual_review_packet_index"],
            "index_md": outputs["residual_review_packet_index_md"],
            "packet_dir": outputs["residual_review_packets_dir"],
        },
        "bundle_status": bundle_summary.get("status", ""),
        "outputs": outputs,
        "errors": [],
    }

    write_csv(args.out_dir / "release_events.csv", release_events, release_fields)
    write_csv(args.out_dir / "formula_comparison.csv", formula_rows, formula_fields)
    write_csv(args.out_dir / "sensitivity_recommendations.csv", sensitivity_rows, sensitivity_fields)
    write_csv(args.out_dir / "residual_triage_top.csv", triage_rows, TRIAGE_TOP_FIELDS)
    write_csv(args.out_dir / "residual_review_evidence.csv", evidence_rows, RESIDUAL_EVIDENCE_FIELDS)
    write_json(args.out_dir / "residual_review_evidence.json", evidence_payload)
    write_residual_evidence_markdown(args.out_dir / "residual_review_evidence.md", evidence_payload)
    write_csv(args.out_dir / "residual_review_annotations_starter.csv", annotation_starter_rows, RESIDUAL_ANNOTATION_STARTER_FIELDS)
    write_residual_annotation_starter_markdown(args.out_dir / "residual_review_annotations_starter.md", annotation_starter_rows)
    write_residual_review_checklist(args.out_dir / "residual_review_checklist.md", len(annotation_starter_rows))
    write_csv(args.out_dir / "residual_review_packet_index.csv", packet_index_rows, RESIDUAL_PACKET_INDEX_FIELDS)
    write_residual_packet_index_markdown(args.out_dir / "residual_review_packet_index.md", packet_index_rows)
    write_residual_review_packets(args.out_dir / "residual_review_packets", evidence_rows)
    write_csv(args.out_dir / "figure_manifest.csv", figure_rows, figure_fields)
    write_csv(args.out_dir / "package_manifest.csv", manifest_rows, PACKAGE_MANIFEST_FIELDS)
    write_csv(args.out_dir / "data_dictionary.csv", data_dictionary_rows, DATA_DICTIONARY_FIELDS)
    write_data_dictionary_markdown(args.out_dir / "data_dictionary.md", data_dictionary_rows)
    write_csv(args.out_dir / "formula_coefficients.csv", coefficient_rows, FORMULA_COEFFICIENT_FIELDS)
    write_formula_coefficients_json(args.out_dir / "formula_coefficients.json", coefficient_rows)
    write_formula_provenance_markdown(args.out_dir / "formula_provenance.md", coefficient_rows)
    write_json(output_summary, payload)
    write_markdown(output_md, payload, release_events, formula_rows, sensitivity_rows, triage_rows, figure_rows)
    legacy_note = args.out_dir / LEGACY_FORMULA_NOTE
    if legacy_note.is_file():
        legacy_note.unlink()
    write_formula_aggregation_note(args.out_dir / FORMULA_AGGREGATION_NOTE, payload, formula_rows, sensitivity_rows)
    return payload


def write_markdown(
    path: Path,
    payload: dict[str, Any],
    release_events: list[dict[str, str]],
    formula_rows: list[dict[str, str]],
    sensitivity_rows: list[dict[str, str]],
    triage_rows: list[dict[str, str]],
    figure_rows: list[dict[str, str]],
) -> None:
    caveat = "required" if payload.get("requires_sensitivity_caveat") else "not required"
    lines = [
        "# PGD Release Package",
        "",
        f"- Status: `{payload.get('status', '')}`",
        f"- Ready events: {payload.get('ready_event_count', 0)}",
        f"- PGD evaluable events: {payload.get('pgd_event_count', 0)}",
        f"- Recommended formula: `{payload.get('recommended_formula', '')}`",
        f"- Station aggregation method: `{STATION_AGGREGATION}`",
        f"- Sensitivity caveat: `{caveat}`",
        f"- Sensitivity switch scenarios: {', '.join(f'`{item}`' for item in payload.get('sensitivity_switch_scenarios', [])) or 'none'}",
        f"- Bundle status: `{payload.get('bundle_status', '')}`",
        "",
    ]
    errors = payload.get("errors") or []
    if errors:
        lines.extend(["## Errors", "", *markdown_table(errors, ["code", "message", "path"]), ""])
    lines.extend(
        [
            "## Release Events",
            "",
            *markdown_table(
                release_events,
                ["event_id", "event_time", "country", "usgs_magnitude", "estimated_mw_median", "abs_residual_mw", "pgd_reliability", "usable_station_count"],
            ),
            "",
            "## Formula Comparison",
            "",
            *markdown_table(formula_rows, ["formula", "station_aggregation", "event_count", "mae_mw", "rmse_mw", "median_abs_error_mw", "residual_outlier_count"]),
            "",
            "## Sensitivity Recommendations",
            "",
            *markdown_table(sensitivity_rows, ["scenario_id", "recommended_formula", "matches_baseline", "mae_mw", "rmse_mw"]),
            "",
            "## Residual Triage",
            "",
            f"- Review rows: {dict(payload.get('residual_triage') or {}).get('row_count', 0)}",
            f"- Suggested statuses: {json.dumps(dict(payload.get('residual_triage') or {}).get('suggested_status_counts', {}), sort_keys=True)}",
            f"- Full evidence rows: {dict(payload.get('residual_review_evidence') or {}).get('row_count', 0)}",
            "",
            *markdown_table(triage_rows, TRIAGE_TOP_FIELDS),
            "",
            "Full residual review evidence is available in `residual_review_evidence.csv`, `residual_review_evidence.json`, and `residual_review_evidence.md`.",
            "Blank manual annotation starters are available in `residual_review_annotations_starter.csv` and `residual_review_annotations_starter.md`; use `residual_review_checklist.md` while filling them.",
            "Per-row review packets are available through `residual_review_packet_index.csv`, `residual_review_packet_index.md`, and `residual_review_packets/`.",
            "",
            "## Figures",
            "",
            *markdown_table(figure_rows, ["figure_type", "path", "role"]),
            "",
            "## Documentation",
            "",
            "- `data_dictionary.csv` and `data_dictionary.md` define release package fields.",
            "- `formula_aggregation_note.md` defines the median-only station aggregation method and the three PGD formulas.",
            "- `formula_coefficients.csv`, `formula_coefficients.json`, and `formula_provenance.md` document formula coefficients, equations, and reference metadata.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_package(args)
    print(json.dumps({"status": payload["status"], "ready_event_count": payload.get("ready_event_count", 0), "out_dir": str(args.out_dir)}, indent=2))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
