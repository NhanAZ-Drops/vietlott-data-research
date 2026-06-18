from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from datetime import date, timedelta

import pytest

from vietlott_analytics.catalog import PRODUCTS
from vietlott_analytics.io import Observation, ProductDataset
from vietlott_analytics.predictions import (
    PredictionLedger,
    _digit_uniform_expectation,
    build_backtest_report,
    finalize_backtests,
)


def _dataset(draws: int) -> ProductDataset:
    product = PRODUCTS["mega645"]
    start = date(2024, 1, 1)
    observations = [
        Observation(
            draw_id=str(index + 1).zfill(5),
            draw_date=start + timedelta(days=index),
            values=tuple(sorted({((index * 3 + offset * 8) % 45) + 1 for offset in range(6)})),
        )
        for index in range(draws)
    ]
    return ProductDataset(
        product=product,
        observations=observations,
        source_counts=Counter({"vietlott.vn": draws}),
        status_counts=Counter({"confirmed": draws}),
        validation_counts=Counter({"valid": draws}),
        latest_fetched_at=f"2024-03-{min(draws, 28):02d}T00:00:00+00:00",
    )


def _digit_dataset(draws: int) -> ProductDataset:
    product = PRODUCTS["max3d"]
    start = date(2024, 1, 1)
    observations = [
        Observation(
            draw_id=str(index + 1).zfill(5),
            draw_date=start + timedelta(days=index),
            outcomes=(
                f"{index % 10}{(index + 3) % 10}{(index + 7) % 10}",
                f"{(index + 5) % 10}{(index + 1) % 10}{(index + 8) % 10}",
            ),
        )
        for index in range(draws)
    ]
    return ProductDataset(
        product=product,
        observations=observations,
        source_counts=Counter({"vietlott.vn": draws}),
        status_counts=Counter({"confirmed": draws}),
        validation_counts=Counter({"valid": draws}),
        latest_fetched_at=f"2024-03-{min(draws, 28):02d}T00:00:00+00:00",
    )


