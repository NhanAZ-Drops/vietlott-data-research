from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .config import PRODUCT_SPECS
from .models import DrawRecord
from .provenance import assess_provenance
from .validation import validate_draw

QUALITY_REPORT_VERSION = "1.0.0"
PARSER_VERSION = "0.2.0"
MANIFEST_TEXT_SUFFIXES = {".csv", ".json", ".jsonl", ".md", ".py", ".yml", ".yaml", ".txt"}
METHODOLOGY_VERSIONS = {
    "data_quality": QUALITY_REPORT_VERSION,
    "descriptive_statistics": "1.0.0",
    "fairness_audit": "2.0.0",
    "backtest": "2.0.0",
    "prediction_ledger": "3.0.0",
    "weather": "1.0.0",
}


@dataclass(slots=True)
class ProductQuality:
    rows: int = 0
    result_rows: int = 0
    prize_rows: int = 0
    draws_with_prizes: set[str] = field(default_factory=set)
    draw_statuses: Counter[str] = field(default_factory=Counter)
    structural_validity: Counter[str] = field(default_factory=Counter)
    source_origins: Counter[str] = field(default_factory=Counter)
    source_verification: Counter[str] = field(default_factory=Counter)
    prize_statuses: Counter[str] = field(default_factory=Counter)
    numeric_ids: set[int] = field(default_factory=set)
    first_date: str | None = None
    last_date: str | None = None
    min_id: str | None = None
    max_id: str | None = None
    missing_required_fields: Counter[str] = field(default_factory=Counter)
    invalid_json_rows: int = 0
    validation_mismatches: int = 0
    order_regressions: int = 0
    previous_order: tuple[str, int] | None = None


KNOWN_GAPS = {
    "keno": {
        *range(32_987, 33_061),
        115_204,
    },
}


def audit_repository(root: Path = Path("datasets")) -> dict[str, object]:
    root = root.resolve()
    summary = _read_json(root / "metadata" / "dataset-summary.json")
    products: dict[str, ProductQuality] = defaultdict(ProductQuality)
    duplicate_keys: list[dict[str, str]] = []
    seen_keys: set[tuple[str, str]] = set()

    for path in sorted((root / "draws").glob("*/*.csv")):
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                product = row.get("product", "")
                profile = products[product]
                profile.rows += 1
                key = (product, row.get("draw_id", ""))
                if key in seen_keys and len(duplicate_keys) < 100:
                    duplicate_keys.append({"product": key[0], "draw_id": key[1]})
                seen_keys.add(key)
                _profile_draw(profile, row)

    for path in sorted((root / "prizes").glob("*/*.csv")):
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                profile = products[row.get("product", "")]
                profile.prize_rows += 1
                profile.draws_with_prizes.add(row.get("draw_id", ""))

    product_reports = {
        product: _product_report(product, profile)
        for product, profile in sorted(products.items())
    }
    totals = {
        "draw_rows": sum(profile.rows for profile in products.values()),
        "result_rows": sum(profile.result_rows for profile in products.values()),
        "prize_rows": sum(profile.prize_rows for profile in products.values()),
        "draws_with_prizes": sum(
            len(profile.draws_with_prizes) for profile in products.values()
        ),
        "duplicate_draw_keys": len(duplicate_keys),
        "structurally_valid_rows": sum(
            profile.structural_validity["valid"] for profile in products.values()
        ),
        "official_source_rows": sum(
            profile.source_origins["official"] for profile in products.values()
        ),
        "cross_checked_rows": sum(
            profile.source_verification["official_verified_match"]
            + profile.source_verification["multi_source_consensus"]
            for profile in products.values()
        ),
    }
    return {
        "schema_version": 1,
        "report_version": QUALITY_REPORT_VERSION,
        "generated_from_dataset_at": summary.get("dataset_updated_at"),
        "grain": "one canonical row per (product, draw_id)",
        "definitions": {
            "draw_confirmation": (
                "Whether an issued draw is accepted for statistical analysis. "
                "It is separate from schema validation and source provenance."
            ),
            "structural_validity": (
                "Deterministic validation of identifier width, result shape, "
                "number range and uniqueness rules."
            ),
            "official_source": (
                "The canonical row is explicitly labelled official_vietlott or carries "
                "stored official verification evidence. A Vietlott-looking URL alone is "
                "not enough to promote an unlabelled legacy row."
            ),
            "cross_checked": (
                "Stored metadata shows an official match or multi-source consensus."
            ),
            "candidate_gap": (
                "A numeric identifier absent between the observed minimum and maximum. "
                "It is not automatically a missing draw."
            ),
        },
        "totals": totals,
        "duplicate_draw_examples": duplicate_keys,
        "products": product_reports,
        "limitations": [
            (
                "Legacy canonical rows do not always retain every raw source observation. "
                "Conflict counts are therefore reported as unavailable rather than zero."
            ),
            (
                "Recent numeric gaps may represent identifiers that were never issued, "
                "delayed publication or incomplete collection. They remain unresolved "
                "until evidence is recorded."
            ),
        ],
    }


