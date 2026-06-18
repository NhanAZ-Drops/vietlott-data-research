from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_static_site_has_required_pages_and_local_assets() -> None:
    index = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    method_page = (ROOT / "site" / "phuong-phap.html").read_text(encoding="utf-8")
    data_page = (ROOT / "site" / "du-lieu.html").read_text(encoding="utf-8")
    styles = (ROOT / "site" / "assets" / "styles.css").read_text(encoding="utf-8")
    app_script = (ROOT / "site" / "assets" / "app.js").read_text(encoding="utf-8")
    docs_script = (ROOT / "site" / "assets" / "docs.js").read_text(encoding="utf-8")
    assert 'id="phan-tich"' in index
    assert 'id="du-doan"' in index
    assert 'id="kiem-dinh"' in index
    assert "assets/app.js?v=20260618-7" in index
    assert "archive-summary-heading" in index
    assert "Sổ dự đoán toàn hệ thống" in index
    assert "assets/docs.js?v=20260618-2" in data_page
    for page in (index, method_page, data_page):
        assert "assets/styles.css?v=20260618-6" in page
        assert "assets/favicon.svg?v=20260614-9" in page
        assert "fonts.googleapis.com/css2?family=Noto+Serif" in page
        assert "cdn-uicons.flaticon.com/3.0.0" in page
        assert "fi-rr-crystal-ball" in page
        assert "Biểu tượng từ UIcons by Flaticon" in page
    assert "[hidden]" in styles
    assert "display: none !important" in styles
    assert "min-height: 72px" in styles
    assert "archive-summary-heading" in styles
    assert "archive-overview-grid" in styles
    assert "prediction-latest-panel" in styles
    assert "backtest-prize-grid" in index
    assert ".backtest-prize-grid" in styles
    assert ".backtest-prize-grid .prize-report" in styles
    assert ".prediction-latest-panel:not([open]) > .prediction-latest-list" in styles
    assert '--font-display: "Noto Serif"' in styles
    assert "Georgia" not in styles
    assert "Cambria" not in styles
    assert '.normalize("NFC")' in app_script
    assert '.normalize("NFC")' in docs_script
    assert "Chọn ngẫu nhiên có thể lặp lại" in app_script
    assert (
        "Kết luận: các chiến lược hiện tại chưa tốt hơn cách chọn đồng đều một cách đáng tin cậy."
        in app_script
    )
    assert "renderFairnessAudit" in app_script
    assert "renderWeatherReport" in app_script
    assert "Thời tiết ngoài trời theo địa điểm quay" in index
    assert "datasets/weather/daily.csv" in data_page
    assert "Cách đọc p, q và độ lớn" in app_script
    assert "Ngưỡng thực dụng" in app_script
    assert "renderAuditVisualLog" in app_script
    assert "renderAuditThresholdSensitivity" in app_script
    assert "threshold_sensitivity" in app_script
    assert "renderPowerMde" in app_script
    assert "MDE 80%" in app_script
    assert "Ngưỡng đủ công suất" in app_script
    assert "renderPermutationCheck" in app_script
    assert "Permutation p" in app_script
    assert "Hoán vị nguyên đơn vị" in app_script
    assert "audit-permutation-note" in styles
    assert "renderBlockBootstrapCheck" in app_script
    assert "Block bootstrap 95%" in app_script
    assert "audit-bootstrap-note" in styles
    assert "renderChangePointScan" in app_script
    assert "Change-point scan" in app_script
    assert "p Bonferroni" in app_script
    assert "audit-change-point-note" in styles
    assert "renderAuditDependencyMatrix" in app_script
    assert "Ma trận phụ thuộc" in app_script
    assert "q theo họ" in app_script
    assert "audit-dependency-panel" in styles
    assert "audit-dependency-grid" in styles
    assert "renderAuditPositionResiduals" in app_script
    assert "renderAuditTierBreakdown" in app_script
    assert "renderAuditPeriodBreakdown" in app_script
    assert "renderAuditSourceBreakdown" in app_script
    assert "renderAuditSourceLeaveOneOut" in app_script
    assert "renderAuditReliabilityPanel" in app_script
    assert "reliability_sensitivity" in app_script
    assert "Ô nào đóng góp nhiều vào độ lệch tổng?" in app_script
    assert "Phân rã residual, không tạo p-value mới" in app_script
    assert "Giai đoạn không chồng lấn" in app_script
    assert "Nguồn dữ liệu" in app_script
    assert "Độ nhạy loại nguồn" in app_script
    assert "Bỏ một nguồn thì tín hiệu đổi bao nhiêu?" in app_script
    assert "audit-reliability-panel" in styles
    assert "audit-reliability-comparisons" in styles
    assert "threshold-sensitivity-grid" in styles
    assert "position-residual-grid" in styles
    assert "position-tier-grid" in styles
    assert "position-period-grid" in styles
    assert "position-source-grid" in styles
    assert "position-source-sensitivity-grid" in styles
    assert "audit-test-details" in app_script
    assert "audit-test-list-inner" in styles
    assert 'text("ribbon-product-count"' in app_script
    assert 'text("exact-predictions"' in app_script
    assert 'text("archive-evaluated-draws"' in app_script
    assert "renderPredictionResults" in app_script
    assert "setupPredictionProductFilters" in app_script
    assert 'details class="prediction-latest-panel"' in app_script
    assert "renderPredictionArchiveDetail" in app_script
    assert "renderPendingPrediction" in app_script
    assert "audit_signal" in app_script
    assert "Khai thác kiểm định công bằng" in app_script
    assert "prediction-history-list" in index
    assert "prediction-history-label" in index
    assert "prediction-archive-detail-list" in index
    assert 'data-archive-filter="partial"' in index
    assert "archive-exact-evaluated" not in index
    assert 'data-product-filter="partial"' in app_script
    assert "Dự đoán gốc so với kết quả thật" in index
    assert "prediction-ledger-integrity" in index
    assert "Chuỗi hash hợp lệ" in app_script
    assert "backtest-evidence" in app_script
    assert "Phương pháp và công thức của báo cáo này" in app_script
    assert "q toàn hệ thống &lt; 0,05" in app_script
    assert "Baseline đồng đều chính xác" in app_script
    assert "Khoảng ước lượng 95%" in app_script
    assert "backtest-correction-summary" in index
    assert "src/vietlott_analytics/predictions.py" in app_script
    assert "Backtest đang chạy chính xác những gì" in method_page
    assert "Kiểm định chênh lệch ghép cặp" in method_page
    assert "phân bố siêu bội chính xác" in method_page
    assert "Tập kỳ mục tiêu chung" in app_script
    assert "target_scope" in app_script
    assert "renderBacktestScoreFormulas" in app_script
    assert "renderBacktestPartialBaseline" in app_script
    assert "Baseline trùng một phần" in app_script
    assert "Thước đo riêng" in app_script
    assert "Ba chiến lược ứng viên" in method_page
    assert "hiệu chỉnh Benjamini-Hochberg" in method_page
    assert "trung_bình(d) ± 1,96 × sai_số_chuẩn" in method_page
    assert "tests/test_prediction_ledger.py" in method_page
    assert "renderBacktestOverview" in app_script
    assert "tín hiệu qua hiệu chỉnh" in app_script
    assert "tín hiệu thô" in app_script
    assert "Xem chi tiết 8 báo cáo backtest" in index
    assert "Toàn hệ thống - khả năng dự báo" in index
    assert "Từ kết luận nhanh đến kiểm định chi tiết" in index
    assert "Bước 2 - kiểm định mở rộng" in index
    assert "audit-log-visual" in index
    assert "audit-log.jsonl" in index
    assert "audit-summary.json" in data_page
    assert "analysis-export.json" in data_page
    assert "analysis-export.schema.json" in data_page
    assert "quality-report.json" in data_page
    assert "snapshot-manifest.json" in data_page
    assert "source-quality-table" in data_page
    assert "Gói phân tích đầy đủ cho Data Analytics AI" in data_page
    assert "display: block;\n  height: 100%;" in styles
    assert "grid-template-columns: auto minmax(0, 1fr)" in styles
    assert "font-size: clamp(36px, 4.5vw, 52px);" in styles
    assert "Phiên bản phương pháp" not in index
    assert "Phiên bản cách tính" not in index
    assert "Cách tính phiên bản" not in app_script
    assert '{ cache: "no-store" }' in app_script
    assert '{ cache: "no-store" }' in docs_script
    assert (ROOT / "site" / "phuong-phap.html").exists()
    assert (ROOT / "site" / "du-lieu.html").exists()
    assert (ROOT / "site" / ".nojekyll").exists()


