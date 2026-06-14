from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from itertools import combinations
from statistics import NormalDist, fmean

from .catalog import AnalyticsProduct
from .io import ProductDataset

NORMAL = NormalDist()


def build_product_report(
    dataset: ProductDataset,
    prize_summary: dict[str, object],
) -> dict[str, object]:
    product = dataset.product
    common = _common_report(dataset, prize_summary)
    if product.kind.value == "number_set":
        analysis = _number_set_report(dataset)
    else:
        analysis = _digit_sequence_report(dataset)
    return {
        "schema_version": 1,
        "product": {
            "slug": product.slug,
            "name": product.name,
            "short_name": product.short_name,
            "kind": product.kind.value,
            "active": product.active,
            "note": product.note,
        },
        "summary": common,
        "analysis": analysis,
    }


def _common_report(
    dataset: ProductDataset,
    prize_summary: dict[str, object],
) -> dict[str, object]:
    observations = dataset.observations
    draw_dates = [item.draw_date for item in observations]
    days = len(set(draw_dates))
    draws_per_day = len(observations) / days if days else 0.0
    weekday_counts = Counter(item.draw_date.weekday() for item in observations)
    month_counts = Counter(item.draw_date.month for item in observations)
    latest_jackpot = dataset.jackpot_values[-1] if dataset.jackpot_values else None
    largest_jackpot = max(dataset.jackpot_values, key=lambda item: item[1], default=None)

    return {
        "confirmed_draws": len(observations),
        "not_confirmed_draws": dataset.status_counts["not_confirmed"],
        "first_draw_id": observations[0].draw_id,
        "latest_draw_id": observations[-1].draw_id,
        "first_date": observations[0].draw_date.isoformat(),
        "latest_date": observations[-1].draw_date.isoformat(),
        "calendar_days_with_draws": days,
        "average_draws_per_active_day": _round(draws_per_day),
        "source_hosts": dict(dataset.source_counts.most_common()),
        "data_sources": dict(dataset.data_source_counts.most_common()),
        "validation_statuses": dict(dataset.validation_counts.most_common()),
        "draws_by_weekday": [
            {"weekday": index, "draws": weekday_counts[index]} for index in range(7)
        ],
        "draws_by_month": [
            {"month": month, "draws": month_counts[month]} for month in range(1, 13)
        ],
        "latest_jackpot": (
            {"draw_id": latest_jackpot[0], "value_vnd": latest_jackpot[1]}
            if latest_jackpot
            else None
        ),
        "largest_jackpot": (
            {"draw_id": largest_jackpot[0], "value_vnd": largest_jackpot[1]}
            if largest_jackpot
            else None
        ),
        "prizes": prize_summary,
        "recent_draws": [_recent_draw(item, dataset.product) for item in observations[-12:][::-1]],
    }


