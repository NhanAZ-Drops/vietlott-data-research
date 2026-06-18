from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

import pytest

from vietlott_analytics.catalog import PRODUCTS
from vietlott_analytics.fairness import (
    EFFECT_THRESHOLD_REGISTRY,
    audit_log_events,
    build_product_audit,
    finalize_audits,
)
from vietlott_analytics.io import Observation, ProductDataset, TieredOutcome


def test_number_audit_contains_lightweight_fairness_tests() -> None:
    product = PRODUCTS["mega645"]
    observations = [
        Observation(
            draw_id=str(index + 1).zfill(5),
            draw_date=date(2024, 1, 1) + timedelta(days=index),
            values=tuple(sorted({((index + offset * 11) % 45) + 1 for offset in range(6)})),
        )
        for index in range(90)
    ]
    dataset = ProductDataset(
        product=product,
        observations=observations,
        source_counts=Counter({"vietlott.vn": 90}),
        status_counts=Counter({"confirmed": 90}),
        validation_counts=Counter({"valid": 90}),
    )

    audit = build_product_audit(dataset)

    assert audit["suite_version"] == "2.0.0"
    assert audit["history_draws"] == 90
    assert audit["audit_interval_draws"] == 25
    assert {test["id"] for test in audit["tests"]} >= {
        "number_marginal_chi_square",
        "number_marginal_g_test",
        "number_sum_runs",
        "number_sum_lag1_autocorrelation",
        "number_current_gap_geometric",
    }
    assert all("interpretation" in test for test in audit["tests"])
    assert all("statistically_notable" in test for test in audit["tests"])
    assert all("practically_large" in test for test in audit["tests"])
    assert all("q_value_bh" in test for test in audit["tests"] if test["p_value"] is not None)
    assert all("dependency_family" in test for test in audit["tests"])
    assert all("dependency_family_label" in test for test in audit["tests"])
    assert all(
        "q_value_dependency_family_bh" in test
        for test in audit["tests"]
        if test["p_value"] is not None
    )
    assert audit["dependency_families"]
    assert audit["multiple_testing"]["diagnostic_family_q"] == "q_value_dependency_family_bh"
    assert audit["dependency_matrix"]["pairs"]
    assert audit["dependency_matrix"]["counts"]["high"] >= 1
    registered_thresholds = {entry["id"] for entry in EFFECT_THRESHOLD_REGISTRY}
    active_tests = [test for test in audit["tests"] if test["status"] != "skipped"]
    assert all(test["effect_threshold_id"] in registered_thresholds for test in active_tests)
    assert all(entry["unit"] for entry in audit["effect_thresholds"])
    assert all(entry["scope"] for entry in audit["effect_thresholds"])
    assert all(entry["reference_or_rationale"] for entry in audit["effect_thresholds"])
    assert all(entry["sensitivity_method"] for entry in audit["effect_thresholds"])


