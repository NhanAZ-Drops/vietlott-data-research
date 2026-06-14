from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from vietlott_analytics.catalog import PRODUCTS
from vietlott_analytics.io import Observation, ProductDataset
from vietlott_analytics.statistics import build_product_report

EMPTY_PRIZES = {
    "rows": 0,
    "draws_with_prizes": 0,
    "reported_winners": 0,
    "estimated_payout_vnd": 0,
    "largest_prize_value_vnd": None,
    "largest_prize_draw_id": None,
}


def test_number_report_contains_uniformity_recency_and_positions() -> None:
    product = PRODUCTS["mega645"]
    start = date(2024, 1, 1)
    observations = []
    for index in range(90):
        values = tuple(sorted({((index + offset * 7) % 45) + 1 for offset in range(6)}))
        observations.append(
            Observation(
                draw_id=str(index + 1).zfill(5),
                draw_date=start + timedelta(days=index),
                values=values,
            )
        )
    dataset = ProductDataset(
        product=product,
        observations=observations,
        source_counts=Counter({"vietlott.vn": 90}),
        status_counts=Counter({"confirmed": 90}),
        validation_counts=Counter({"valid": 90}),
    )

    report = build_product_report(dataset, EMPTY_PRIZES)

    assert report["summary"]["confirmed_draws"] == 90
    assert len(report["analysis"]["numbers"]) == 45
    assert len(report["analysis"]["positions"]) == 6
    assert len(report["analysis"]["months"]) == 12
    assert len(report["analysis"]["weekdays"]) == 7
    assert report["analysis"]["uniformity"]["normalized_entropy"] > 0.95
    assert report["analysis"]["pairs"] is not None
    assert all("q_value_bh" in row for row in report["analysis"]["numbers"])


def test_digit_report_preserves_position_information() -> None:
    product = PRODUCTS["bingo18"]
    start = date(2025, 1, 1)
    observations = [
        Observation(
            draw_id=str(index + 1).zfill(7),
            draw_date=start + timedelta(days=index // 10),
            outcomes=(f"{index % 10}{(index + 1) % 10}{(index + 2) % 10}",),
        )
        for index in range(100)
    ]
    dataset = ProductDataset(
        product=product,
        observations=observations,
        source_counts=Counter({"vietlott.vn": 100}),
        status_counts=Counter({"confirmed": 100}),
        validation_counts=Counter({"valid": 100}),
    )

    report = build_product_report(dataset, EMPTY_PRIZES)

    analysis = report["analysis"]
    assert analysis["sequence_length"] == 3
    assert analysis["outcomes"] == 100
    assert len(analysis["positions"]) == 3
    assert all(len(position["values"]) == 10 for position in analysis["positions"])
    assert analysis["bingo_total_test"]["degrees_of_freedom"] == 27
