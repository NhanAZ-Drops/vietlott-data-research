from __future__ import annotations

import json
from pathlib import Path

from vietlott_collector.quality import METHODOLOGY_VERSIONS

from .catalog import PRODUCT_ORDER, PRODUCTS
from .fairness import (
    audit_log_events,
    build_product_audit,
    dump_jsonl,
    finalize_audits,
)
from .io import load_prize_summary, load_product_dataset
from .predictions import PredictionLedger, build_backtest_report, finalize_backtests
from .schema import ANALYSIS_EXPORT_SCHEMA
from .statistics import build_product_report
from .weather_analysis import build_weather_report, load_weather_days


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
    weather_days = load_weather_days(datasets_dir)
    dataset_quality = _read_json(
        datasets_dir / "metadata" / "quality-report.json"
    )
    snapshot_manifest = _read_json(
        datasets_dir / "metadata" / "snapshot-manifest.json"
    )
    product_summaries: list[dict[str, object]] = []
    product_reports: list[dict[str, object]] = []

    for slug in PRODUCT_ORDER:
        product = PRODUCTS[slug]
        dataset = load_product_dataset(datasets_dir, product)
        prize_summary = load_prize_summary(datasets_dir, product)
        report = build_product_report(dataset, prize_summary)
        quality_product = dataset_quality.get("products", {}).get(slug)
        if isinstance(quality_product, dict):
            report["data_quality"] = quality_product
        report["weather"] = build_weather_report(dataset, weather_days)
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
                "result_coverage_rate": summary["data_quality"][
                    "result_coverage_rate"
                ],
                "prize_coverage_rate": summary["data_quality"][
                    "prize_coverage_rate"
                ],
                "official_source_rate": summary["data_quality"][
                    "official_source_rate"
                ],
                "cross_checked_rate": summary["data_quality"][
                    "cross_checked_rate"
                ],
            }
        )

    backtest_summary = finalize_backtests(product_reports)
    audit_summary = finalize_audits(product_reports)
    for report in product_reports:
        _write_json(product_data_dir / f"{report['product']['slug']}.json", report)
    _write_json(site_dir / "data" / "audit-summary.json", audit_summary)
    audit_events = list(audit_log_events(product_reports))
    _write_jsonl(site_dir / "data" / "audit-log.jsonl", audit_events)

    ledger.save()
    prediction_report = ledger.site_report()
    _write_json(site_dir / "data" / "predictions.json", prediction_report)

    source_summary_path = datasets_dir / "metadata" / "dataset-summary.json"
    source_summary = json.loads(source_summary_path.read_text(encoding="utf-8"))
    manifest = {
        "schema_version": 2,
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
        "backtest_summary": backtest_summary,
        "methodology_versions": METHODOLOGY_VERSIONS,
        "dataset_quality": {
            "path": "data/dataset-quality.json",
            "report_version": dataset_quality.get("report_version"),
        },
        "snapshot_manifest": {
            "path": "data/snapshot-manifest.json",
            "schema_version": snapshot_manifest.get("schema_version"),
        },
        "analysis_export": {
            "path": "data/analysis-export.json",
            "schema_version": 2,
            "schema_path": "data/analysis-export.schema.json",
            "description": (
                "Gói JSON tự mô tả chứa toàn bộ dữ liệu dẫn xuất quan trọng đang dùng "
                "trên website để phục vụ tái phân tích bằng phần mềm hoặc AI."
            ),
        },
    }
    analysis_export = _build_analysis_export(
        manifest=manifest,
        source_summary=source_summary,
        product_reports=product_reports,
        prediction_report=prediction_report,
        audit_summary=audit_summary,
        audit_events=audit_events,
        dataset_quality=dataset_quality,
        snapshot_manifest=snapshot_manifest,
    )
    _write_json(site_dir / "data" / "dataset-quality.json", dataset_quality)
    _write_json(site_dir / "data" / "snapshot-manifest.json", snapshot_manifest)
    _write_json(site_dir / "data" / "analysis-export.schema.json", ANALYSIS_EXPORT_SCHEMA)
    _write_json(site_dir / "data" / "analysis-export.json", analysis_export)
    _write_json(site_dir / "data" / "manifest.json", manifest)
    return manifest


