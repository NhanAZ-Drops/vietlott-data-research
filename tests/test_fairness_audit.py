from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from vietlott_analytics.catalog import PRODUCTS
from vietlott_analytics.fairness import (
    audit_log_events,
    build_product_audit,
    finalize_audits,
)
from vietlott_analytics.io import Observation, ProductDataset


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

    assert audit["suite_version"] == "1.0.0"
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
    assert all("q_value_bh" in test for test in audit["tests"] if test["p_value"] is not None)


def test_finalize_audits_adds_global_correction_and_jsonl_events() -> None:
    product = PRODUCTS["bingo18"]
    observations = [
        Observation(
            draw_id=str(index + 1).zfill(7),
            draw_date=date(2025, 1, 1) + timedelta(days=index // 10),
            outcomes=(f"{index % 10}{(index + 3) % 10}{(index + 7) % 10}",),
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
    assert events
    assert {event["event_type"] for event in events} == {"fairness_audit_test"}
    assert all(
        "q_value_global_bh" in test
        for test in report["audit"]["tests"]
        if test["p_value"] is not None
    )
