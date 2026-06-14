from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist, fmean, stdev
from typing import Any

from .catalog import AnalysisKind, AnalyticsProduct
from .io import Observation, ProductDataset

MODEL_VERSION = "1.0.0"
NORMAL = NormalDist()


@dataclass(slots=True)
class PredictionLedger:
    path: Path
    events: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> PredictionLedger:
        events: list[dict[str, Any]] = []
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError as error:
                        raise ValueError(f"Invalid prediction ledger line {line_number}") from error
        return cls(path=path, events=events)

    def process_product(self, dataset: ProductDataset) -> None:
        predictions = {
            event["prediction_id"]: event
            for event in self.events
            if event.get("event_type") == "prediction"
            and event.get("product") == dataset.product.slug
        }
        evaluated = {
            event["prediction_id"]
            for event in self.events
            if event.get("event_type") == "evaluation"
        }
        for prediction_id, prediction in predictions.items():
            if prediction_id in evaluated:
                continue
            actual = _first_observation_after(dataset.observations, prediction)
            if actual is not None:
                self.events.append(_evaluation_event(prediction, actual, dataset))
                evaluated.add(prediction_id)

        if not dataset.product.active:
            return
        latest = dataset.latest
        existing_keys = {
            (
                event.get("product"),
                event.get("dataset_cutoff_draw_id"),
                event.get("strategy"),
                event.get("model_version"),
            )
            for event in predictions.values()
        }
        for forecast in _forecast_events(dataset):
            key = (
                dataset.product.slug,
                latest.draw_id,
                forecast["strategy"],
                MODEL_VERSION,
            )
            if key not in existing_keys:
                self.events.append(forecast)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            for event in self.events:
                handle.write(
                    json.dumps(
                        event,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                    + "\n"
                )
        temp_path.replace(self.path)

    def site_report(self) -> dict[str, object]:
        predictions = [
            event for event in self.events if event.get("event_type") == "prediction"
        ]
        evaluations = [
            event for event in self.events if event.get("event_type") == "evaluation"
        ]
        evaluated_ids = {event["prediction_id"] for event in evaluations}
        latest_by_product: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for prediction in predictions:
            product = prediction["product"]
            strategy = prediction["strategy"]
            old = latest_by_product[product].get(strategy)
            if old is None or _prediction_order(prediction) > _prediction_order(old):
                latest_by_product[product][strategy] = prediction

        performance: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for evaluation in evaluations:
            performance[(evaluation["product"], evaluation["strategy"])].append(evaluation)

        performance_rows = []
        for (product, strategy), rows in sorted(performance.items()):
            exact_hits = sum(bool(row["metrics"].get("exact_hit")) for row in rows)
            hit_counts = [
                int(row["metrics"]["hit_count"])
                for row in rows
                if "hit_count" in row["metrics"]
            ]
            best_position = [
                int(row["metrics"]["best_position_matches"])
                for row in rows
                if "best_position_matches" in row["metrics"]
            ]
            performance_rows.append(
                {
                    "product": product,
                    "strategy": strategy,
                    "evaluations": len(rows),
                    "exact_hits": exact_hits,
                    "exact_hit_rate": _round(exact_hits / len(rows)),
                    "average_hits": _round(fmean(hit_counts)) if hit_counts else None,
                    "average_best_position_matches": (
                        _round(fmean(best_position)) if best_position else None
                    ),
                }
            )

        pending = [
            prediction for prediction in predictions if prediction["prediction_id"] not in evaluated_ids
        ]
        return {
            "schema_version": 1,
            "model_version": MODEL_VERSION,
            "principle": (
                "Mọi dự đoán được ghi trước kết quả, giữ nguyên tham số và luôn so với "
                "baseline chọn đồng đều."
            ),
            "latest": {
                product: list(strategies.values())
                for product, strategies in sorted(latest_by_product.items())
            },
            "pending_count": len(pending),
            "evaluation_count": len(evaluations),
            "performance": performance_rows,
            "recent_evaluations": evaluations[-100:][::-1],
        }


def build_backtest_report(dataset: ProductDataset) -> dict[str, object]:
    if dataset.product.kind is AnalysisKind.NUMBER_SET:
        return _number_backtest(dataset)
    return _digit_backtest(dataset)


def _forecast_events(dataset: ProductDataset) -> list[dict[str, Any]]:
    product = dataset.product
    latest = dataset.latest
    generated_at = dataset.latest_fetched_at or f"{latest.draw_date.isoformat()}T00:00:00+00:00"
    fingerprint = hashlib.sha256(dataset.fingerprint.encode()).hexdigest()
    if product.kind is AnalysisKind.NUMBER_SET:
        forecasts = _number_forecasts(dataset)
    else:
        forecasts = _digit_forecasts(dataset)
    events = []
    for forecast in forecasts:
        identity = "|".join(
            (
                product.slug,
                latest.draw_id,
                forecast["strategy"],
                MODEL_VERSION,
                fingerprint,
            )
        )
        events.append(
            {
                "event_type": "prediction",
                "prediction_id": hashlib.sha256(identity.encode()).hexdigest()[:24],
                "product": product.slug,
                "strategy": forecast["strategy"],
                "strategy_label": forecast["strategy_label"],
                "model_version": MODEL_VERSION,
                "generated_at": generated_at,
                "dataset_cutoff_draw_id": latest.draw_id,
                "dataset_cutoff_date": latest.draw_date.isoformat(),
                "dataset_fingerprint": fingerprint,
                "target": "first_confirmed_draw_after_cutoff",
                "prediction": forecast["prediction"],
                "parameters": forecast["parameters"],
                "research_only": True,
            }
        )
    return events


def _number_forecasts(dataset: ProductDataset) -> list[dict[str, Any]]:
    product = dataset.product
    observations = dataset.observations
    total_counts = Counter(value for item in observations for value in item.values)
    recent_window = min(1000 if product.slug == "keno" else 200, len(observations))
    recent_counts = Counter(
        value for item in observations[-recent_window:] for value in item.values
    )
    last_seen: dict[int, int] = {}
    for index, item in enumerate(observations):
        for value in item.values:
            last_seen[value] = index
    scores = _number_scores(
        product,
        total_counts,
        len(observations),
        recent_counts,
        recent_window,
        last_seen,
        len(observations),
    )
    seed = f"{product.slug}|{dataset.latest.draw_id}|{MODEL_VERSION}"
    uniform = _uniform_number_pick(product, seed)
    balanced = _top_numbers(scores, "balanced", product.pick_count or 0, seed)
    recent = _top_numbers(scores, "recent", product.pick_count or 0, seed)

    special_predictions = _special_forecasts(dataset, seed)
    result = []
    for strategy, label, values in (
        ("uniform_seeded", "Baseline đồng đều có seed", uniform),
        ("balanced_signal", "Tín hiệu cân bằng", balanced),
        ("recent_frequency", "Tần suất cửa sổ gần", recent),
    ):
        result.append(
            {
                "strategy": strategy,
                "strategy_label": label,
                "prediction": {
                    "numbers": values,
                    "special_numbers": special_predictions.get(strategy, []),
                },
                "parameters": {
                    "history_draws": len(observations),
                    "recent_window_draws": recent_window,
                    "selection_count": product.pick_count,
                    "pool_size": product.pool_size,
                    "seed_policy": "sha256(product, cutoff, model_version)",
                },
            }
        )
    return result


def _digit_forecasts(dataset: ProductDataset) -> list[dict[str, Any]]:
    product = dataset.product
    length = product.sequence_length or 0
    total = [Counter() for _ in range(length)]
    recent = [Counter() for _ in range(length)]
    outcomes = [outcome for item in dataset.observations for outcome in item.outcomes]
    recent_draws = dataset.observations[-min(500, len(dataset.observations)) :]
    recent_outcomes = [outcome for item in recent_draws for outcome in item.outcomes]
    for outcome in outcomes:
        for position, char in enumerate(outcome):
            total[position][int(char)] += 1
    for outcome in recent_outcomes:
        for position, char in enumerate(outcome):
            recent[position][int(char)] += 1

    seed = f"{product.slug}|{dataset.latest.draw_id}|{MODEL_VERSION}"
    uniform_rng = random.Random(_seed_int(seed + "|uniform"))
    uniform = "".join(str(uniform_rng.randrange(10)) for _ in range(length))
    recent_mode = _digit_sequence_from_scores(total, recent, "recent", seed)
    balanced = _digit_sequence_from_scores(total, recent, "balanced", seed)
    return [
        {
            "strategy": "uniform_seeded",
            "strategy_label": "Baseline đồng đều có seed",
            "prediction": {"sequence": uniform},
            "parameters": {
                "history_draws": len(dataset.observations),
                "recent_window_draws": len(recent_draws),
                "sequence_length": length,
            },
        },
        {
            "strategy": "balanced_signal",
            "strategy_label": "Tín hiệu cân bằng",
            "prediction": {"sequence": balanced},
            "parameters": {
                "history_draws": len(dataset.observations),
                "recent_window_draws": len(recent_draws),
                "sequence_length": length,
            },
        },
        {
            "strategy": "recent_frequency",
            "strategy_label": "Tần suất cửa sổ gần",
            "prediction": {"sequence": recent_mode},
            "parameters": {
                "history_draws": len(dataset.observations),
                "recent_window_draws": len(recent_draws),
                "sequence_length": length,
            },
        },
    ]


def _number_backtest(dataset: ProductDataset) -> dict[str, object]:
    product = dataset.product
    observations = dataset.observations
    minimum_history = min(200, max(30, len(observations) // 3))
    limit = 5000 if product.slug == "keno" else 1000
    start = max(minimum_history, len(observations) - limit)
    if start >= len(observations):
        return {"status": "insufficient_data", "samples": 0}

    recent_window = 1000 if product.slug == "keno" else 200
    total_counts: Counter[int] = Counter()
    last_seen: dict[int, int] = {}
    for index, item in enumerate(observations[:start]):
        total_counts.update(item.values)
        for value in item.values:
            last_seen[value] = index
    recent_items = deque(observations[max(0, start - recent_window) : start])
    recent_counts = Counter(value for item in recent_items for value in item.values)

    model_hits: list[int] = []
    baseline_hits: list[int] = []
    differences: list[float] = []
    model_distribution = Counter()
    baseline_distribution = Counter()
    for index in range(start, len(observations)):
        target = observations[index]
        scores = _number_scores(
            product,
            total_counts,
            index,
            recent_counts,
            len(recent_items),
            last_seen,
            index,
        )
        seed = f"backtest|{product.slug}|{target.draw_id}|{MODEL_VERSION}"
        model = _top_numbers(scores, "balanced", product.pick_count or 0, seed)
        baseline = _uniform_number_pick(product, seed)
        actual = set(target.values)
        model_hit = len(actual.intersection(model))
        baseline_hit = len(actual.intersection(baseline))
        model_hits.append(model_hit)
        baseline_hits.append(baseline_hit)
        differences.append(float(model_hit - baseline_hit))
        model_distribution[model_hit] += 1
        baseline_distribution[baseline_hit] += 1

        total_counts.update(target.values)
        for value in target.values:
            last_seen[value] = index
        recent_items.append(target)
        recent_counts.update(target.values)
        if len(recent_items) > recent_window:
            expired = recent_items.popleft()
            recent_counts.subtract(expired.values)

    z_score, p_value = _paired_normal_test(differences)
    expected_hits = (product.pick_count or 0) ** 2 / product.pool_size
    return {
        "status": "complete",
        "method": "walk_forward",
        "samples": len(model_hits),
        "first_test_draw_id": observations[start].draw_id,
        "latest_test_draw_id": observations[-1].draw_id,
        "minimum_history_draws": start,
        "recent_window_draws": recent_window,
        "model": {
            "strategy": "balanced_signal",
            "average_hits": _round(fmean(model_hits)),
            "exact_hits": model_distribution[product.pick_count or 0],
            "hit_distribution": _counter_to_rows(model_distribution),
        },
        "baseline": {
            "strategy": "uniform_seeded",
            "average_hits": _round(fmean(baseline_hits)),
            "expected_average_hits": _round(expected_hits),
            "exact_hits": baseline_distribution[product.pick_count or 0],
            "hit_distribution": _counter_to_rows(baseline_distribution),
        },
        "comparison": {
            "mean_hit_difference": _round(fmean(differences)),
            "paired_z_score": _round(z_score),
            "approximate_p_value": _round(p_value, 8),
            "beats_baseline": fmean(differences) > 0 and p_value < 0.05,
        },
        "warning": (
            "Backtest cuốn chiếu chỉ dùng dữ liệu trước kỳ kiểm tra. Kết quả vẫn có thể "
            "do nhiễu và phải được xác nhận bằng dự đoán đã đóng băng."
        ),
    }


def _digit_backtest(dataset: ProductDataset) -> dict[str, object]:
    product = dataset.product
    observations = dataset.observations
    minimum_history = min(100, max(30, len(observations) // 3))
    limit = 5000 if product.slug == "bingo18" else 1000
    start = max(minimum_history, len(observations) - limit)
    if start >= len(observations):
        return {"status": "insufficient_data", "samples": 0}

    length = product.sequence_length or 0
    total = [Counter() for _ in range(length)]
    recent = [Counter() for _ in range(length)]
    for item in observations[:start]:
        _update_digit_counts(total, item.outcomes, 1)
    recent_window = 500
    recent_items = deque(observations[max(0, start - recent_window) : start])
    for item in recent_items:
        _update_digit_counts(recent, item.outcomes, 1)

    model_exact = 0
    baseline_exact = 0
    model_best: list[int] = []
    baseline_best: list[int] = []
    for index in range(start, len(observations)):
        target = observations[index]
        seed = f"backtest|{product.slug}|{target.draw_id}|{MODEL_VERSION}"
        model = _digit_sequence_from_scores(total, recent, "balanced", seed)
        rng = random.Random(_seed_int(seed + "|uniform"))
        baseline = "".join(str(rng.randrange(10)) for _ in range(length))
        actual = set(target.outcomes)
        model_exact += model in actual
        baseline_exact += baseline in actual
        model_best.append(_best_position_match(model, actual))
        baseline_best.append(_best_position_match(baseline, actual))

        _update_digit_counts(total, target.outcomes, 1)
        recent_items.append(target)
        _update_digit_counts(recent, target.outcomes, 1)
        if len(recent_items) > recent_window:
            expired = recent_items.popleft()
            _update_digit_counts(recent, expired.outcomes, -1)

    samples = len(model_best)
    differences = [
        float(model - baseline)
        for model, baseline in zip(model_best, baseline_best, strict=True)
    ]
    z_score, p_value = _paired_normal_test(differences)
    average_outcomes = fmean(len(item.outcomes) for item in observations[start:])
    expected_exact_rate = min(1.0, average_outcomes / (10**length))
    return {
        "status": "complete",
        "method": "walk_forward",
        "samples": samples,
        "first_test_draw_id": observations[start].draw_id,
        "latest_test_draw_id": observations[-1].draw_id,
        "minimum_history_draws": start,
        "recent_window_draws": recent_window,
        "model": {
            "strategy": "balanced_signal",
            "exact_hits": model_exact,
            "exact_hit_rate": _round(model_exact / samples),
            "average_best_position_matches": _round(fmean(model_best)),
        },
        "baseline": {
            "strategy": "uniform_seeded",
            "exact_hits": baseline_exact,
            "exact_hit_rate": _round(baseline_exact / samples),
            "expected_exact_hit_rate": _round(expected_exact_rate),
            "average_best_position_matches": _round(fmean(baseline_best)),
        },
        "comparison": {
            "mean_position_match_difference": _round(fmean(differences)),
            "paired_z_score": _round(z_score),
            "approximate_p_value": _round(p_value, 8),
            "beats_baseline": fmean(differences) > 0 and p_value < 0.05,
        },
        "warning": (
            "Các kết quả cùng một kỳ ở trò chơi nhiều hạng giải không hoàn toàn là các mẫu "
            "độc lập. Chỉ nên xem đây là kiểm tra mô tả."
        ),
    }


def _number_scores(
    product: AnalyticsProduct,
    total_counts: Counter[int],
    total_draws: int,
    recent_counts: Counter[int],
    recent_draws: int,
    last_seen: dict[int, int],
    current_index: int,
) -> dict[int, dict[str, float]]:
    probability = (product.pick_count or 0) / product.pool_size
    total_sd = math.sqrt(max(total_draws * probability * (1 - probability), 1e-12))
    recent_sd = math.sqrt(max(recent_draws * probability * (1 - probability), 1e-12))
    scores = {}
    for value in range(product.pool_min or 1, (product.pool_max or 0) + 1):
        long_z = (
            (total_counts[value] - total_draws * probability) / total_sd
            if total_draws
            else 0.0
        )
        recent_z = (
            (recent_counts[value] - recent_draws * probability) / recent_sd
            if recent_draws
            else 0.0
        )
        draws_since = current_index - 1 - last_seen.get(value, -1)
        overdue_ratio = min(4.0, draws_since * probability)
        scores[value] = {
            "recent": recent_z,
            "balanced": 0.55 * recent_z - 0.25 * long_z + 0.12 * (overdue_ratio - 1),
        }
    return scores


def _top_numbers(
    scores: dict[int, dict[str, float]],
    key: str,
    count: int,
    seed: str,
) -> list[int]:
    ranked = sorted(
        scores,
        key=lambda value: (scores[value][key], _stable_jitter(seed, value)),
        reverse=True,
    )
    return sorted(ranked[:count])


def _uniform_number_pick(product: AnalyticsProduct, seed: str) -> list[int]:
    rng = random.Random(_seed_int(seed + "|uniform"))
    values = list(range(product.pool_min or 1, (product.pool_max or 0) + 1))
    return sorted(rng.sample(values, product.pick_count or 0))


def _special_forecasts(dataset: ProductDataset, seed: str) -> dict[str, list[int]]:
    product = dataset.product
    if not product.special_count or product.special_min is None or product.special_max is None:
        return {}
    observations = [item for item in dataset.observations if item.special_values]
    total_counts = Counter(value for item in observations for value in item.special_values)
    recent_window = min(200, len(observations))
    recent_counts = Counter(
        value for item in observations[-recent_window:] for value in item.special_values
    )
    pool = list(range(product.special_min, product.special_max + 1))
    expected = product.special_count / len(pool)
    total_sd = math.sqrt(max(len(observations) * expected * (1 - expected), 1e-12))
    recent_sd = math.sqrt(max(recent_window * expected * (1 - expected), 1e-12))
    score_rows = {}
    for value in pool:
        long_z = (total_counts[value] - len(observations) * expected) / total_sd
        recent_z = (recent_counts[value] - recent_window * expected) / recent_sd
        score_rows[value] = {
            "balanced": 0.6 * recent_z - 0.25 * long_z,
            "recent": recent_z,
        }
    rng = random.Random(_seed_int(seed + "|special"))
    return {
        "uniform_seeded": sorted(rng.sample(pool, product.special_count)),
        "balanced_signal": _top_numbers(
            score_rows,
            "balanced",
            product.special_count,
            seed + "|special",
        ),
        "recent_frequency": _top_numbers(
            score_rows,
            "recent",
            product.special_count,
            seed + "|special",
        ),
    }


def _digit_sequence_from_scores(
    total: list[Counter[int]],
    recent: list[Counter[int]],
    strategy: str,
    seed: str,
) -> str:
    result = []
    for position, (total_counter, recent_counter) in enumerate(
        zip(total, recent, strict=True)
    ):
        total_observations = sum(total_counter.values())
        recent_observations = sum(recent_counter.values())
        expected_total = total_observations / 10 if total_observations else 0
        expected_recent = recent_observations / 10 if recent_observations else 0
        total_sd = math.sqrt(max(total_observations * 0.1 * 0.9, 1e-12))
        recent_sd = math.sqrt(max(recent_observations * 0.1 * 0.9, 1e-12))
        scores = {}
        for digit in range(10):
            long_z = (
                (total_counter[digit] - expected_total) / total_sd
                if total_observations
                else 0
            )
            recent_z = (
                (recent_counter[digit] - expected_recent) / recent_sd
                if recent_observations
                else 0
            )
            score = recent_z if strategy == "recent" else 0.65 * recent_z - 0.25 * long_z
            scores[digit] = score + _stable_jitter(f"{seed}|{position}", digit) * 1e-6
        result.append(str(max(scores, key=scores.get)))
    return "".join(result)


def _evaluation_event(
    prediction: dict[str, Any],
    actual: Observation,
    dataset: ProductDataset,
) -> dict[str, Any]:
    product = dataset.product
    predicted = prediction["prediction"]
    if product.kind is AnalysisKind.NUMBER_SET:
        numbers = set(int(value) for value in predicted.get("numbers", []))
        actual_numbers = set(actual.values)
        predicted_special = set(int(value) for value in predicted.get("special_numbers", []))
        metrics = {
            "hit_count": len(numbers.intersection(actual_numbers)),
            "exact_hit": numbers == actual_numbers,
            "special_hit_count": len(predicted_special.intersection(actual.special_values)),
        }
        actual_result: dict[str, object] = {
            "numbers": list(actual.values),
            "special_numbers": list(actual.special_values),
        }
    else:
        sequence = str(predicted.get("sequence", ""))
        actual_set = set(actual.outcomes)
        metrics = {
            "exact_hit": sequence in actual_set,
            "best_position_matches": _best_position_match(sequence, actual_set),
        }
        actual_result = {"outcomes": list(actual.outcomes)}
    identity = f"{prediction['prediction_id']}|{actual.draw_id}"
    return {
        "event_type": "evaluation",
        "evaluation_id": hashlib.sha256(identity.encode()).hexdigest()[:24],
        "prediction_id": prediction["prediction_id"],
        "product": product.slug,
        "strategy": prediction["strategy"],
        "model_version": prediction["model_version"],
        "evaluated_at": dataset.latest_fetched_at
        or datetime.now(UTC).replace(microsecond=0).isoformat(),
        "actual_draw_id": actual.draw_id,
        "actual_draw_date": actual.draw_date.isoformat(),
        "actual_result": actual_result,
        "metrics": metrics,
    }


def _first_observation_after(
    observations: list[Observation],
    prediction: dict[str, Any],
) -> Observation | None:
    cutoff_date = prediction["dataset_cutoff_date"]
    cutoff_id = prediction["dataset_cutoff_draw_id"]
    cutoff_key = (
        cutoff_date,
        int(cutoff_id) if str(cutoff_id).isdigit() else str(cutoff_id),
    )
    for observation in observations:
        key = (
            observation.draw_date.isoformat(),
            int(observation.draw_id) if observation.draw_id.isdigit() else observation.draw_id,
        )
        if key > cutoff_key:
            return observation
    return None


def _prediction_order(prediction: dict[str, Any]) -> tuple[str, int | str]:
    draw_id = prediction["dataset_cutoff_draw_id"]
    return prediction["dataset_cutoff_date"], int(draw_id) if draw_id.isdigit() else draw_id


def _best_position_match(prediction: str, outcomes: set[str]) -> int:
    if not outcomes:
        return 0
    return max(
        sum(
            left == right
            for left, right in zip(prediction, outcome, strict=False)
        )
        for outcome in outcomes
    )


def _update_digit_counts(
    counters: list[Counter[int]],
    outcomes: tuple[str, ...],
    direction: int,
) -> None:
    for outcome in outcomes:
        for position, char in enumerate(outcome):
            counters[position][int(char)] += direction


def _paired_normal_test(differences: list[float]) -> tuple[float, float]:
    if len(differences) < 2 or stdev(differences) == 0:
        return 0.0, 1.0
    z_score = fmean(differences) / (stdev(differences) / math.sqrt(len(differences)))
    p_value = 2 * (1 - NORMAL.cdf(abs(z_score)))
    return z_score, max(0.0, min(1.0, p_value))


def _counter_to_rows(counter: Counter[int]) -> list[dict[str, int]]:
    return [{"hits": hits, "count": counter[hits]} for hits in sorted(counter)]


def _stable_jitter(seed: str, value: int) -> float:
    digest = hashlib.sha256(f"{seed}|{value}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _seed_int(seed: str) -> int:
    return int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], "big")


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)