def _number_set_report(dataset: ProductDataset) -> dict[str, object]:
    product = dataset.product
    observations = dataset.observations
    n_draws = len(observations)
    pool = list(range(product.pool_min or 1, (product.pool_max or 0) + 1))
    pick_count = product.pick_count or 0
    expected_probability = pick_count / product.pool_size
    expected_count = n_draws * expected_probability
    variance = n_draws * expected_probability * (1 - expected_probability)
    standard_error_count = math.sqrt(variance) if variance > 0 else 0.0

    frequencies: Counter[int] = Counter()
    position_counts = [Counter() for _ in range(pick_count)]
    month_counts = {month: Counter() for month in range(1, 13)}
    month_draws = Counter()
    weekday_counts = {weekday: Counter() for weekday in range(7)}
    weekday_draws = Counter()
    last_seen_index: dict[int, int] = {}
    last_seen_date: dict[int, str] = {}
    gap_totals: Counter[int] = Counter()
    gap_counts: Counter[int] = Counter()
    max_gaps: Counter[int] = Counter()
    sums: list[int] = []
    spreads: list[int] = []
    odd_counts: Counter[int] = Counter()
    consecutive_counts: Counter[int] = Counter()

    for index, observation in enumerate(observations):
        values = tuple(sorted(observation.values))
        frequencies.update(values)
        month_draws[observation.draw_date.month] += 1
        month_counts[observation.draw_date.month].update(values)
        weekday_draws[observation.draw_date.weekday()] += 1
        weekday_counts[observation.draw_date.weekday()].update(values)
        sums.append(sum(values))
        spreads.append(max(values) - min(values))
        odd_counts[sum(value % 2 for value in values)] += 1
        consecutive_counts[
            sum(
                right - left == 1
                for left, right in zip(values, values[1:], strict=False)
            )
        ] += 1
        for position, value in enumerate(values):
            if position < len(position_counts):
                position_counts[position][value] += 1
            previous_index = last_seen_index.get(value)
            if previous_index is not None:
                gap = index - previous_index
                gap_totals[value] += gap
                gap_counts[value] += 1
                max_gaps[value] = max(max_gaps[value], gap)
            last_seen_index[value] = index
            last_seen_date[value] = observation.draw_date.isoformat()

    recent_window = min(1000, n_draws)
    recent_counts: Counter[int] = Counter()
    for observation in observations[-recent_window:]:
        recent_counts.update(observation.values)

    number_rows: list[dict[str, object]] = []
    p_values: list[float] = []
    for value in pool:
        count = frequencies[value]
        z_score = (count - expected_count) / standard_error_count if standard_error_count else 0.0
        p_value = 2 * (1 - NORMAL.cdf(abs(z_score)))
        p_values.append(p_value)
        wilson_low, wilson_high = _wilson_interval(count, n_draws)
        recent_expected = recent_window * expected_probability
        recent_variance = recent_window * expected_probability * (1 - expected_probability)
        recent_z = (
            (recent_counts[value] - recent_expected) / math.sqrt(recent_variance)
            if recent_variance
            else 0.0
        )
        number_rows.append(
            {
                "number": value,
                "count": count,
                "observed_rate": _round(count / n_draws),
                "expected_rate": _round(expected_probability),
                "rate_per_100_draws": _round(100 * count / n_draws),
                "z_score": _round(z_score),
                "p_value": _round(p_value, 8),
                "ci95_low": _round(wilson_low),
                "ci95_high": _round(wilson_high),
                "last_seen_date": last_seen_date.get(value),
                "draws_since": n_draws - 1 - last_seen_index.get(value, -1),
                "average_gap_draws": _round(
                    gap_totals[value] / gap_counts[value] if gap_counts[value] else 0
                ),
                "maximum_gap_draws": max_gaps[value],
                "recent_count": recent_counts[value],
                "recent_window_draws": recent_window,
                "recent_z_score": _round(recent_z),
            }
        )

    q_values = _benjamini_hochberg(p_values)
    for row, q_value in zip(number_rows, q_values, strict=True):
        row["q_value_bh"] = _round(q_value, 8)

    total_selections = n_draws * pick_count
    chi_square = sum(
        ((frequencies[value] - expected_count) ** 2) / expected_count for value in pool
    )
    entropy = _normalized_entropy(frequencies[value] for value in pool)
    position_rates = [
        {
            "position": position + 1,
            "values": [
                {
                    "number": value,
                    "count": counter[value],
                    "rate": _round(counter[value] / n_draws),
                }
                for value in pool
            ],
        }
        for position, counter in enumerate(position_counts)
    ]
    month_rates = [
        {
            "month": month,
            "draws": month_draws[month],
            "values": [
                {
                    "number": value,
                    "count": month_counts[month][value],
                    "rate_per_draw": _round(
                        month_counts[month][value] / month_draws[month]
                        if month_draws[month]
                        else 0
                    ),
                }
                for value in pool
            ],
        }
        for month in range(1, 13)
    ]
    weekday_rates = [
        {
            "weekday": weekday,
            "draws": weekday_draws[weekday],
            "values": [
                {
                    "number": value,
                    "count": weekday_counts[weekday][value],
                    "rate_per_draw": _round(
                        weekday_counts[weekday][value] / weekday_draws[weekday]
                        if weekday_draws[weekday]
                        else 0
                    ),
                }
                for value in pool
            ],
        }
        for weekday in range(7)
    ]

    special = _special_number_report(dataset)
    return {
        "pool": {
            "minimum": product.pool_min,
            "maximum": product.pool_max,
            "size": product.pool_size,
            "pick_count": pick_count,
            "expected_probability_per_draw": _round(expected_probability),
        },
        "uniformity": {
            "chi_square": _round(chi_square),
            "degrees_of_freedom": product.pool_size - 1,
            "approximate_p_value": _round(
                _chi_square_survival_approx(chi_square, product.pool_size - 1),
                8,
            ),
            "cohens_w": _round(math.sqrt(chi_square / total_selections)),
            "normalized_entropy": _round(entropy, 8),
            "interpretation": _effect_label(math.sqrt(chi_square / total_selections)),
        },
        "numbers": number_rows,
        "positions": position_rates,
        "months": month_rates,
        "weekdays": weekday_rates,
        "structure": {
            "sum": _distribution_summary(sums),
            "spread": _distribution_summary(spreads),
            "odd_count_distribution": _counter_rows(odd_counts),
            "consecutive_pair_distribution": _counter_rows(consecutive_counts),
        },
        "pairs": _pair_report(dataset),
        "special_numbers": special,
    }


