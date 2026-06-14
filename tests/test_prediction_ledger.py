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
    report = ledger.site_report()
    assert report["schema_version"] == 2
    assert report["evaluation_count"] == 3
    assert report["outcome_summary"]["exact"] == 0
    assert report["product_outcomes"]["mega645"]["evaluated_predictions"] == 3
    assert report["history_limit_per_product"] == 100
    assert report["recent_evaluations"][0]["prediction"]
    assert report["recent_evaluations"][0]["prediction_generated_at"]
    assert report["recent_evaluations"][0]["outcome"]["status"] in {
        "exact",
        "near",
        "wrong",
    }

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

    assert report["outcome_summary"] == {
        "evaluated_draws": 3,
        "evaluated_predictions": 3,
        "exact": 1,
        "near": 1,
        "wrong": 1,
        "partial_matches": 2,
        "zero_matches": 0,
        "near_rule": (
            "Gần đúng chỉ khi thiếu đúng một số hoặc một vị trí so với kết quả "
            "đầy đủ. Trùng ít hơn vẫn được ghi số lượng nhưng tính là sai."
        ),
    }
    assert report["product_outcomes"]["mega645"] == {
        "evaluated_draws": 3,
        "evaluated_predictions": 3,
        "exact": 1,
        "near": 1,
        "wrong": 1,
        "partial_matches": 2,
        "zero_matches": 0,
        "score_kind": "numbers",
        "score_distribution": [
            {"score": 1, "count": 1},
            {"score": 5, "count": 1},
            {"score": 6, "count": 1},
        ],
    }
    statuses = {
        evaluation["prediction_id"]: evaluation["outcome"]["status"]
        for evaluation in report["recent_evaluations"]
    }
    assert statuses == {
        "prediction-0": "exact",
        "prediction-1": "near",
        "prediction-2": "wrong",
    }