def test_static_site_text_is_normalized_unicode() -> None:
    text_suffixes = {".css", ".html", ".js", ".json"}
    for path in (ROOT / "site").rglob("*"):
        if path.is_file() and path.suffix.lower() in text_suffixes:
            content = path.read_text(encoding="utf-8")
            assert unicodedata.is_normalized("NFC", content), path


def test_generated_site_data_matches_manifest() -> None:
    data_root = ROOT / "site" / "data"
    manifest = json.loads((data_root / "manifest.json").read_text(encoding="utf-8"))
    predictions = json.loads((data_root / "predictions.json").read_text(encoding="utf-8"))
    audit_summary = json.loads((data_root / "audit-summary.json").read_text(encoding="utf-8"))
    audit_log = (data_root / "audit-log.jsonl").read_text(encoding="utf-8")
    analysis_export = json.loads(
        (data_root / "analysis-export.json").read_text(encoding="utf-8")
    )
    analysis_schema = json.loads(
        (data_root / "analysis-export.schema.json").read_text(encoding="utf-8")
    )
    dataset_quality = json.loads(
        (data_root / "dataset-quality.json").read_text(encoding="utf-8")
    )
    snapshot_manifest = json.loads(
        (data_root / "snapshot-manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["draw_rows"] >= manifest["confirmed_rows"]
    assert manifest["analysis_export"]["path"] == "data/analysis-export.json"
    assert manifest["backtest_summary"]["multiple_testing_method"] == "benjamini_hochberg"
    assert manifest["backtest_summary"]["comparison_count"] == 24
    target_scope_validation = manifest["backtest_summary"]["target_scope_validation"]
    assert target_scope_validation["status"] == "validated"
    assert target_scope_validation["product_count"] == len(manifest["products"])
    assert target_scope_validation["method"] == "shared_target_scope_id_per_product"
    assert predictions["model_version"]
    assert predictions["ledger_integrity"]["status"] == "valid"
    assert predictions["ledger_integrity"]["event_count"] > 0
    assert len(predictions["ledger_integrity"]["root_hash"]) == 64
    assert manifest["fairness_audit"]["test_count"] == audit_summary["summary"]["test_count"]
    assert audit_summary["suite_version"] == "2.0.0"
    assert audit_summary["dependency_families"]
    assert audit_summary["dependency_matrix"]["pairs"]
    assert audit_summary["multiple_testing"]["diagnostic_family_q"] == "q_value_dependency_family_bh"
    assert audit_summary["power_summary"]["primary_power"] == 0.8
    assert audit_log
    assert analysis_export["export_type"] == "vietlott_research_analysis"
    assert analysis_export["manifest"] == manifest
    assert analysis_export["predictions"] == predictions
    assert analysis_export["audit_summary"] == audit_summary
    assert len(analysis_export["product_reports"]) == len(manifest["products"])
    assert analysis_export["audit_events"]
    jsonschema.validate(analysis_export, analysis_schema)
    assert analysis_export["schema_version"] == 2
    assert analysis_export["dataset_quality"] == dataset_quality
    assert analysis_export["snapshot_manifest"] == snapshot_manifest
    assert manifest["draw_rows"] == dataset_quality["totals"]["draw_rows"]
    assert manifest["prize_rows"] == dataset_quality["totals"]["prize_rows"]
    assert snapshot_manifest["dataset_rows"] == {
        "draws": manifest["draw_rows"],
        "prizes": manifest["prize_rows"],
    }
    assert predictions["pending_count"] >= predictions["embedded_pending_count"]
    assert len(predictions["pending_predictions"]) == predictions["pending_count"]
    assert len(predictions["archived_evaluations"]) == predictions["evaluation_count"]
    assert predictions["pending_predictions"][0]["prediction"]
    assert predictions["archived_evaluations"][0]["outcome"]["status"] in {
        "exact",
        "near",
        "wrong",
    }
    assert sum(
        len(rows) for rows in predictions["latest"].values()
    ) == predictions["embedded_pending_count"]
    assert analysis_export["methodology"]["versions"] == manifest["methodology_versions"]
    assert analysis_export["methodology"]["fairness_audit"]["dependency_matrix"][
        "pair_definition_count"
    ] == audit_summary["dependency_matrix"]["pair_definition_count"]
    assert analysis_export["raw_data_catalog"]
    for entry in analysis_export["raw_data_catalog"]:
        assert len(entry["sha256"]) == 64
        assert entry["path"] in snapshot_manifest["files"]
    for product in manifest["products"]:
        report = json.loads(
            (data_root / "products" / f"{product['slug']}.json").read_text(encoding="utf-8")
        )
        summary_product = next(
            item for item in audit_summary["products"] if item["slug"] == product["slug"]
        )
        assert report["product"]["slug"] == product["slug"]
        assert report["summary"]["confirmed_draws"] == product["confirmed_draws"]
        assert (
            report["summary"]["data_quality"]["result_coverage_rate"]
            == product["result_coverage_rate"]
        )
        assert (
            report["summary"]["data_quality"]["prize_coverage_rate"]
            == product["prize_coverage_rate"]
        )
        assert report["audit"]["suite_version"] == "2.0.0"
        assert report["audit"]["dependency_matrix"]["pairs"]
        assert report["audit"]["power_summary"]["supported_test_count"] > 0
        reliability = report["audit"]["reliability_sensitivity"]
        assert reliability["basis"] == "draw_status plus source_verification"
        assert reliability["no_new_p_values"] is True
        assert reliability["baseline"]["audit_uses_confirmed_only"] is True
        assert (
            reliability["baseline"]["confirmed_draws_in_audit"]
            == report["audit"]["history_draws"]
        )
        assert isinstance(reliability["comparisons"], list)
        for comparison in reliability["comparisons"]:
            assert all(
                not key.startswith(("p_value", "q_value"))
                for key in comparison
            )
        assert summary_product["reliability_sensitivity"]["status"] == reliability[
            "status"
        ]
        assert summary_product["reliability_sensitivity"]["no_new_p_values"] is True
        active_tests = [
            item
            for item in report["audit"]["tests"]
            if item["status"] != "skipped"
        ]
        assert all("power_analysis" in item for item in active_tests)
        available_power = [
            item["power_analysis"]
            for item in active_tests
            if item["power_analysis"]["status"] == "available"
        ]
        assert available_power
        assert all(
            any(row["power"] == 0.8 for row in item["target_powers"])
            for item in available_power
        )
        ordered_tests = [
            item
            for item in active_tests
            if item["id"].endswith(("runs", "lag1_autocorrelation", "split_half_change"))
        ]
        assert ordered_tests
        for item in ordered_tests:
            check = item["parameters"]["permutation_check"]
            assert check["status"] == "available"
            assert check["method"] == "whole_observation_label_permutation"
            assert check["permutations"] == 499
            assert check["no_multiple_testing_decision"] is True
            assert 0 <= check["empirical_p_value"] <= 1
            bootstrap = item["parameters"]["block_bootstrap_check"]
            assert bootstrap["status"] == "available"
            assert bootstrap["method"] == "moving_block_bootstrap"
            assert bootstrap["resamples"] == 199
            assert bootstrap["preserve_time_structure"] == "contiguous_observation_blocks"
            assert bootstrap["no_multiple_testing_decision"] is True
            assert bootstrap["confidence_interval_lower"] <= bootstrap[
                "confidence_interval_upper"
            ]
            if item["id"].endswith("split_half_change"):
                scan = item["parameters"]["change_point_scan"]
                assert scan["status"] == "available"
                assert scan["method"] == "pre_registered_candidate_scan"
                assert scan["multiple_candidate_correction"] == "bonferroni"
                assert scan["candidate_count"] >= 3
                assert len(scan["candidates"]) == scan["candidate_count"]
                assert scan["adjusted_p_value"] >= scan["raw_p_value"]
                assert scan["no_unadjusted_search_decision"] is True
        if product["slug"] == "keno":
            pair_test = next(
                item
                for item in report["audit"]["tests"]
                if item["id"] == "number_pair_co_occurrence"
            )
            assert pair_test["status"] != "skipped"
            assert pair_test["degrees_of_freedom"] == 3159
            pair_parameters = pair_test["parameters"]
            assert pair_parameters["counting_method"] == "dense_pair_index_vector"
            assert pair_parameters["no_sampling"] is True
            assert pair_parameters["pairs"] == 3160
            assert pair_parameters["pair_observations"] > 50_000_000
            assert pair_parameters["observed_pair_observations"] == pair_parameters[
                "pair_observations"
            ]
            assert len(pair_parameters["top_pairs"]) == 5
        if product["slug"] in {"max3d", "max4d"}:
            position_test = next(
                item
                for item in report["audit"]["tests"]
                if item["id"] == "digit_position_chi_square"
            )
            breakdown = position_test["parameters"]["tier_breakdown"]
            assert breakdown["status"] == "available"
            assert breakdown["no_new_p_values"] is True
            assert breakdown["tiers"]
            period_breakdown = position_test["parameters"]["period_breakdown"]
            assert period_breakdown["status"] == "available"
            assert period_breakdown["no_new_p_values"] is True
            assert len(period_breakdown["segments"]) == 3
            assert all("p_value" not in segment for segment in period_breakdown["segments"])
            source_breakdown = position_test["parameters"]["source_breakdown"]
            assert source_breakdown["no_new_p_values"] is True
            assert source_breakdown["sources"]
            assert all("p_value" not in source for source in source_breakdown["sources"])
            source_leave_one_out = position_test["parameters"]["source_leave_one_out"]
            assert source_leave_one_out["method"] == "source_leave_one_out"
            assert source_leave_one_out["no_new_p_values"] is True
            assert source_leave_one_out["baseline"]["statistic"] == pytest.approx(
                position_test["statistic"],
                abs=1e-4,
            )
            if source_leave_one_out["source_count"] > 1:
                assert source_leave_one_out["excluded_sources"]
                assert all(
                    "p_value" not in source
                    for source in source_leave_one_out["excluded_sources"]
                )
            else:
                assert source_leave_one_out["status"] == "single_source"
                assert source_leave_one_out["excluded_sources"] == []
            if product["slug"] == "max4d":
                assert any(
                    row["result_type"] == "wildcard_prefix"
                    and row["usable_for_position_audit"] is False
                    for row in breakdown["result_types"]
                )
        assert report["backtest"]["recent_model"]["strategy"] == "recent_frequency"
        assert "recent_comparison" in report["backtest"]
        formulas = report["backtest"]["score_formulas"]
        assert formulas["product_kind"] == product["kind"]
        assert formulas["per_draw_score"]
        assert formulas["comparison_difference"]
        assert {row["strategy"] for row in formulas["strategies"]} == {
            "balanced_signal",
            "recent_frequency",
            "audit_signal",
        }
        if product["kind"] == "number_set":
            assert formulas["score_unit"] == "main_number_hits_per_draw"
            assert formulas["comparison_metric"] == "mean_hit_difference"
            assert (
                formulas["special_numbers_policy"]
                == "special_numbers_not_scored_in_backtest"
            )
        else:
            assert formulas["score_unit"] == "best_position_matches_per_draw"
            assert formulas["comparison_metric"] == "mean_position_match_difference"
            assert "multi_outcome_policy" in formulas
        partial_baseline = report["backtest"]["baseline"]["partial_match_baseline"]
        assert partial_baseline["samples"] == report["backtest"]["samples"]
        assert partial_baseline["expected_partial_match_count"] >= 0
        assert partial_baseline["expected_zero_match_count"] >= 0
        assert 0 <= partial_baseline["partial_match_probability"] <= 1
        assert 0 <= partial_baseline["zero_match_probability"] <= 1
        if product["kind"] == "number_set":
            assert partial_baseline["method"] == "exact_hypergeometric_distribution"
            assert partial_baseline["score_basis"] == "main_number_hits"
        else:
            assert partial_baseline["method"] == "exact_sequence_enumeration"
            assert partial_baseline["score_basis"] == "best_position_matches"
            assert partial_baseline["multi_outcome_policy"]
        target_scope = report["backtest"]["target_scope"]
        assert target_scope["method"] == "same_confirmed_draw_targets_for_all_strategies"
        assert target_scope["target_draw_count"] == report["backtest"]["samples"]
        assert target_scope["no_strategy_specific_filtering"] is True
        assert len(target_scope["target_draw_ids_sha256"]) == 64
        for key in (
            "model",
            "recent_model",
            "audit_model",
            "baseline",
            "comparison",
            "recent_comparison",
            "audit_comparison",
        ):
            assert report["backtest"][key]["target_scope_id"] == target_scope[
                "scope_id"
            ]
            assert report["backtest"][key]["target_draw_count"] == target_scope[
                "target_draw_count"
            ]
