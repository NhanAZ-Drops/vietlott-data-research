from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
from collections import Counter, defaultdict
from contextlib import ExitStack
from pathlib import Path
from typing import TextIO

from .exclusions import KNOWN_EXCLUSIONS
from .quality import write_quality_metadata
from .storage import DRAW_COLUMNS, PRIZE_COLUMNS

HIGH_FREQUENCY_PRODUCTS = {"keno", "bingo18"}
MAX_GITHUB_FILE_BYTES = 100 * 1024 * 1024
MANIFEST_TEXT_SUFFIXES = {".csv", ".json", ".jsonl", ".md", ".py", ".yml", ".yaml", ".txt"}


def publish_repository_data(
    source_dir: Path = Path("data"),
    destination_dir: Path = Path("datasets"),
) -> dict[str, object]:
    draws_path = source_dir / "draws.csv"
    prizes_path = source_dir / "prizes.csv"
    if not draws_path.exists() or not prizes_path.exists():
        raise FileNotFoundError("data/draws.csv and data/prizes.csv are required")

    destination_dir = destination_dir.resolve()
    temp_dir = destination_dir.with_name(f".{destination_dir.name}.tmp")
    _remove_tree(temp_dir)
    temp_dir.mkdir(parents=True)

    try:
        _copy_auxiliary_dataset_files(destination_dir, temp_dir)
        summary = _partition_draws(draws_path, temp_dir / "draws")
        prize_rows = _partition_prizes(prizes_path, temp_dir / "prizes")
        _write_exclusions(temp_dir / "exclusions.csv")

        rules_source = source_dir / "prize_rules.csv"
        if rules_source.exists():
            shutil.copyfile(rules_source, temp_dir / "prize_rules.csv")

        summary["prize_rows"] = prize_rows
        summary["schema_version"] = 1
        summary["storage_layout"] = {
            "high_frequency": "draws/<product>/YYYY-MM.csv",
            "other_products": "draws/<product>/all.csv",
            "prizes": "prizes/<product>/all.csv",
        }
        summary_path = temp_dir / "metadata" / "dataset-summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_quality_metadata(temp_dir)

        _remove_tree(destination_dir)
        os.replace(temp_dir, destination_dir)
        validation = validate_repository_data(destination_dir)
        if not validation["valid"]:
            raise RuntimeError(
                "Published repository data failed validation: "
                + "; ".join(validation["errors"])
            )
        return validation
    except Exception:
        _remove_tree(temp_dir)
        raise


def hydrate_repository_data(
    source_dir: Path = Path("datasets"),
    destination_dir: Path = Path("data"),
) -> dict[str, int]:
    source_dir = source_dir.resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    draw_rows = _join_partitions(
        sorted((source_dir / "draws").glob("*/*.csv")),
        destination_dir / "draws.csv",
        DRAW_COLUMNS,
    )
    prize_rows = _join_partitions(
        sorted((source_dir / "prizes").glob("*/*.csv")),
        destination_dir / "prizes.csv",
        PRIZE_COLUMNS,
    )
    rules_source = source_dir / "prize_rules.csv"
    if rules_source.exists():
        shutil.copyfile(rules_source, destination_dir / "prize_rules.csv")
    return {"draw_rows": draw_rows, "prize_rows": prize_rows}