def _digit_sequence_report(dataset: ProductDataset) -> dict[str, object]:
    product = dataset.product
    sequence_length = product.sequence_length or 0
    observations = dataset.observations
    digit_counts = Counter()
    position_counts = [Counter() for _ in range(sequence_length)]
    exact_counts = Counter()
    sum_counts = Counter()
    unique_digit_counts = Counter()
    month_counts = {month: Counter() for month in range(1, 13)}
    month_outcomes = Counter()
    total_outcomes = 0

    for observation in observations:
        month = observation.draw_date.month
        for outcome in observation.outcomes:
            if len(outcome) != sequence_length or not outcome.isdigit():
                continue
            total_outcomes += 1
            exact_counts[outcome] += 1
            digits = [int(char) for char in outcome]
            digit_counts.update(digits)
            month_counts[month].update(digits)
            month_outcomes[month] += 1
            sum_counts[sum(digits)] += 1
            unique_digit_counts[len(set(digits))] += 1
            for position, digit in enumerate(digits):
                position_counts[position][digit] += 1

    expected_per_digit = total_outcomes * sequence_length / 10 if total_outcomes else 0
    chi_square = (
        sum(
            ((digit_counts[digit] - expected_per_digit) ** 2) / expected_per_digit
            for digit in range(10)
        )
        if expected_per_digit
        else 0
    )
    total_digits = total_outcomes * sequence_length
    position_rows = [
        {
            "position": position + 1,
            "values": [
                {
                    "digit": digit,
                    "count": counter[digit],
                    "rate": _round(counter[digit] / total_outcomes)
                    if total_outcomes
                    else 0,
                }
                for digit in range(10)
            ],
            "normalized_entropy": _round(
                _normalized_entropy(counter[digit] for digit in range(10)),
                8,
            ),
        }
        for position, counter in enumerate(position_counts)
    ]
    month_rows = [
        {
            "month": month,
            "outcomes": month_outcomes[month],
            "values": [
                {
                    "digit": digit,
                    "count": month_counts[month][digit],
                    "rate_per_position": _round(
                        month_counts[month][digit]
                        / (month_outcomes[month] * sequence_length)
                        if month_outcomes[month]
                        else 0
                    ),
                }
                for digit in range(10)
            ],
        }
        for month in range(1, 13)
    ]

    bingo_total_test = None
    if product.slug == "bingo18":
        expected_sum_probabilities = _digit_sum_probabilities(sequence_length)
        bingo_chi_square = 0.0
        for total, probability in expected_sum_probabilities.items():
            expected = len(observations) * probability
            if expected:
                bingo_chi_square += ((sum_counts[total] - expected) ** 2) / expected
        bingo_total_test = {
            "chi_square": _round(bingo_chi_square),
            "degrees_of_freedom": len(expected_sum_probabilities) - 1,
            "approximate_p_value": _round(
                _chi_square_survival_approx(
                    bingo_chi_square,
                    len(expected_sum_probabilities) - 1,
                ),
                8,
            ),
            "expected": [
                {
                    "sum": total,
                    "probability": _round(probability, 8),
                    "observed_count": sum_counts[total],
                }
                for total, probability in expected_sum_probabilities.items()
            ],
        }

    return {
        "sequence_length": sequence_length,
        "draws": len(observations),
        "outcomes": total_outcomes,
        "average_outcomes_per_draw": _round(total_outcomes / len(observations)),
        "uniformity": {
            "chi_square": _round(chi_square),
            "degrees_of_freedom": 9,
            "approximate_p_value": _round(_chi_square_survival_approx(chi_square, 9), 8),
            "cohens_w": _round(math.sqrt(chi_square / total_digits)) if total_digits else 0,
            "normalized_entropy": _round(
                _normalized_entropy(digit_counts[digit] for digit in range(10)),
                8,
            ),
        },
        "digits": [
            {
                "digit": digit,
                "count": digit_counts[digit],
                "rate": _round(digit_counts[digit] / total_digits) if total_digits else 0,
            }
            for digit in range(10)
        ],
        "positions": position_rows,
        "months": month_rows,
        "sum_distribution": _counter_rows(sum_counts),
        "unique_digit_distribution": _counter_rows(unique_digit_counts),
        "most_frequent_sequences": [
            {"sequence": sequence, "count": count}
            for sequence, count in exact_counts.most_common(20)
        ],
        "bingo_total_test": bingo_total_test,
    }


