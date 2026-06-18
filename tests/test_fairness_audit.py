from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

import pytest

from vietlott_analytics.catalog import PRODUCTS
from vietlott_analytics.fairness import (
    EFFECT_THRESHOLD_REGISTRY,
    _pair_co_occurrence_test,
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
    assert audit["power_summary"]["primary_power"] == 0.8
    assert audit["power_summary"]["supported_test_count"] > 0
    assert audit["power_summary"]["threshold_detectable_count"] <= audit["power_summary"][
        "supported_test_count"
    ]
    assert all("power_analysis" in test for test in active_tests)
    frequency_power = next(
        test["power_analysis"]
        for test in active_tests
        if test["id"] == "number_marginal_chi_square"
    )
    assert frequency_power["status"] == "available"
    assert frequency_power["effective_sample_size"] == 540
    assert frequency_power["practical_threshold_delta"] == 0.05
    assert any(row["power"] == 0.8 for row in frequency_power["target_powers"])
    assert all(
        row["minimum_detectable_effect"] > 0
        for row in frequency_power["target_powers"]
    )
    gap_power = next(
        test["power_analysis"]
        for test in active_tests
        if test["id"] == "number_current_gap_geometric"
    )
    assert gap_power["status"] == "unsupported_scale"
    for test_id in (
        "number_sum_runs",
        "number_sum_lag1_autocorrelation",
        "number_sum_split_half_change",
    ):
        permutation = next(
            test["parameters"]["permutation_check"]
            for test in active_tests
            if test["id"] == test_id
        )
        assert permutation["status"] == "available"
        assert permutation["method"] == "whole_observation_label_permutation"
        assert permutation["permutations"] == 499
        assert len(permutation["seed"]) == 16
        assert permutation["preserve_unit"] == "whole_draw_sum"
        assert permutation["sampling_method"] == "full_sequence"
        assert permutation["no_multiple_testing_decision"] is True
        assert 0 <= permutation["empirical_p_value"] <= 1
        bootstrap = next(
            test["parameters"]["block_bootstrap_check"]
            for test in active_tests
            if test["id"] == test_id
        )
        assert bootstrap["status"] == "available"
        assert bootstrap["method"] == "moving_block_bootstrap"
        assert bootstrap["resamples"] == 199
        assert len(bootstrap["seed"]) == 16
        assert bootstrap["sampling_method"] == "full_sequence"
        assert bootstrap["preserve_time_structure"] == "contiguous_observation_blocks"
        assert bootstrap["no_multiple_testing_decision"] is True
        assert bootstrap["confidence_interval_lower"] <= bootstrap["confidence_interval_upper"]
    change_point_test = next(
        test
        for test in active_tests
        if test["id"] == "number_sum_split_half_change"
    )
    assert change_point_test["algorithm"] == "Pre-Registered Multi-Candidate Change-Point Scan"
    assert change_point_test["statistic_name"] == "max_abs_z_score"
    scan = change_point_test["parameters"]["change_point_scan"]
    assert scan["status"] == "available"
    assert scan["method"] == "pre_registered_candidate_scan"
    assert scan["multiple_candidate_correction"] == "bonferroni"
    assert scan["candidate_count"] >= 3
    assert len(scan["candidates"]) == scan["candidate_count"]
    assert scan["adjusted_p_value"] >= scan["raw_p_value"]
    assert scan["no_unadjusted_search_decision"] is True
    strongest = scan["strongest_candidate"]
    assert 0 < strongest["candidate_fraction"] < 1
    assert "adjusted_p_value" in strongest


def test_keno_pair_co_occurrence_uses_full_dense_counter_above_old_limit() -> None:
    product = PRODUCTS["keno"]
    observations = [
        Observation(
            draw_id=str(index + 1).zfill(7),
            draw_date=date(2026, 1, 1) + timedelta(days=index // 288),
            values=tuple(
                sorted(((index * 17 + offset * 3) % 80) + 1 for offset in range(20))
            ),
        )
        for index in range(15_800)
    ]
    dataset = ProductDataset(
        product=product,
        observations=observations,
        source_counts=Counter({"synthetic": len(observations)}),
        status_counts=Counter({"confirmed": len(observations)}),
        validation_counts=Counter({"valid": len(observations)}),
    )

    test = _pair_co_occurrence_test(dataset)

    assert test is not None
    assert test["id"] == "number_pair_co_occurrence"
    assert test["status"] == "pending"
    assert test["degrees_of_freedom"] == 3159
    assert test["p_value"] is not None
    assert test["power_analysis"]["status"] == "available"
    parameters = test["parameters"]
    assert parameters["counting_method"] == "dense_pair_index_vector"
    assert parameters["no_sampling"] is True
    assert parameters["pairs"] == 3160
    assert parameters["pair_space"] == 3160
    assert parameters["pair_observations"] > 3_000_000
    assert parameters["observed_pair_observations"] == parameters["pair_observations"]
    assert len(parameters["top_pairs"]) == 5
    assert parameters["highest_count_pair"] == parameters["top_pairs"][0]["pair"]


def test_finalize_audits_adds_global_correction_and_jsonl_events() -> None:
    product = PRODUCTS["bingo18"]
    observations = [
        Observation(
            draw_id=str(index + 1).zfill(7),
            draw_date=date(2025, 1, 1) + timedelta(days=index // 10),
            outcomes=(
                f"{index % 6 + 1}{(index + 3) % 6 + 1}{(index + 5) % 6 + 1}",
            ),
            source_host="vietlott.vn" if index < 60 else "mirror.example",
            data_source="official_vietlott" if index < 60 else "community_mirror",
            source_origin="official" if index < 60 else "community",
            source_verification="official_verified_match"
            if index < 60
            else "single_secondary_source",
        )
        for index in range(120)
    ]
    dataset = ProductDataset(
        product=product,
        observations=observations,
        source_counts=Counter({"vietlott.vn": 120}),
        status_counts=Counter({"confirmed": 120, "not_confirmed": 3}),
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
    assert summary["power_summary"]["method"] == "normal_approximation"
    assert summary["power_summary"]["supported_test_count"] > 0
    product_summary = summary["products"][0]
    assert product_summary["reliability_sensitivity"]["status"] == "available"
    assert product_summary["reliability_sensitivity"]["not_confirmed_rows"] == 3
    assert product_summary["reliability_sensitivity"]["filtered_confirmed_draws"] == 60
    assert (
        product_summary["reliability_sensitivity"]["low_reliability_confirmed_draws"]
        == 60
    )
    assert any(
        entry["test_count"] > 0
        for entry in summary["threshold_sensitivity"]["by_threshold"]
    )
    assert events
    assert {event["event_type"] for event in events} == {"fairness_audit_test"}
    assert all("dependency_family" in event for event in events)
    assert any(event["minimum_detectable_effect_80"] is not None for event in events)
    assert any(event["power_status"] == "available" for event in events)
    assert any(event["permutation_status"] == "available" for event in events)
    assert any(event["permutation_p_value"] is not None for event in events)
    assert any(event["block_bootstrap_status"] == "available" for event in events)
    assert any(event["block_bootstrap_interval_lower"] is not None for event in events)
    assert any(event["change_point_candidate_count"] is not None for event in events)
    assert any(event["change_point_adjusted_p_value"] is not None for event in events)
    assert any(event["q_value_dependency_family_bh"] is not None for event in events)
    assert any(event["reliability_sensitivity_status"] == "available" for event in events)
    assert any(event["reliability_low_reliability_draws"] == 60 for event in events)
    assert any(event["reliability_filtered_draws"] == 60 for event in events)
    assert any(event["reliability_compared_test_count"] for event in events)
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
    reliability = report["audit"]["reliability_sensitivity"]
    assert reliability["status"] == "available"
    assert reliability["no_new_p_values"] is True
    assert reliability["basis"] == "draw_status plus source_verification"
    assert reliability["baseline"]["audit_uses_confirmed_only"] is True
    assert reliability["baseline"]["not_confirmed_rows"] == 3
    assert reliability["baseline"]["confirmed_draws_in_audit"] == 120
    assert reliability["filtered_confirmed_draws"] == 60
    assert reliability["low_reliability_confirmed_draws"] == 60
    assert reliability["compared_test_count"] > 0
    assert reliability["comparisons"]
    assert reliability["largest_effect_shift"]
    assert all("p_value" not in row for row in reliability["comparisons"])
    assert all("q_value" not in row for row in reliability["comparisons"])
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
    source_breakdown = position_test["parameters"]["source_breakdown"]
    assert source_breakdown["status"] == "available"
    assert source_breakdown["no_new_p_values"] is True
    assert source_breakdown["eligible_source_count"] == 2
    assert {source["source_key"] for source in source_breakdown["sources"]} == {
        "community_mirror",
        "official_vietlott",
    }
    assert all(source["sample_status"] == "usable" for source in source_breakdown["sources"])
    assert all("p_value" not in source for source in source_breakdown["sources"])
    assert all(source["top_residuals"] for source in source_breakdown["sources"])
    assert all(
        "p_value" not in residual
        for source in source_breakdown["sources"]
        for residual in source["top_residuals"]
    )
    source_leave_one_out = position_test["parameters"]["source_leave_one_out"]
    assert source_leave_one_out["status"] == "available"
    assert source_leave_one_out["method"] == "source_leave_one_out"
    assert source_leave_one_out["no_new_p_values"] is True
    assert source_leave_one_out["eligible_source_count"] == 2
    assert source_leave_one_out["baseline"]["statistic"] == pytest.approx(
        position_test["statistic"],
        abs=1e-4,
    )
    assert {
        source["excluded_source_key"]
        for source in source_leave_one_out["excluded_sources"]
    } == {
        "community_mirror",
        "official_vietlott",
    }
    assert all(
        source["sample_status"] == "usable"
        for source in source_leave_one_out["excluded_sources"]
    )
    assert all(
        source["remaining_draws"] == 60
        for source in source_leave_one_out["excluded_sources"]
    )
    assert all(
        "p_value" not in source
        for source in source_leave_one_out["excluded_sources"]
    )
    assert all(
        "p_value" not in residual
        for source in source_leave_one_out["excluded_sources"]
        for residual in source["top_residuals"]
    )
    assert source_leave_one_out["strongest_effect_shift"]["excluded_source_key"] in {
        "community_mirror",
        "official_vietlott",
    }
    digit_permutation = next(
        item["parameters"]["permutation_check"]
        for item in report["audit"]["tests"]
        if item["id"] == "digit_value_lag1_autocorrelation"
    )
    assert digit_permutation["status"] == "available"
    assert digit_permutation["preserve_unit"] == "whole_digit_value"
    assert digit_permutation["no_multiple_testing_decision"] is True
    digit_bootstrap = next(
        item["parameters"]["block_bootstrap_check"]
        for item in report["audit"]["tests"]
        if item["id"] == "digit_value_lag1_autocorrelation"
    )
    assert digit_bootstrap["status"] == "available"
    assert digit_bootstrap["preserve_time_structure"] == "contiguous_observation_blocks"
    assert digit_bootstrap["no_multiple_testing_decision"] is True


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