def validate_repository_data(root: Path = Path("datasets")) -> dict[str, object]:
    root = root.resolve()
    errors: list[str] = []
    draw_keys: set[tuple[str, str]] = set()
    prize_keys: set[tuple[str, ...]] = set()
    draw_rows = 0
    prize_rows = 0
    files: dict[str, dict[str, object]] = {}

    draw_paths = sorted((root / "draws").glob("*/*.csv"))
    prize_paths = sorted((root / "prizes").glob("*/*.csv"))
    if not draw_paths:
        errors.append("No draw partitions found")
    if not prize_paths:
        errors.append("No prize partitions found")

    for path in [*draw_paths, *prize_paths, root / "exclusions.csv", root / "prize_rules.csv"]:
        if not path.exists():
            continue
        content = _manifest_bytes(path)
        size = len(content)
        relative = path.relative_to(root).as_posix()
        files[relative] = {
            "bytes": size,
            "sha256": _sha256_bytes(content),
        }
        if size >= MAX_GITHUB_FILE_BYTES:
            errors.append(f"{relative} is too large for normal Git storage")

    for path in draw_paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != DRAW_COLUMNS:
                errors.append(f"Unexpected draw columns in {path.relative_to(root)}")
                continue
            for row in reader:
                draw_rows += 1
                key = (row["product"], row["draw_id"])
                if key in draw_keys:
                    errors.append(f"Duplicate draw key {key}")
                    continue
                draw_keys.add(key)
                for field in ("product", "draw_id", "draw_date", "result_json", "source_url"):
                    if not row[field].strip():
                        errors.append(f"Missing {field} for draw {key}")
                try:
                    json.loads(row["result_json"])
                except json.JSONDecodeError:
                    errors.append(f"Invalid result_json for draw {key}")
                if row["draw_status"] not in {"confirmed", "not_confirmed"}:
                    errors.append(f"Invalid draw_status for draw {key}")

    prize_identity = (
        "product",
        "draw_id",
        "game_variant",
        "prize_tier",
        "winning_rule",
        "prize_value_vnd",
    )
    for path in prize_paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != PRIZE_COLUMNS:
                errors.append(f"Unexpected prize columns in {path.relative_to(root)}")
                continue
            for row in reader:
                prize_rows += 1
                key = tuple(row[column] for column in prize_identity)
                if key in prize_keys:
                    errors.append(f"Duplicate prize key {key}")
                    continue
                prize_keys.add(key)
                if (row["product"], row["draw_id"]) not in draw_keys:
                    errors.append(
                        f"Orphan prize row {(row['product'], row['draw_id'])}"
                    )

    summary_path = root / "metadata" / "dataset-summary.json"
    if not summary_path.exists():
        errors.append("Missing metadata/dataset-summary.json")
    else:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if int(summary.get("draw_rows", -1)) != draw_rows:
            errors.append("Summary draw_rows does not match partitions")
        if int(summary.get("prize_rows", -1)) != prize_rows:
            errors.append("Summary prize_rows does not match partitions")

    quality_path = root / "metadata" / "quality-report.json"
    if not quality_path.exists():
        errors.append("Missing metadata/quality-report.json")
    else:
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
        totals = quality.get("totals", {})
        if int(totals.get("draw_rows", -1)) != draw_rows:
            errors.append("Quality report draw_rows does not match partitions")
        if int(totals.get("prize_rows", -1)) != prize_rows:
            errors.append("Quality report prize_rows does not match partitions")

    manifest_path = root / "metadata" / "snapshot-manifest.json"
    if not manifest_path.exists():
        errors.append("Missing metadata/snapshot-manifest.json")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_rows = manifest.get("dataset_rows", {})
        if int(manifest_rows.get("draws", -1)) != draw_rows:
            errors.append("Snapshot manifest draw_rows does not match partitions")
        if int(manifest_rows.get("prizes", -1)) != prize_rows:
            errors.append("Snapshot manifest prize_rows does not match partitions")
        for relative, expected in manifest.get("files", {}).items():
            path = root / relative
            if not path.exists():
                errors.append(f"Snapshot file is missing: {relative}")
                continue
            content = _manifest_bytes(path)
            if int(expected.get("bytes", -1)) != len(content):
                errors.append(f"Snapshot byte size changed: {relative}")
            if str(expected.get("sha256", "")) != _sha256_bytes(content):
                errors.append(f"Snapshot hash changed: {relative}")

    return {
        "valid": not errors,
        "draw_rows": draw_rows,
        "prize_rows": prize_rows,
        "files": files,
        "errors": errors[:100],
    }


def _partition_draws(source: Path, destination: Path) -> dict[str, object]:
    counts: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    products: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "rows": 0,
            "first_date": None,
            "last_date": None,
            "min_id": None,
            "max_id": None,
            "confirmed_rows": 0,
            "not_confirmed_rows": 0,
        }
    )
    latest_fetched_at = ""

    with ExitStack() as stack:
        writers: dict[Path, csv.DictWriter] = {}
        with source.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("draws.csv has no header")
            for row in reader:
                normalized = {column: row.get(column, "") for column in DRAW_COLUMNS}
                normalized["draw_status"] = normalized["draw_status"] or "confirmed"
                product = normalized["product"]
                date_value = normalized["draw_date"]
                partition = date_value[:7] if product in HIGH_FREQUENCY_PRODUCTS else "all"
                path = destination / product / f"{partition}.csv"
                writer = _writer_for(path, DRAW_COLUMNS, writers, stack)
                writer.writerow(normalized)
                counts[product] += 1
                statuses[normalized["draw_status"]] += 1
                latest_fetched_at = max(latest_fetched_at, normalized["fetched_at"])

                stats = products[product]
                stats["rows"] = int(stats["rows"]) + 1
                stats["first_date"] = _minimum(stats["first_date"], date_value)
                stats["last_date"] = _maximum(stats["last_date"], date_value)
                stats["min_id"] = _numeric_extreme(stats["min_id"], normalized["draw_id"], min)
                stats["max_id"] = _numeric_extreme(stats["max_id"], normalized["draw_id"], max)
                status_key = f"{normalized['draw_status']}_rows"
                if status_key in stats:
                    stats[status_key] = int(stats[status_key]) + 1

    return {
        "draw_rows": sum(counts.values()),
        "confirmed_rows": statuses["confirmed"],
        "not_confirmed_rows": statuses["not_confirmed"],
        "dataset_updated_at": latest_fetched_at or None,
        "products": dict(sorted(products.items())),
    }


