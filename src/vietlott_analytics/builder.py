from __future__ import annotations

import json
from pathlib import Path

from .catalog import PRODUCT_ORDER, PRODUCTS
from .fairness import (
    audit_log_events,
    build_product_audit,
    dump_jsonl,
    finalize_audits,
)
from .io import load_prize_summary, load_product_dataset
from .predictions import PredictionLedger, build_backtest_report
from .statistics import build_product_report


def build_research_site(
    datasets_dir: Path = Path("datasets"),
    site_dir: Path = Path("site"),
    prediction_ledger_path: Path = Path("predictions/ledger.jsonl"),
) -> dict[str, object]:
    datasets_dir = datasets_dir.resolve()
    site_dir = site_dir.resolve()
    product_data_dir = site_dir / "data" / "products"
    product_data_dir.mkdir(parents=True, exist_ok=True)
    ledger = PredictionLedger.load(prediction_ledger_path.resolve())
    product_summaries: list[dict[str, object]] = []
    product_reports: list[dict[str, object]] = []

    for slug in PRODUCT_ORDER:
        product = PRODUCTS[slug]
        dataset = load_product_dataset(datasets_dir, product)
        prize_summary = load_prize_summary(datasets_dir, product)
        report = build_product_report(dataset, prize_summary)
        report["backtest"] = build_backtest_report(dataset)
        report["audit"] = build_product_audit(dataset)
        product_reports.append(report)
        ledger.process_product(dataset)
        summary = report["summary"]
        product_summaries.append(
            {
                "slug": slug,
                "name": product.name,
                "short_name": product.short_name,
                "kind": product.kind.value,
                "active": product.active,
                "confirmed_draws": summary["confirmed_draws"],
                "not_confirmed_draws": summary["not_confirmed_draws"],
                "first_date": summary["first_date"],
                "latest_date": summary["latest_date"],
                "latest_draw_id": summary["latest_draw_id"],
            }
        )

    audit_summary = finalize_audits(product_reports)
    for report in product_reports:
        _write_json(product_data_dir / f"{report['product']['slug']}.json", report)
    _write_json(site_dir / "data" / "audit-summary.json", audit_summary)
    _write_jsonl(site_dir / "data" / "audit-log.jsonl", audit_log_events(product_reports))

    ledger.save()
    prediction_report = ledger.site_report()
    _write_json(site_dir / "data" / "predictions.json", prediction_report)

    source_summary_path = datasets_dir / "metadata" / "dataset-summary.json"
    source_summary = json.loads(source_summary_path.read_text(encoding="utf-8"))
    manifest = {
        "schema_version": 1,
        "title": "Vietlott Data Research",
        "generated_from_dataset_at": source_summary.get("dataset_updated_at"),
        "draw_rows": source_summary["draw_rows"],
        "confirmed_rows": source_summary["confirmed_rows"],
        "not_confirmed_rows": source_summary["not_confirmed_rows"],
        "prize_rows": source_summary["prize_rows"],
        "products": product_summaries,
        "prediction_evaluations": prediction_report["evaluation_count"],
        "prediction_pending": prediction_report["pending_count"],
        "fairness_audit": audit_summary["summary"],
        "methodology_version": "1.0.0",
    }
    _write_json(site_dir / "data" / "manifest.json", manifest)
    return manifest


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def _write_jsonl(path: Path, events: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(dump_jsonl(events), encoding="utf-8")
    temp_path.replace(path)