def build_snapshot_manifest(root: Path = Path("datasets")) -> dict[str, object]:
    root = root.resolve()
    summary = _read_json(root / "metadata" / "dataset-summary.json")
    files: dict[str, dict[str, object]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative == "metadata/snapshot-manifest.json":
            continue
        content = _manifest_bytes(path)
        entry: dict[str, object] = {
            "bytes": len(content),
            "sha256": _sha256_bytes(content),
        }
        if path.suffix.lower() == ".csv":
            entry["data_rows"] = _csv_data_rows(path)
        files[relative] = entry
    return {
        "schema_version": 1,
        "snapshot_at": summary.get("dataset_updated_at"),
        "dataset_rows": {
            "draws": summary.get("draw_rows"),
            "prizes": summary.get("prize_rows"),
        },
        "date_range": {
            "first": min(
                (
                    str(item.get("first_date"))
                    for item in summary.get("products", {}).values()
                    if item.get("first_date")
                ),
                default=None,
            ),
            "last": max(
                (
                    str(item.get("last_date"))
                    for item in summary.get("products", {}).values()
                    if item.get("last_date")
                ),
                default=None,
            ),
        },
        "parser_version": PARSER_VERSION,
        "methodology_versions": METHODOLOGY_VERSIONS,
        "repository_commit": _repository_commit(root),
        "files": files,
    }


def write_quality_metadata(root: Path = Path("datasets")) -> dict[str, object]:
    root = root.resolve()
    metadata_dir = root / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    quality = audit_repository(root)
    _write_json(metadata_dir / "quality-report.json", quality)
    manifest = build_snapshot_manifest(root)
    _write_json(metadata_dir / "snapshot-manifest.json", manifest)
    return {
        "quality_report": quality,
        "snapshot_manifest": manifest,
    }


def _profile_draw(profile: ProductQuality, row: dict[str, str]) -> None:
    required = ("product", "draw_id", "draw_date", "result_json", "source_url")
    for field_name in required:
        if not str(row.get(field_name, "")).strip():
            profile.missing_required_fields[field_name] += 1
    profile.draw_statuses[row.get("draw_status", "") or "unknown"] += 1
    profile.prize_statuses[row.get("prize_status", "") or "unknown"] += 1
    assessment = assess_provenance(row)
    profile.structural_validity[assessment.structural_validity.value] += 1
    profile.source_origins[assessment.source_origin.value] += 1
    profile.source_verification[assessment.source_verification.value] += 1
    draw_id = row.get("draw_id", "")
    if draw_id.isdigit():
        profile.numeric_ids.add(int(draw_id))
    profile.min_id = draw_id if profile.min_id is None else min(profile.min_id, draw_id)
    profile.max_id = draw_id if profile.max_id is None else max(profile.max_id, draw_id)
    draw_date = row.get("draw_date", "")
    profile.first_date = (
        draw_date if profile.first_date is None else min(profile.first_date, draw_date)
    )
    profile.last_date = (
        draw_date if profile.last_date is None else max(profile.last_date, draw_date)
    )
    try:
        result = json.loads(row.get("result_json", ""))
    except (json.JSONDecodeError, TypeError):
        profile.invalid_json_rows += 1
        return
    if result:
        profile.result_rows += 1
    product = row.get("product", "")
    spec = PRODUCT_SPECS.get(product)
    if spec is not None:
        try:
            record = DrawRecord(
                product=product,
                draw_id=draw_id,
                draw_date=date.fromisoformat(draw_date),
                result=result if isinstance(result, dict) else {},
                source_url=row.get("source_url", ""),
                draw_status=row.get("draw_status", "confirmed") or "confirmed",
            )
            computed = "valid" if not validate_draw(record, spec) else "warning"
            stored = row.get("validation_status", "unchecked") or "unchecked"
            if stored != "unchecked" and stored != computed:
                profile.validation_mismatches += 1
        except ValueError:
            profile.validation_mismatches += 1
    if draw_id.isdigit() and draw_date:
        order = (draw_date, int(draw_id))
        if profile.previous_order is not None and order < profile.previous_order:
            profile.order_regressions += 1
        profile.previous_order = order


def _product_report(product: str, profile: ProductQuality) -> dict[str, object]:
    candidate_gaps = _candidate_gaps(profile.numeric_ids)
    known = KNOWN_GAPS.get(product, set())
    classifications: Counter[str] = Counter()
    ranges: list[dict[str, object]] = []
    for first, last in _ranges(candidate_gaps):
        values = set(range(first, last + 1))
        if values <= known:
            classification = "known_not_issued"
        elif values & known:
            classification = "mixed"
        else:
            classification = "unresolved"
        classifications[classification] += last - first + 1
        ranges.append(
            {
                "first_id": str(first).zfill(7 if product in {"keno", "bingo18"} else 5),
                "last_id": str(last).zfill(7 if product in {"keno", "bingo18"} else 5),
                "count": last - first + 1,
                "classification": classification,
            }
        )
    prize_draws = len(profile.draws_with_prizes)
    return {
        "rows": profile.rows,
        "first_date": profile.first_date,
        "last_date": profile.last_date,
        "min_id": profile.min_id,
        "max_id": profile.max_id,
        "result_coverage": {
            "rows_with_result": profile.result_rows,
            "rate": _rate(profile.result_rows, profile.rows),
        },
        "prize_coverage": {
            "draws_with_prize_rows": prize_draws,
            "prize_rows": profile.prize_rows,
            "rate": _rate(prize_draws, profile.rows),
        },
        "draw_confirmation": dict(profile.draw_statuses),
        "structural_validity": dict(profile.structural_validity),
        "source_origin": dict(profile.source_origins),
        "source_verification": dict(profile.source_verification),
        "prize_status": dict(profile.prize_statuses),
        "source_agreement": {
            "official_direct": profile.source_verification["official_direct"],
            "official_verified_match": profile.source_verification[
                "official_verified_match"
            ],
            "multi_source_consensus": profile.source_verification[
                "multi_source_consensus"
            ],
            "single_secondary_source": profile.source_verification[
                "single_secondary_source"
            ],
            "pending_official": profile.source_verification["pending_official"],
            "unknown": profile.source_verification["unknown"],
            "conflicts": None,
            "conflict_count_reason": (
                "Raw source observations were not retained consistently in legacy rows."
            ),
        },
        "candidate_gaps": {
            "count": len(candidate_gaps),
            "classification_counts": dict(classifications),
            "ranges": ranges,
            "interpretation": (
                "An absent numeric ID is a candidate gap only. It is not classified "
                "as a missing draw without source evidence."
            ),
        },
        "checks": {
            "missing_required_fields": dict(profile.missing_required_fields),
            "invalid_json_rows": profile.invalid_json_rows,
            "validation_mismatches": profile.validation_mismatches,
            "file_order_regressions": profile.order_regressions,
        },
    }


def _candidate_gaps(values: set[int]) -> list[int]:
    if not values:
        return []
    return [value for value in range(min(values), max(values) + 1) if value not in values]


def _ranges(values: list[int]) -> list[tuple[int, int]]:
    if not values:
        return []
    result: list[tuple[int, int]] = []
    first = previous = values[0]
    for value in values[1:]:
        if value == previous + 1:
            previous = value
            continue
        result.append((first, previous))
        first = previous = value
    result.append((first, previous))
    return result


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 8) if denominator else 0.0


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _csv_data_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def _sha256(path: Path) -> str:
    return _sha256_bytes(_manifest_bytes(path))


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _manifest_bytes(path: Path) -> bytes:
    content = path.read_bytes()
    if path.suffix.lower() in MANIFEST_TEXT_SUFFIXES:
        return content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return content


def _repository_commit(root: Path) -> str | None:
    if value := os.environ.get("GITHUB_SHA"):
        return value
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