def test_finalize_audits_adds_global_correction_and_jsonl_events() -> None:
    product = PRODUCTS["bingo18"]
    observations = [
        Observation(
            draw_id=str(index + 1).zfill(7),
            draw_date=date(2025, 1, 1) + timedelta(days=index // 10),
            outcomes=(
                f"{index % 6 + 1}{(index + 3) % 6 + 1}{(index + 5) % 6 + 1}",
            ),
        )
        for index in range(120)
    ]
    dataset = ProductDataset(
        product=product,
        observations=observations,
        source_counts=Counter({"vietlott.vn": 120}),
        status_counts=Counter({"confirmed": 120}),
        validation_counts=Counter({"valid": 120}),
    )
    report = {
        "product": {"slug": product.slug, "name": product.name},
        "audit": build_product_audit(dataset),
    }

    summary = finalize_audits([report])
    events = list(audit_log_events([report]))

    assert summary["summary"]["product_count"] == 1
    assert summary["summary"]["test_count"] == len(report["audit"]["tests"])
    assert summary["effect_thresholds"]
    assert summary["dependency_families"]
    assert summary["dependency_matrix"]["pairs"]
    assert summary["multiple_testing"]["primary_decision_q"] == "q_value_global_bh"
    assert summary["threshold_sensitivity"]["method"] == "threshold_multiplier_sweep"
    assert summary["threshold_sensitivity"]["multipliers"] == [0.5, 1.0, 1.5, 2.0]
    assert any(
        entry["test_count"] > 0
        for entry in summary["threshold_sensitivity"]["by_threshold"]
    )
    assert events
    assert {event["event_type"] for event in events} == {"fairness_audit_test"}
    assert all("dependency_family" in event for event in events)
    assert any(event["q_value_dependency_family_bh"] is not None for event in events)
    assert all(
        "q_value_global_bh" in test
        for test in report["audit"]["tests"]
        if test["p_value"] is not None
    )
    assert set(summary["summary"]["status_counts"]) <= {
        "pass",
        "statistically_notable",
        "practically_large",
        "both",
        "skipped",
    }
    position_test = next(
        item
        for item in report["audit"]["tests"]
        if item["id"] == "digit_position_chi_square"
    )
    residuals = position_test["parameters"]["position_residuals"]
    assert len(residuals) == 18
    assert sum(item["chi_square_contribution"] for item in residuals) == pytest.approx(
        position_test["statistic"],
        abs=1e-4,
    )
    period_breakdown = position_test["parameters"]["period_breakdown"]
    assert period_breakdown["status"] == "available"
    assert period_breakdown["no_new_p_values"] is True
    assert period_breakdown["segment_count"] == 3
    assert [segment["draws"] for segment in period_breakdown["segments"]] == [40, 40, 40]
    assert all("p_value" not in segment for segment in period_breakdown["segments"])
    assert all(segment["top_residuals"] for segment in period_breakdown["segments"])
    assert all(
        "p_value" not in residual
        for segment in period_breakdown["segments"]
        for residual in segment["top_residuals"]
    )
    assert int(period_breakdown["segments"][0]["end_draw_id"]) < int(
        period_breakdown["segments"][1]["start_draw_id"]
    )


def test_digit_position_audit_breaks_down_tiered_outcomes_without_new_p_values() -> None:
    product = PRODUCTS["max4d"]

    def sequence(seed: int) -> str:
        return "".join(str((seed + offset) % 10) for offset in range(4))

    observations = []
    for index in range(60):
        first = [sequence(index)]
        second = [sequence(index + 11), sequence(index + 23)]
        third = [sequence(index + 31), sequence(index + 43), sequence(index + 59)]
        wildcard = [f"X{sequence(index + 71)[1:]}", f"XX{sequence(index + 83)[2:]}"]
        tiered_outcomes = tuple(
            TieredOutcome(tier=tier, outcome=outcome, result_type="full_sequence")
            for tier, rows in (
                ("first", first),
                ("second", second),
                ("third", third),
            )
            for outcome in rows
        ) + tuple(
            TieredOutcome(tier="consolation_1", outcome=outcome, result_type="wildcard_prefix")
            for outcome in wildcard
        )
        observations.append(
            Observation(
                draw_id=str(index + 1).zfill(5),
                draw_date=date(2024, 1, 1) + timedelta(days=index),
                outcomes=tuple(
                    item.outcome
                    for item in tiered_outcomes
                    if item.result_type == "full_sequence"
                ),
                tiered_outcomes=tiered_outcomes,
            )
        )

    dataset = ProductDataset(
        product=product,
        observations=observations,
        source_counts=Counter({"vietlott.vn": len(observations)}),
        status_counts=Counter({"confirmed": len(observations)}),
        validation_counts=Counter({"valid": len(observations)}),
    )

    audit = build_product_audit(dataset)
    position_test = next(
        item
        for item in audit["tests"]
        if item["id"] == "digit_position_chi_square"
    )
    breakdown = position_test["parameters"]["tier_breakdown"]

    assert breakdown["status"] == "available"
    assert breakdown["no_new_p_values"] is True
    assert {row["result_type"] for row in breakdown["result_types"]} == {
        "full_sequence",
        "wildcard_prefix",
    }
    assert all(row["tier"] != "consolation_1" for row in breakdown["tiers"])
    assert {row["tier"] for row in breakdown["tiers"]} == {"first", "second", "third"}
    assert all(row["position_residuals"] for row in breakdown["tiers"])