def _pair_report(dataset: ProductDataset) -> dict[str, object] | None:
    product = dataset.product
    if product.slug == "keno":
        return None
    pair_counts: Counter[tuple[int, int]] = Counter()
    for observation in dataset.observations:
        pair_counts.update(combinations(sorted(observation.values), 2))
    probability = (product.pick_count or 0) * ((product.pick_count or 0) - 1) / (
        product.pool_size * (product.pool_size - 1)
    )
    expected = len(dataset.observations) * probability
    rows = []
    for pair, count in pair_counts.items():
        z_score = (count - expected) / math.sqrt(expected * (1 - probability))
        rows.append(
            {
                "pair": list(pair),
                "count": count,
                "expected_count": _round(expected),
                "ratio_to_expected": _round(count / expected),
                "z_score": _round(z_score),
            }
        )
    rows.sort(key=lambda item: float(item["z_score"]), reverse=True)
    return {
        "expected_probability_per_draw": _round(probability),
        "highest_residuals": rows[:15],
        "lowest_residuals": list(reversed(rows[-15:])),
        "warning": "Các cặp được xếp hạng sau khi đã xem dữ liệu và chưa tự động là tín hiệu dự báo.",
    }


def _special_number_report(dataset: ProductDataset) -> dict[str, object] | None:
    product = dataset.product
    if not product.special_count or product.special_min is None or product.special_max is None:
        return None
    observations = [
        item for item in dataset.observations if len(item.special_values) == product.special_count
    ]
    counts = Counter(value for item in observations for value in item.special_values)
    pool = list(range(product.special_min, product.special_max + 1))
    expected_probability = product.special_count / len(pool)
    return {
        "minimum": product.special_min,
        "maximum": product.special_max,
        "observed_draws": len(observations),
        "values": [
            {
                "number": value,
                "count": counts[value],
                "rate": _round(counts[value] / len(observations)) if observations else 0,
                "expected_rate": _round(expected_probability),
            }
            for value in pool
        ],
    }