def _partition_prizes(source: Path, destination: Path) -> int:
    total = 0
    with ExitStack() as stack:
        writers: dict[Path, csv.DictWriter] = {}
        with source.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("prizes.csv has no header")
            for row in reader:
                normalized = {column: row.get(column, "") for column in PRIZE_COLUMNS}
                path = destination / normalized["product"] / "all.csv"
                _writer_for(path, PRIZE_COLUMNS, writers, stack).writerow(normalized)
                total += 1
    return total


def _writer_for(
    path: Path,
    columns: list[str],
    writers: dict[Path, csv.DictWriter],
    stack: ExitStack,
) -> csv.DictWriter:
    writer = writers.get(path)
    if writer is not None:
        return writer
    path.parent.mkdir(parents=True, exist_ok=True)
    handle: TextIO = stack.enter_context(path.open("w", encoding="utf-8", newline=""))
    writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writers[path] = writer
    return writer


def _write_exclusions(path: Path) -> None:
    columns = [
        "product",
        "draw_id",
        "draw_status",
        "effective_date",
        "reason",
        "source_url",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for exclusion in KNOWN_EXCLUSIONS:
            for numeric_id in exclusion.draw_ids():
                writer.writerow(
                    {
                        "product": exclusion.product,
                        "draw_id": str(numeric_id).zfill(7),
                        "draw_status": exclusion.status,
                        "effective_date": exclusion.effective_date,
                        "reason": exclusion.reason,
                        "source_url": exclusion.source_url,
                    }
                )


def _join_partitions(paths: list[Path], destination: Path, columns: list[str]) -> int:
    if not paths:
        raise FileNotFoundError(f"No partitions found for {destination.name}")
    temp_path = destination.with_suffix(f"{destination.suffix}.tmp")
    rows = 0
    with temp_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for path in paths:
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames != columns:
                    raise ValueError(f"Unexpected columns in {path}")
                for row in reader:
                    writer.writerow(row)
                    rows += 1
    os.replace(temp_path, destination)
    return rows


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return
    if path == path.parent or not path.name:
        raise ValueError(f"Refusing to remove unsafe path {path}")
    shutil.rmtree(path)


def _copy_auxiliary_dataset_files(source: Path, destination: Path) -> None:
    """Preserve independently maintained datasets such as historical weather."""

    if not source.exists():
        return
    owned = {"draws", "prizes", "metadata", "exclusions.csv", "prize_rules.csv"}
    for item in source.iterdir():
        if item.name in owned:
            continue
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        elif item.is_file():
            shutil.copyfile(item, target)


def _minimum(old: object, new: str) -> str:
    return new if old is None else min(str(old), new)


def _maximum(old: object, new: str) -> str:
    return new if old is None else max(str(old), new)


def _numeric_extreme(old: object, new: str, operation) -> str:
    if old is None:
        return new
    if str(old).isdigit() and new.isdigit():
        return str(operation(int(str(old)), int(new))).zfill(max(len(str(old)), len(new)))
    return operation(str(old), new)


def _sha256(path: Path) -> str:
    return _sha256_bytes(_manifest_bytes(path))


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _manifest_bytes(path: Path) -> bytes:
    content = path.read_bytes()
    if path.suffix.lower() in MANIFEST_TEXT_SUFFIXES:
        return content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return content


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vietlott-repository-data",
        description="Publish, hydrate, or validate the Git-friendly dataset layout.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    publish = subparsers.add_parser("publish")
    publish.add_argument("--source-dir", type=Path, default=Path("data"))
    publish.add_argument("--destination-dir", type=Path, default=Path("datasets"))

    hydrate = subparsers.add_parser("hydrate")
    hydrate.add_argument("--source-dir", type=Path, default=Path("datasets"))
    hydrate.add_argument("--destination-dir", type=Path, default=Path("data"))

    validate = subparsers.add_parser("validate")
    validate.add_argument("--source-dir", type=Path, default=Path("datasets"))

    audit = subparsers.add_parser("audit")
    audit.add_argument("--source-dir", type=Path, default=Path("datasets"))
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "publish":
        report = publish_repository_data(args.source_dir, args.destination_dir)
    elif args.command == "hydrate":
        report = hydrate_repository_data(args.source_dir, args.destination_dir)
    elif args.command == "audit":
        report = write_quality_metadata(args.source_dir)
    else:
        report = validate_repository_data(args.source_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if args.command == "validate" and not report["valid"]:
        raise SystemExit(1)