def test_prediction_ledger_is_idempotent_and_appends_evaluations(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = PredictionLedger.load(path)
    ledger.process_product(_dataset(40))
    original_predictions = [
        event.copy() for event in ledger.events if event["event_type"] == "prediction"
    ]
    assert len(original_predictions) == 4
    assert {event["strategy"] for event in original_predictions} == {
        "audit_signal",
        "balanced_signal",
        "recent_frequency",
        "uniform_seeded",
    }

    ledger.process_product(_dataset(40))
    assert len(ledger.events) == 4

    ledger.process_product(_dataset(41))
    predictions = [event for event in ledger.events if event["event_type"] == "prediction"]
    evaluations = [event for event in ledger.events if event["event_type"] == "evaluation"]
    assert len(predictions) == 8
    assert len(evaluations) == 4
    assert predictions[:4] == original_predictions
    assert all(event["actual_draw_id"] == "00041" for event in evaluations)
    report = ledger.site_report()
    assert report["schema_version"] == 2
    assert report["evaluation_count"] == 4
    assert report["outcome_summary"]["exact"] == 0
    assert report["product_outcomes"]["mega645"]["evaluated_predictions"] == 4
    assert report["history_limit_per_product"] == 100
    assert len(report["archived_evaluations"]) == report["evaluation_count"] == 4
    assert report["archived_evaluations"][0]["actual_draw_id"] == "00041"
    assert len(report["pending_predictions"]) == report["pending_count"] == 4
    assert report["pending_predictions"][0]["prediction"]
    assert report["pending_predictions"][0]["prediction_generated_at"]
    assert report["recent_evaluations"][0]["prediction"]
    assert report["recent_evaluations"][0]["prediction_generated_at"]
    assert report["recent_evaluations"][0]["outcome"]["status"] in {
        "exact",
        "near",
        "wrong",
    }

    ledger.save()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 12
    saved = [json.loads(line) for line in lines]
    assert all(event["event_type"] in {"prediction", "evaluation"} for event in saved)
    assert all(len(event["event_hash"]) == 64 for event in saved)
    assert saved[0]["previous_event_hash"] is None
    assert saved[-1]["ledger_index"] == 11
    reloaded = PredictionLedger.load(path)
    assert reloaded.validate_integrity()["status"] == "valid"
    assert reloaded.site_report()["ledger_integrity"]["root_hash"] == saved[-1]["event_hash"]


def test_prediction_ledger_detects_historical_tampering(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = PredictionLedger.load(path)
    ledger.process_product(_dataset(40))
    ledger.save()

    events = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    events[1]["prediction"]["numbers"][0] = 45
    path.write_text(
        "\n".join(
            json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for event in events
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="hash mismatch"):
        PredictionLedger.load(path)


@pytest.mark.parametrize("mutation", ["delete", "insert", "append_unsealed"])
def test_prediction_ledger_detects_structural_tampering(tmp_path, mutation) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = PredictionLedger.load(path)
    ledger.process_product(_dataset(40))
    ledger.save()
    events = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]

    if mutation == "delete":
        events.pop(1)
    elif mutation == "insert":
        events.insert(1, events[0].copy())
    else:
        events.append({"event_type": "prediction", "prediction_id": "unsealed"})

    path.write_text(
        "\n".join(
            json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for event in events
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        PredictionLedger.load(path)


def test_history_fingerprint_covers_all_observations() -> None:
    original = _dataset(40)
    changed = _dataset(40)
    first = changed.observations[0]
    changed.observations[0] = Observation(
        draw_id=first.draw_id,
        draw_date=first.draw_date,
        values=(1, 2, 3, 4, 5, 45),
    )

    assert original.fingerprint == changed.fingerprint
    assert original.history_fingerprint != changed.history_fingerprint


def test_walk_forward_backtest_reports_uniform_baseline() -> None:
    report = build_backtest_report(_dataset(160))

    assert report["status"] == "complete"
    assert report["method"] == "walk_forward"
    assert report["samples"] > 0
    target_scope = report["target_scope"]
    assert target_scope["method"] == "same_confirmed_draw_targets_for_all_strategies"
    assert target_scope["target_draw_count"] == report["samples"]
    assert target_scope["first_target_draw_id"] == report["first_test_draw_id"]
    assert target_scope["latest_target_draw_id"] == report["latest_test_draw_id"]
    assert target_scope["no_strategy_specific_filtering"] is True
    assert report["baseline"]["strategy"] == "uniform_exact_expectation"
    assert report["baseline"]["method"] == "exact_hypergeometric_expectation"
    assert report["baseline"]["average_hits"] == 0.8
    partial_baseline = report["baseline"]["partial_match_baseline"]
    assert partial_baseline["method"] == "exact_hypergeometric_distribution"
    assert partial_baseline["score_basis"] == "main_number_hits"
    assert partial_baseline["samples"] == report["samples"]
    assert partial_baseline["partial_match_rule"] == "0 < hit_count_t < pick_count"
    assert partial_baseline["partial_match_probability"] == pytest.approx(
        sum(
            row["probability"]
            for row in report["baseline"]["hit_distribution"]
            if 0 < row["hits"] < report["baseline"]["partial_match_baseline"]["pick_count"]
        )
    )
    assert (
        partial_baseline["expected_partial_match_count"]
        > partial_baseline["expected_near_count"]
        > partial_baseline["expected_exact_count"]
    )
    formulas = report["score_formulas"]
    assert formulas["product_kind"] == "number_set"
    assert formulas["score_unit"] == "main_number_hits_per_draw"
    assert formulas["comparison_metric"] == "mean_hit_difference"
    assert formulas["special_numbers_policy"] == "special_numbers_not_scored_in_backtest"
    assert {row["strategy"] for row in formulas["strategies"]} == {
        "balanced_signal",
        "recent_frequency",
        "audit_signal",
    }
    assert any(
        "(overdue_ratio - 1)" in row["formula"]
        for row in formulas["strategies"]
    )
    assert report["recent_model"]["strategy"] == "recent_frequency"
    assert report["audit_model"]["strategy"] == "audit_signal"
    assert "recent_comparison" in report
    assert "audit_comparison" in report
    assert "approximate_p_value" in report["comparison"]
    assert report["comparison"]["confidence_level"] == 0.95
    assert (
        report["comparison"]["confidence_interval_lower"]
        <= report["comparison"]["mean_hit_difference"]
        <= report["comparison"]["confidence_interval_upper"]
    )
    assert report["comparison"]["beats_baseline"] is False
    for key in (
        "model",
        "recent_model",
        "audit_model",
        "baseline",
        "comparison",
        "recent_comparison",
        "audit_comparison",
    ):
        assert report[key]["target_scope_id"] == target_scope["scope_id"]
        assert report[key]["target_draw_count"] == target_scope["target_draw_count"]


def test_digit_walk_forward_backtest_reports_digit_score_formula() -> None:
    report = build_backtest_report(_digit_dataset(160))

    assert report["status"] == "complete"
    assert report["baseline"]["method"] == "exact_sequence_enumeration"
    partial_baseline = report["baseline"]["partial_match_baseline"]
    assert partial_baseline["method"] == "exact_sequence_enumeration"
    assert partial_baseline["score_basis"] == "best_position_matches"
    assert partial_baseline["samples"] == report["samples"]
    assert partial_baseline["candidate_space_size"] == 1000
    assert (
        partial_baseline["partial_match_rule"]
        == "0 < best_position_matches_t < sequence_length"
    )
    assert partial_baseline["expected_partial_match_count"] > partial_baseline[
        "expected_exact_count"
    ]
    assert 0 < partial_baseline["zero_match_probability"] < 1
    formulas = report["score_formulas"]
    assert formulas["product_kind"] == "digit_sequence"
    assert formulas["score_unit"] == "best_position_matches_per_draw"
    assert formulas["comparison_metric"] == "mean_position_match_difference"
    assert "max_actual" in formulas["per_draw_score"]
    assert "actual outcomes_t" in formulas["comparison_difference"]
    assert {row["strategy"] for row in formulas["strategies"]} == {
        "balanced_signal",
        "recent_frequency",
        "audit_signal",
    }
    assert all("selection_rule" in row for row in formulas["strategies"])


def test_digit_uniform_expectation_enumerates_complete_space() -> None:
    expected, exact_probability, distribution = _digit_uniform_expectation(
        {"111"},
        [1, 2],
        3,
    )

    assert expected == 1.5
    assert exact_probability == 0.125
    assert distribution == {
        0: 0.125,
        1: 0.375,
        2: 0.375,
        3: 0.125,
    }


def test_finalize_backtests_applies_global_bh_correction() -> None:
    scope = {
        "scope_id": "scope-a",
        "target_draw_count": 10,
        "target_draw_ids_sha256": "a" * 64,
    }
    reports = [
        {
            "product": {"slug": "first"},
            "backtest": {
                "status": "complete",
                "target_scope": scope,
                "comparison": {
                    "mean_hit_difference": 0.1,
                    "approximate_p_value": 0.01,
                    "target_scope_id": "scope-a",
                    "target_draw_count": 10,
                },
                "audit_comparison": {
                    "mean_hit_difference": 0.1,
                    "approximate_p_value": 0.04,
                    "target_scope_id": "scope-a",
                    "target_draw_count": 10,
                },
            },
        },
        {
            "product": {"slug": "second"},
            "backtest": {
                "status": "complete",
                "target_scope": scope,
                "comparison": {
                    "mean_position_match_difference": 0.1,
                    "approximate_p_value": 0.06,
                    "target_scope_id": "scope-a",
                    "target_draw_count": 10,
                },
                "audit_comparison": {
                    "mean_position_match_difference": -0.1,
                    "approximate_p_value": 0.001,
                    "target_scope_id": "scope-a",
                    "target_draw_count": 10,
                },
            },
        },
    ]

    summary = finalize_backtests(reports)

    assert summary["comparison_count"] == 4
    assert summary["target_scope_validation"]["status"] == "validated"
    assert summary["target_scope_validation"]["product_count"] == 2
    assert summary["unadjusted_winning_comparisons"] == 2
    assert summary["adjusted_winning_comparisons"] == 1
    assert summary["products_with_adjusted_win"] == ["first"]
    assert reports[0]["backtest"]["comparison"]["q_value_global_bh"] == 0.02
    assert reports[0]["backtest"]["comparison"]["beats_baseline"] is True
    assert reports[0]["backtest"]["audit_comparison"]["beats_baseline"] is False
    assert reports[1]["backtest"]["audit_comparison"]["beats_baseline"] is False


def test_finalize_backtests_rejects_target_scope_mismatch() -> None:
    report = build_backtest_report(_dataset(160))
    broken = deepcopy(report)
    broken["recent_comparison"]["target_scope_id"] = "different-scope"

    with pytest.raises(ValueError, match="target_scope_id mismatch"):
        finalize_backtests([{"product": {"slug": "mega645"}, "backtest": broken}])


def test_prediction_report_prefers_newer_model_for_same_cutoff(tmp_path) -> None:
    older = {
        "event_type": "prediction",
        "prediction_id": "older-model",
        "product": "mega645",
        "strategy": "balanced_signal",
        "strategy_label": "balanced",
        "model_version": "1.0.0",
        "generated_at": "2026-06-14T12:00:00+00:00",
        "dataset_cutoff_draw_id": "00100",
        "dataset_cutoff_date": "2026-06-13",
        "dataset_fingerprint": "same-cutoff",
        "target": "first_confirmed_draw_after_cutoff",
        "prediction": {"numbers": [1, 2, 3, 4, 5, 6], "special_numbers": []},
        "parameters": {"selection_count": 6},
        "research_only": True,
    }
    newer = {
        **older,
        "prediction_id": "newer-model",
        "model_version": "1.1.0",
        "generated_at": "2026-06-13T12:00:00+00:00",
        "prediction": {"numbers": [7, 8, 9, 10, 11, 12], "special_numbers": []},
    }

    report = PredictionLedger(
        path=tmp_path / "ledger.jsonl",
        events=[older, newer],
    ).site_report()

    [latest] = report["latest"]["mega645"]
    assert latest["prediction_id"] == "newer-model"
    assert latest["prediction"]["numbers"] == [7, 8, 9, 10, 11, 12]
    assert {row["prediction_id"] for row in report["pending_predictions"]} == {
        "newer-model",
        "older-model",
    }


def test_prediction_report_uses_strict_exact_and_near_rules(tmp_path) -> None:
    base_prediction = {
        "event_type": "prediction",
        "product": "mega645",
        "strategy": "balanced_signal",
        "strategy_label": "Tín hiệu cân bằng",
        "model_version": "1.0.0",
        "generated_at": "2026-06-13T12:00:00+00:00",
        "dataset_cutoff_draw_id": "00100",
        "dataset_cutoff_date": "2026-06-13",
        "dataset_fingerprint": "frozen",
        "prediction": {
            "numbers": [1, 2, 3, 4, 5, 6],
            "special_numbers": [],
        },
        "parameters": {"selection_count": 6},
    }
    actuals = (
        ("exact", [1, 2, 3, 4, 5, 6]),
        ("near", [1, 2, 3, 4, 5, 7]),
        ("wrong", [1, 8, 9, 10, 11, 12]),
    )
    events = []
    for index, (expected_status, actual_numbers) in enumerate(actuals):
        prediction_id = f"prediction-{index}"
        events.append({**base_prediction, "prediction_id": prediction_id})
        events.append(
            {
                "event_type": "evaluation",
                "evaluation_id": f"evaluation-{index}",
                "prediction_id": prediction_id,
                "product": "mega645",
                "strategy": "balanced_signal",
                "model_version": "1.0.0",
                "evaluated_at": "2026-06-14T12:00:00+00:00",
                "actual_draw_id": f"0010{index + 1}",
                "actual_draw_date": "2026-06-14",
                "actual_result": {
                    "numbers": actual_numbers,
                    "special_numbers": [],
                },
                "metrics": {
                    "exact_hit": expected_status == "exact",
                    "hit_count": len(
                        set(base_prediction["prediction"]["numbers"])
                        & set(actual_numbers)
                    ),
                    "special_hit_count": 0,
                },
            }
        )

    report = PredictionLedger(path=tmp_path / "ledger.jsonl", events=events).site_report()

    summary = report["outcome_summary"]
    assert summary["evaluated_draws"] == 3
    assert summary["evaluated_predictions"] == 3
    assert summary["exact"] == 1
    assert summary["near"] == 1
    assert summary["wrong"] == 1
    assert summary["partial_matches"] == 2
    assert summary["zero_matches"] == 0
    assert summary["expected_exact_by_chance"] > 0
    assert summary["expected_near_by_chance"] > summary["expected_exact_by_chance"]
    assert summary["near_excess_vs_chance"] > 0

    product_outcome = report["product_outcomes"]["mega645"]
    assert product_outcome["evaluated_draws"] == 3
    assert product_outcome["evaluated_predictions"] == 3
    assert product_outcome["exact"] == 1
    assert product_outcome["near"] == 1
    assert product_outcome["wrong"] == 1
    assert product_outcome["partial_matches"] == 2
    assert product_outcome["zero_matches"] == 0
    assert product_outcome["score_kind"] == "numbers"
    assert product_outcome["expected_near_by_chance"] == summary["expected_near_by_chance"]
    assert product_outcome["score_distribution"] == [
        {"score": 1, "count": 1},
        {"score": 5, "count": 1},
        {"score": 6, "count": 1},
    ]
    statuses = {
        evaluation["prediction_id"]: evaluation["outcome"]["status"]
        for evaluation in report["recent_evaluations"]
    }
    assert len(report["archived_evaluations"]) == 3
    assert statuses == {
        "prediction-0": "exact",
        "prediction-1": "near",
        "prediction-2": "wrong",
    }
    near_row = next(
        evaluation
        for evaluation in report["recent_evaluations"]
        if evaluation["outcome"]["status"] == "near"
    )
    assert (
        near_row["outcome"]["baseline_probability"]["near"]
        > near_row["outcome"]["baseline_probability"]["exact"]
    )


def test_digit_near_probability_accounts_for_multiple_prize_outcomes(tmp_path) -> None:
    outcomes = [
        "312",
        "097",
        "756",
        "585",
        "958",
        "008",
        "795",
        "713",
        "998",
        "953",
        "307",
        "449",
        "849",
        "207",
        "137",
        "038",
        "017",
        "198",
        "436",
        "401",
    ]
    prediction = {
        "event_type": "prediction",
        "prediction_id": "max3dpro-prediction",
        "product": "max3dpro",
        "strategy": "balanced_signal",
        "strategy_label": "balanced",
        "model_version": "1.3.0",
        "generated_at": "2026-06-13T19:25:04+00:00",
        "dataset_cutoff_draw_id": "00739",
        "dataset_cutoff_date": "2026-06-13",
        "dataset_fingerprint": "frozen",
        "prediction": {"sequence": "015"},
        "parameters": {"sequence_length": 3},
    }
    evaluation = {
        "event_type": "evaluation",
        "evaluation_id": "max3dpro-evaluation",
        "prediction_id": "max3dpro-prediction",
        "product": "max3dpro",
        "strategy": "balanced_signal",
        "model_version": "1.3.0",
        "evaluated_at": "2026-06-16T11:32:02+00:00",
        "actual_draw_id": "00740",
        "actual_draw_date": "2026-06-16",
        "actual_result": {"outcomes": outcomes},
        "metrics": {
            "exact_hit": False,
            "best_position_matches": 2,
        },
    }

    report = PredictionLedger(
        path=tmp_path / "ledger.jsonl",
        events=[prediction, evaluation],
    ).site_report()

    [row] = report["recent_evaluations"]
    baseline = row["outcome"]["baseline_probability"]
    assert row["outcome"]["status"] == "near"
    assert baseline["actual_outcomes"] == 20
    assert baseline["candidate_space_size"] == 1000
    assert baseline["exact"] == 0.02
    assert baseline["near"] == 0.401
    assert report["product_outcomes"]["max3dpro"]["expected_near_by_chance"] == 0.401
