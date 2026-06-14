from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta

from vietlott_analytics.catalog import PRODUCTS
from vietlott_analytics.io import Observation, ProductDataset
from vietlott_analytics.predictions import PredictionLedger, build_backtest_report


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


def test_prediction_ledger_is_idempotent_and_appends_evaluations(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = PredictionLedger.load(path)
    ledger.process_product(_dataset(40))
    original_predictions = [
        event.copy() for event in ledger.events if event["event_type"] == "prediction"
    ]
    assert len(original_predictions) == 3

    ledger.process_product(_dataset(40))
    assert len(ledger.events) == 3

    ledger.process_product(_dataset(41))
    predictions = [event for event in ledger.events if event["event_type"] == "prediction"]
    evaluations = [event for event in ledger.events if event["event_type"] == "evaluation"]
    assert len(predictions) == 6
    assert len(evaluations) == 3
    assert predictions[:3] == original_predictions
    assert all(event["actual_draw_id"] == "00041" for event in evaluations)

    ledger.save()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 9
    assert all(json.loads(line)["event_type"] in {"prediction", "evaluation"} for line in lines)


def test_walk_forward_backtest_reports_uniform_baseline() -> None:
    report = build_backtest_report(_dataset(160))

    assert report["status"] == "complete"
    assert report["method"] == "walk_forward"
    assert report["samples"] > 0
    assert report["baseline"]["strategy"] == "uniform_seeded"
    assert "approximate_p_value" in report["comparison"]