def _build_analysis_export(
    *,
    manifest: dict[str, object],
    source_summary: dict[str, object],
    product_reports: list[dict[str, object]],
    prediction_report: dict[str, object],
    audit_summary: dict[str, object],
    audit_events: list[dict[str, object]],
    dataset_quality: dict[str, object],
    snapshot_manifest: dict[str, object],
) -> dict[str, object]:
    raw_catalog = [
        {"path": path, **details}
        for path, details in snapshot_manifest.get("files", {}).items()
        if path.startswith(("draws/", "prizes/"))
    ]
    return {
        "schema_version": 2,
        "export_type": "vietlott_research_analysis",
        "language": "vi",
        "generated_from_dataset_at": manifest["generated_from_dataset_at"],
        "purpose": (
            "Một điểm vào duy nhất cho phân tích dữ liệu, kiểm tra phương pháp, "
            "đối chiếu backtest và đọc sổ dự đoán. Không phải khuyến nghị mua vé."
        ),
        "manifest": manifest,
        "dataset_summary": source_summary,
        "dataset_quality": dataset_quality,
        "snapshot_manifest": snapshot_manifest,
        "data_dictionary": {
            "product_reports": (
                "Báo cáo đầy đủ theo sản phẩm gồm thống kê mô tả, tần suất, độ vắng, "
                "mùa vụ, thời tiết, giải thưởng, backtest và kiểm định công bằng."
            ),
            "predictions": (
                "Sổ dự đoán đã lưu trước, kết quả đối chiếu, trạng thái đúng, gần đúng, "
                "sai và các chỉ số trùng một phần."
            ),
            "audit_summary": (
                "Kết quả tổng hợp của bộ kiểm định công bằng thống kê sau hiệu chỉnh "
                "Benjamini-Hochberg ở cả phạm vi sản phẩm và toàn hệ thống."
            ),
            "audit_events": (
                "Nhật ký phẳng của từng phép kiểm để lọc theo sản phẩm, phương pháp, "
                "trạng thái, p-value, q-value và kích thước hiệu ứng."
            ),
            "backtest": (
                "Walk-forward theo thời gian. Mỗi kỳ chỉ dùng lịch sử trước kỳ đó và "
                "so sánh với kỳ vọng chính xác của cách chọn đồng đều."
            ),
            "raw_draws": (
                "Dữ liệu kỳ quay gốc không nhúng vào gói này vì có hàng trăm nghìn dòng. "
                "Dùng danh mục source_files để tải CSV phân vùng khi cần phân tích cấp kỳ."
            ),
        },
        "methodology": {
            "versions": METHODOLOGY_VERSIONS,
            "backtest": {
                "method": "walk_forward",
                "candidate_strategies": [
                    "balanced_signal",
                    "recent_frequency",
                    "audit_signal",
                ],
                "baseline": "uniform_exact_expectation",
                "baseline_methods": {
                    "number_set": "exact_hypergeometric_expectation",
                    "digit_sequence": "exact_sequence_enumeration",
                },
                "score_formula_field": "product_reports[*].backtest.score_formulas",
                "partial_match_baseline_field": (
                    "product_reports[*].backtest.baseline.partial_match_baseline"
                ),
                "score_units": {
                    "number_set": "main_number_hits_per_draw",
                    "digit_sequence": "best_position_matches_per_draw",
                },
                "multiple_testing": {
                    "method": "benjamini_hochberg",
                    "scope": "all completed product-strategy comparisons",
                    "alpha": 0.05,
                },
                "target_scope_validation": manifest.get("backtest_summary", {}).get(
                    "target_scope_validation",
                    {},
                ),
                "win_rule": "mean_difference > 0 and global_bh_q < 0.05",
                "important_limitations": [
                    "Điểm backtest tập số hiện chỉ tính số chính, chưa tính số đặc biệt.",
                    "p-value dùng xấp xỉ chuẩn trên chuỗi chênh lệch theo kỳ.",
                    "Backtest quá khứ không thay thế dự đoán đã đóng băng trước kỳ quay.",
                ],
            },
            "fairness_audit": {
                "suite_version": audit_summary["suite_version"],
                "multiple_testing": "Benjamini-Hochberg trong bộ kiểm định được công bố",
                "multiple_testing_details": audit_summary.get("multiple_testing", {}),
                "dependency_families": audit_summary.get("dependency_families", []),
                "dependency_matrix": audit_summary.get("dependency_matrix", {}),
                "effect_thresholds": audit_summary.get("effect_thresholds", []),
                "threshold_sensitivity": audit_summary.get("threshold_sensitivity", {}),
                "interpretation": (
                    "Tín hiệu thống kê chỉ cho biết dữ liệu cần theo dõi hoặc đọc kỹ hơn; "
                    "không tự chứng minh nguyên nhân vận hành hay gian lận."
                ),
            },
        },
        "source_files": {
            "draws": "https://github.com/NhanAZ/vietlott-data-research/tree/main/datasets/draws",
            "prizes": "https://github.com/NhanAZ/vietlott-data-research/tree/main/datasets/prizes",
            "weather": (
                "https://github.com/NhanAZ/vietlott-data-research/blob/main/"
                "datasets/weather/daily.csv"
            ),
            "prediction_ledger": (
                "https://github.com/NhanAZ/vietlott-data-research/blob/main/"
                "predictions/ledger.jsonl"
            ),
            "implementation": (
                "https://github.com/NhanAZ/vietlott-data-research/tree/main/"
                "src/vietlott_analytics"
            ),
            "quality_report": (
                "https://github.com/NhanAZ/vietlott-data-research/blob/main/"
                "datasets/metadata/quality-report.json"
            ),
            "snapshot_manifest": (
                "https://github.com/NhanAZ/vietlott-data-research/blob/main/"
                "datasets/metadata/snapshot-manifest.json"
            ),
        },
        "raw_data_catalog": raw_catalog,
        "product_reports": {
            str(report["product"]["slug"]): report for report in product_reports
        },
        "predictions": prediction_report,
        "audit_summary": audit_summary,
        "audit_events": audit_events,
    }


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


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}