def _recent_draw(observation, product: AnalyticsProduct) -> dict[str, object]:
    if product.kind.value == "number_set":
        result: object = {
            "numbers": list(observation.values),
            "special_numbers": list(observation.special_values),
        }
    else:
        result = {"outcomes": list(observation.outcomes)}
    return {
        "draw_id": observation.draw_id,
        "draw_date": observation.draw_date.isoformat(),
        "result": result,
    }


def _distribution_summary(values: list[int]) -> dict[str, object]:
    if not values:
        return {"count": 0}
    sorted_values = sorted(values)
    return {
        "count": len(values),
        "minimum": sorted_values[0],
        "p10": _quantile(sorted_values, 0.10),
        "median": _quantile(sorted_values, 0.50),
        "mean": _round(fmean(values)),
        "p90": _quantile(sorted_values, 0.90),
        "maximum": sorted_values[-1],
        "histogram": _histogram(values, max_bins=24),
    }


def _histogram(values: list[int], max_bins: int) -> list[dict[str, int]]:
    minimum = min(values)
    maximum = max(values)
    width = max(1, math.ceil((maximum - minimum + 1) / max_bins))
    bins: Counter[int] = Counter((value - minimum) // width for value in values)
    maximum_bin = (maximum - minimum) // width
    return [
        {
            "start": minimum + index * width,
            "end": min(maximum, minimum + (index + 1) * width - 1),
            "count": bins[index],
        }
        for index in range(maximum_bin + 1)
    ]


def _counter_rows(counter: Counter[int]) -> list[dict[str, int]]:
    return [{"value": value, "count": counter[value]} for value in sorted(counter)]


def _wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if not trials:
        return 0.0, 0.0
    rate = successes / trials
    denominator = 1 + z * z / trials
    center = (rate + z * z / (2 * trials)) / denominator
    margin = (
        z
        * math.sqrt(rate * (1 - rate) / trials + z * z / (4 * trials * trials))
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _benjamini_hochberg(p_values: list[float]) -> list[float]:
    count = len(p_values)
    ranked = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [1.0] * count
    running_min = 1.0
    for reverse_index in range(count - 1, -1, -1):
        original_index, p_value = ranked[reverse_index]
        rank = reverse_index + 1
        running_min = min(running_min, p_value * count / rank)
        adjusted[original_index] = min(1.0, running_min)
    return adjusted


def _chi_square_survival_approx(value: float, degrees_of_freedom: int) -> float:
    if value <= 0 or degrees_of_freedom <= 0:
        return 1.0
    transformed = (
        (value / degrees_of_freedom) ** (1 / 3)
        - (1 - 2 / (9 * degrees_of_freedom))
    ) / math.sqrt(2 / (9 * degrees_of_freedom))
    return max(0.0, min(1.0, 1 - NORMAL.cdf(transformed)))


def _normalized_entropy(counts: Iterable[int]) -> float:
    values = [count for count in counts if count > 0]
    total = sum(values)
    if total <= 0 or len(values) <= 1:
        return 0.0
    entropy = -sum((count / total) * math.log(count / total) for count in values)
    return entropy / math.log(len(values))


def _digit_sum_probabilities(length: int) -> dict[int, float]:
    counts = Counter({0: 1})
    for _ in range(length):
        next_counts = Counter()
        for subtotal, count in counts.items():
            for digit in range(10):
                next_counts[subtotal + digit] += count
        counts = next_counts
    total = 10**length
    return {value: count / total for value, count in sorted(counts.items())}


def _quantile(sorted_values: list[int], probability: float) -> float:
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = position - lower
    return _round(sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction)


def _effect_label(value: float) -> str:
    if value < 0.05:
        return "rất nhỏ"
    if value < 0.10:
        return "nhỏ"
    if value < 0.30:
        return "vừa"
    return "lớn"


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)
