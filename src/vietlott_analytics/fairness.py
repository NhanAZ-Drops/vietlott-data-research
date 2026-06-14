from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Iterable, Iterator
from itertools import combinations
from statistics import NormalDist, fmean, stdev
from typing import Any

from .catalog import AnalysisKind
from .io import ProductDataset

AUDIT_SUITE_VERSION = "1.0.0"
NORMAL = NormalDist()

FAMILY_DESCRIPTIONS = [
    {
        "id": "distribution_fit",
        "label": "Khớp phân bố",
        "plain_language": "Đếm xem các số hoặc chữ số có lệch khỏi tần suất kỳ vọng hay không.",
    },
    {
        "id": "sequence_dependence",
        "label": "Phụ thuộc theo thời gian",
        "plain_language": "Kiểm tra kết quả gần nhau có tạo thành chuỗi dễ đoán hay không.",
    },
    {
        "id": "seasonality",
        "label": "Mùa vụ và lịch",
        "plain_language": "So sánh theo tháng để xem có nhóm thời gian nào lệch rõ hơn phần còn lại.",
    },
    {
        "id": "change_point",
        "label": "Điểm đổi chế độ",
        "plain_language": "So nửa đầu với nửa sau để tìm dấu hiệu quy trình thay đổi.",
    },
    {
        "id": "co_occurrence",
        "label": "Đồng xuất hiện",
        "plain_language": "Kiểm tra các cặp số hoặc mẫu lặp xuất hiện nhiều hơn mức nền hay không.",
    },
]

DEFERRED_METHODS = [
    {
        "family": "randomness_testing",
        "methods": ["NIST Statistical Test Suite", "Dieharder", "TestU01"],
        "reason": (
            "Các bộ này phù hợp với chuỗi bit dài và cần ánh xạ kết quả xổ số sang bit thật cẩn thận. "
            "Nếu ánh xạ kém, kết luận dễ phản ánh cách mã hóa hơn là dữ liệu gốc."
        ),
    },
    {
        "family": "heavy_models",
        "methods": ["Hidden Markov Model", "MCMC", "LSTM", "Transformer", "Graph Neural Network"],
        "reason": (
            "Nhóm này tốn tài nguyên, khó giải thích với người đọc phổ thông và có nguy cơ học nhiễu "
            "trên dữ liệu vốn được kỳ vọng là không có tín hiệu dự báo."
        ),
    },
    {
        "family": "external_evidence",
        "methods": ["Causal audit by machine id", "Ball-set audit", "Temperature and maintenance model"],
        "reason": (
            "Cần dữ liệu vận hành không có trong nguồn công khai hiện tại như mã máy quay, bộ bi, "
            "bảo trì, nhiệt độ và quy trình kiểm định thiết bị."
        ),
    },
]


def build_product_audit(dataset: ProductDataset) -> dict[str, Any]:
    product = dataset.product
    tests = (
        _number_set_tests(dataset)
        if product.kind is AnalysisKind.NUMBER_SET
        else _digit_sequence_tests(dataset)
    )
    _apply_local_correction(tests)
    _refresh_test_statuses(tests)
    return _audit_payload(dataset, tests)


def finalize_audits(product_reports: list[dict[str, Any]]) -> dict[str, Any]:
    tests = [
        test
        for report in product_reports
        for test in report.get("audit", {}).get("tests", [])
        if isinstance(test.get("p_value"), (int, float))
    ]
    q_values = _benjamini_hochberg([float(test["p_value"]) for test in tests])
    for test, q_value in zip(tests, q_values, strict=True):
        test["q_value_global_bh"] = _round(q_value, 8)

    for report in product_reports:
        audit = report.get("audit")
        if not isinstance(audit, dict):
            continue
        _refresh_test_statuses(audit["tests"])
        audit["status_counts"] = dict(Counter(test["status"] for test in audit["tests"]))
        audit["strongest_signal"] = _strongest_signal(audit["tests"])
        audit["conclusion"] = _audit_conclusion(audit["tests"])

    return {
        "schema_version": 1,
        "suite_version": AUDIT_SUITE_VERSION,
        "title": "Bộ kiểm định công bằng thống kê",
        "scope": (
            "Kiểm tra dấu hiệu lệch khỏi mô hình ngẫu nhiên trên dữ liệu công khai. "
            "Đây không phải kết luận pháp lý hay kiểm toán vận hành."
        ),
        "families": FAMILY_DESCRIPTIONS,
        "deferred_methods": DEFERRED_METHODS,
        "summary": _global_summary(product_reports),
        "products": [
            {
                "slug": report["product"]["slug"],
                "name": report["product"]["name"],
                "history_draws": report["audit"]["history_draws"],
                "status_counts": report["audit"]["status_counts"],
                "strongest_signal": report["audit"]["strongest_signal"],
                "conclusion": report["audit"]["conclusion"],
                "next_recommended_audit_after_draws": report["audit"][
                    "next_recommended_audit_after_draws"
                ],
            }
            for report in product_reports
        ],
    }


def audit_log_events(product_reports: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for report in product_reports:
        audit = report["audit"]
        product = report["product"]
        for test in audit["tests"]:
            yield {
                "schema_version": 1,
                "event_type": "fairness_audit_test",
                "suite_version": AUDIT_SUITE_VERSION,
                "product": product["slug"],
                "product_name": product["name"],
                "snapshot_id": audit["snapshot_id"],
                "history_draws": audit["history_draws"],
                "latest_draw_id": audit["latest_draw_id"],
                "latest_date": audit["latest_date"],
                "audit_interval_draws": audit["audit_interval_draws"],
                "test_id": test["id"],
                "family": test["family"],
                "algorithm": test["algorithm"],
                "status": test["status"],
                "statistic": test.get("statistic"),
                "p_value": test.get("p_value"),
                "q_value_bh": test.get("q_value_bh"),
                "q_value_global_bh": test.get("q_value_global_bh"),
                "effect_size": test.get("effect_size"),
                "interpretation": test["interpretation"],
            }


def dump_jsonl(events: Iterable[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(
            event,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
        for event in events
    )


def _audit_payload(dataset: ProductDataset, tests: list[dict[str, Any]]) -> dict[str, Any]:
    latest = dataset.latest
    interval = _audit_interval(dataset)
    return {
        "schema_version": 1,
        "suite_version": AUDIT_SUITE_VERSION,
        "title": "Bộ kiểm định công bằng thống kê",
        "scope": (
            "Các kiểm định chỉ dùng dữ liệu công khai đã xác nhận. Kết quả phát hiện bất thường "
            "là tín hiệu cần đọc tiếp, không phải bằng chứng gian lận hay kết luận vận hành."
        ),
        "snapshot_id": _snapshot_id(dataset),
        "history_draws": len(dataset.observations),
        "latest_draw_id": latest.draw_id,
        "latest_date": latest.draw_date.isoformat(),
        "audit_interval_draws": interval,
        "next_recommended_audit_after_draws": len(dataset.observations) + interval,
        "families": FAMILY_DESCRIPTIONS,
        "status_counts": dict(Counter(test["status"] for test in tests)),
        "strongest_signal": _strongest_signal(tests),
        "conclusion": _audit_conclusion(tests),
        "tests": tests,
    }


def _number_set_tests(dataset: ProductDataset) -> list[dict[str, Any]]:
    product = dataset.product
    observations = dataset.observations
    pool = list(range(product.pool_min or 1, (product.pool_max or 0) + 1))
    pick_count = product.pick_count or 0
    frequencies = Counter(value for observation in observations for value in observation.values)
    draw_sums = [sum(observation.values) for observation in observations]
    expected_per_number = len(observations) * pick_count / product.pool_size
    total_selections = len(observations) * pick_count

    tests = [
        _chi_square_test(
            test_id="number_marginal_chi_square",
            family="distribution_fit",
            algorithm="Chi-Square Goodness-of-Fit Test",
            label="Tần suất từng số so với phân bố đều",
            plain_language=(
                "Nếu hệ thống công bằng theo mô hình đồng đều, mỗi số dài hạn nên xuất hiện gần cùng số lần."
            ),
            observed=[frequencies[value] for value in pool],
            expected=[expected_per_number for _ in pool],
            sample_size=len(observations),
            effect_denominator=total_selections,
            effect_label="Cohen's w",
            practical_threshold=0.05,
        ),
        _g_test(
            test_id="number_marginal_g_test",
            family="distribution_fit",
            label="G-test cho tần suất từng số",
            plain_language="Cùng câu hỏi với chi-square, nhưng đo bằng tỷ lệ hợp lý likelihood.",
            observed=[frequencies[value] for value in pool],
            expected=[expected_per_number for _ in pool],
            sample_size=len(observations),
            effect_denominator=total_selections,
            practical_threshold=0.05,
        ),
        _runs_test(
            test_id="number_sum_runs",
            label="Runs test trên tổng bộ số",
            values=draw_sums,
            center=pick_count * ((product.pool_min or 1) + (product.pool_max or 0)) / 2,
            plain_language=(
                "Tổng bộ số không nên tạo thành chuỗi cao thấp quá đều hoặc quá gom cụm theo thời gian."
            ),
        ),
        _autocorrelation_test(
            test_id="number_sum_lag1_autocorrelation",
            label="Tự tương quan lag-1 của tổng bộ số",
            values=draw_sums,
            plain_language="Kiểm tra tổng kỳ liền trước có liên quan tuyến tính với tổng kỳ liền sau không.",
        ),
        _split_half_change_test(
            test_id="number_sum_split_half_change",
            label="So nửa đầu và nửa sau bằng tổng bộ số",
            values=draw_sums,
            plain_language=(
                "Nếu quy trình ổn định, trung bình tổng bộ số giữa hai nửa lịch sử "
                "không nên lệch lớn."
            ),
        ),
        _month_heterogeneity_number_test(dataset, pool, frequencies),
        _current_gap_test(dataset),
        _pair_co_occurrence_test(dataset),
        _odd_count_test(dataset),
    ]
    return [test for test in tests if test is not None]


def _digit_sequence_tests(dataset: ProductDataset) -> list[dict[str, Any]]:
    product = dataset.product
    length = product.sequence_length or 0
    observations = dataset.observations
    outcomes = [
        outcome
        for observation in observations
        for outcome in observation.outcomes
        if len(outcome) == length and outcome.isdigit()
    ]
    digit_counts = Counter(int(char) for outcome in outcomes for char in outcome)
    expected_per_digit = len(outcomes) * length / 10 if outcomes else 0
    numeric_values = [int(outcome) for outcome in outcomes]
    digit_sums = [sum(int(char) for char in outcome) for outcome in outcomes]

    tests = [
        _chi_square_test(
            test_id="digit_marginal_chi_square",
            family="distribution_fit",
            algorithm="Chi-Square Goodness-of-Fit Test",
            label="Tần suất chữ số 0 đến 9",
            plain_language="Mỗi chữ số nên xuất hiện gần 10% trên toàn bộ vị trí quan sát.",
            observed=[digit_counts[digit] for digit in range(10)],
            expected=[expected_per_digit for _ in range(10)],
            sample_size=len(outcomes),
            effect_denominator=len(outcomes) * length,
            effect_label="Cohen's w",
            practical_threshold=0.05,
        ),
        _g_test(
            test_id="digit_marginal_g_test",
            family="distribution_fit",
            label="G-test cho tần suất chữ số",
            plain_language="Đo độ lệch chữ số bằng tỷ lệ hợp lý likelihood.",
            observed=[digit_counts[digit] for digit in range(10)],
            expected=[expected_per_digit for _ in range(10)],
            sample_size=len(outcomes),
            effect_denominator=len(outcomes) * length,
            practical_threshold=0.05,
        ),
        _digit_position_test(dataset, outcomes),
        _digit_sum_distribution_test(outcomes, length),
        _runs_test(
            test_id="digit_value_runs",
            label="Runs test trên giá trị chuỗi",
            values=numeric_values,
            center=(10**length - 1) / 2,
            plain_language="Giá trị chuỗi không nên tạo thành nhịp cao thấp quá đều hoặc quá gom cụm.",
        ),
        _autocorrelation_test(
            test_id="digit_value_lag1_autocorrelation",
            label="Tự tương quan lag-1 của giá trị chuỗi",
            values=numeric_values,
            plain_language="Kiểm tra chuỗi trước có liên quan tuyến tính với chuỗi ngay sau không.",
        ),
        _split_half_change_test(
            test_id="digit_sum_split_half_change",
            label="So nửa đầu và nửa sau bằng tổng chữ số",
            values=digit_sums,
            plain_language=(
                "Nếu quy trình ổn định, trung bình tổng chữ số giữa hai nửa lịch sử "
                "không nên lệch lớn."
            ),
        ),
        _month_heterogeneity_digit_test(dataset),
        _repeat_rate_test(outcomes, length),
    ]
    return [test for test in tests if test is not None]


def _chi_square_test(
    *,
    test_id: str,
    family: str,
    algorithm: str,
    label: str,
    plain_language: str,
    observed: list[float],
    expected: list[float],
    sample_size: int,
    effect_denominator: float,
    effect_label: str,
    practical_threshold: float,
) -> dict[str, Any] | None:
    pairs = [(obs, exp) for obs, exp in zip(observed, expected, strict=True) if exp > 0]
    if len(pairs) < 2:
        return None
    statistic = sum((obs - exp) ** 2 / exp for obs, exp in pairs)
    degrees = len(pairs) - 1
    effect = math.sqrt(statistic / effect_denominator) if effect_denominator else 0.0
    return _test_result(
        test_id=test_id,
        family=family,
        algorithm=algorithm,
        label=label,
        plain_language=plain_language,
        statistic_name="chi_square",
        statistic=statistic,
        degrees_of_freedom=degrees,
        p_value=_chi_square_survival_approx(statistic, degrees),
        effect_size_name=effect_label,
        effect_size=effect,
        practical_threshold=practical_threshold,
        sample_size=sample_size,
    )


def _g_test(
    *,
    test_id: str,
    family: str,
    label: str,
    plain_language: str,
    observed: list[float],
    expected: list[float],
    sample_size: int,
    effect_denominator: float,
    practical_threshold: float,
) -> dict[str, Any] | None:
    terms = [
        obs * math.log(obs / exp)
        for obs, exp in zip(observed, expected, strict=True)
        if obs > 0 and exp > 0
    ]
    if not terms:
        return None
    statistic = 2 * sum(terms)
    degrees = sum(1 for exp in expected if exp > 0) - 1
    effect = math.sqrt(statistic / effect_denominator) if effect_denominator else 0.0
    return _test_result(
        test_id=test_id,
        family=family,
        algorithm="G-Test (Likelihood-Ratio Test)",
        label=label,
        plain_language=plain_language,
        statistic_name="g",
        statistic=statistic,
        degrees_of_freedom=degrees,
        p_value=_chi_square_survival_approx(statistic, degrees),
        effect_size_name="likelihood w",
        effect_size=effect,
        practical_threshold=practical_threshold,
        sample_size=sample_size,
    )


def _runs_test(
    *,
    test_id: str,
    label: str,
    values: list[int],
    center: float,
    plain_language: str,
) -> dict[str, Any] | None:
    signs = [1 if value > center else 0 if value < center else None for value in values]
    signs = [sign for sign in signs if sign is not None]
    n1 = sum(signs)
    n0 = len(signs) - n1
    if n1 < 2 or n0 < 2:
        return None
    runs = 1 + sum(left != right for left, right in zip(signs, signs[1:], strict=False))
    total = n0 + n1
    expected = 1 + (2 * n0 * n1) / total
    variance = (
        2
        * n0
        * n1
        * (2 * n0 * n1 - total)
        / (total * total * (total - 1))
    )
    z_score = (runs - expected) / math.sqrt(variance) if variance > 0 else 0.0
    return _test_result(
        test_id=test_id,
        family="sequence_dependence",
        algorithm="Wald-Wolfowitz Runs Test",
        label=label,
        plain_language=plain_language,
        statistic_name="z_score",
        statistic=z_score,
        p_value=_two_sided_normal_p(z_score),
        effect_size_name="absolute z per sqrt(n)",
        effect_size=abs(z_score) / math.sqrt(total),
        practical_threshold=0.10,
        sample_size=total,
        parameters={"center": _round(center), "runs": runs, "expected_runs": _round(expected)},
    )


def _autocorrelation_test(
    *,
    test_id: str,
    label: str,
    values: list[int],
    plain_language: str,
) -> dict[str, Any] | None:
    if len(values) < 8:
        return None
    left = values[:-1]
    right = values[1:]
    coefficient = _correlation(left, right)
    z_score = coefficient * math.sqrt(len(left))
    return _test_result(
        test_id=test_id,
        family="sequence_dependence",
        algorithm="Lag-1 Autocorrelation Test",
        label=label,
        plain_language=plain_language,
        statistic_name="autocorrelation",
        statistic=coefficient,
        p_value=_two_sided_normal_p(z_score),
        effect_size_name="absolute correlation",
        effect_size=abs(coefficient),
        practical_threshold=0.05,
        sample_size=len(left),
        parameters={"lag": 1},
    )


def _split_half_change_test(
    *,
    test_id: str,
    label: str,
    values: list[int],
    plain_language: str,
) -> dict[str, Any] | None:
    if len(values) < 20:
        return None
    midpoint = len(values) // 2
    first = values[:midpoint]
    second = values[midpoint:]
    if len(first) < 2 or len(second) < 2:
        return None
    first_sd = stdev(first)
    second_sd = stdev(second)
    standard_error = math.sqrt((first_sd**2 / len(first)) + (second_sd**2 / len(second)))
    difference = fmean(second) - fmean(first)
    z_score = difference / standard_error if standard_error else 0.0
    pooled = math.sqrt((first_sd**2 + second_sd**2) / 2) if first_sd or second_sd else 0.0
    effect = abs(difference) / pooled if pooled else 0.0
    return _test_result(
        test_id=test_id,
        family="change_point",
        algorithm="Split-Half Change-Point Test",
        label=label,
        plain_language=plain_language,
        statistic_name="z_score",
        statistic=z_score,
        p_value=_two_sided_normal_p(z_score),
        effect_size_name="standardized mean difference",
        effect_size=effect,
        practical_threshold=0.15,
        sample_size=len(values),
        parameters={
            "first_half_mean": _round(fmean(first)),
            "second_half_mean": _round(fmean(second)),
        },
    )


def _month_heterogeneity_number_test(
    dataset: ProductDataset,
    pool: list[int],
    frequencies: Counter[int],
) -> dict[str, Any] | None:
    product = dataset.product
    month_counts = {month: Counter() for month in range(1, 13)}
    month_draws = Counter()
    for observation in dataset.observations:
        month = observation.draw_date.month
        month_draws[month] += 1
        month_counts[month].update(observation.values)
    months = [month for month in range(1, 13) if month_draws[month] > 0]
    if len(months) < 2:
        return None
    statistic = 0.0
    cells = 0
    for month in months:
        expected_per_number = month_draws[month] * (product.pick_count or 0) / product.pool_size
        for value in pool:
            if frequencies[value] == 0 or expected_per_number <= 0:
                continue
            statistic += (month_counts[month][value] - expected_per_number) ** 2 / expected_per_number
            cells += 1
    degrees = max(1, (len(months) - 1) * (len(pool) - 1))
    total = len(dataset.observations) * (product.pick_count or 0)
    return _test_result(
        test_id="number_month_heterogeneity",
        family="seasonality",
        algorithm="Month-by-Number Chi-Square Test",
        label="Tần suất theo tháng",
        plain_language="So từng tháng với tần suất nền để xem mùa vụ lịch có nổi bật không.",
        statistic_name="chi_square",
        statistic=statistic,
        degrees_of_freedom=degrees,
        p_value=_chi_square_survival_approx(statistic, degrees),
        effect_size_name="Cramer's style w",
        effect_size=math.sqrt(statistic / total) if total else 0.0,
        practical_threshold=0.05,
        sample_size=len(dataset.observations),
        parameters={"months_with_data": len(months), "cells": cells},
    )


def _month_heterogeneity_digit_test(dataset: ProductDataset) -> dict[str, Any] | None:
    product = dataset.product
    length = product.sequence_length or 0
    month_counts = {month: Counter() for month in range(1, 13)}
    month_outcomes = Counter()
    for observation in dataset.observations:
        month = observation.draw_date.month
        for outcome in observation.outcomes:
            if len(outcome) != length or not outcome.isdigit():
                continue
            month_outcomes[month] += 1
            month_counts[month].update(int(char) for char in outcome)
    months = [month for month in range(1, 13) if month_outcomes[month] > 0]
    if len(months) < 2:
        return None
    statistic = 0.0
    total_digits = 0
    for month in months:
        expected = month_outcomes[month] * length / 10
        total_digits += month_outcomes[month] * length
        for digit in range(10):
            if expected > 0:
                statistic += (month_counts[month][digit] - expected) ** 2 / expected
    degrees = max(1, (len(months) - 1) * 9)
    return _test_result(
        test_id="digit_month_heterogeneity",
        family="seasonality",
        algorithm="Month-by-Digit Chi-Square Test",
        label="Tần suất chữ số theo tháng",
        plain_language="So từng tháng với tần suất nền của chữ số 0 đến 9.",
        statistic_name="chi_square",
        statistic=statistic,
        degrees_of_freedom=degrees,
        p_value=_chi_square_survival_approx(statistic, degrees),
        effect_size_name="Cramer's style w",
        effect_size=math.sqrt(statistic / total_digits) if total_digits else 0.0,
        practical_threshold=0.05,
        sample_size=sum(month_outcomes.values()),
        parameters={"months_with_data": len(months)},
    )


def _current_gap_test(dataset: ProductDataset) -> dict[str, Any] | None:
    product = dataset.product
    if not dataset.observations or not product.pick_count:
        return None
    last_seen = {}
    for index, observation in enumerate(dataset.observations):
        for value in observation.values:
            last_seen[value] = index
    pool = range(product.pool_min or 1, (product.pool_max or 0) + 1)
    gaps = {
        value: len(dataset.observations) - 1 - last_seen.get(value, -1)
        for value in pool
    }
    max_number, max_gap = max(gaps.items(), key=lambda item: item[1])
    probability = product.pick_count / product.pool_size
    single_tail = (1 - probability) ** max_gap
    any_tail = 1 - (1 - single_tail) ** product.pool_size
    expected_gap = 1 / probability if probability else 0
    return _test_result(
        test_id="number_current_gap_geometric",
        family="sequence_dependence",
        algorithm="Geometric Waiting-Time Tail Test",
        label="Số đang vắng lâu nhất",
        plain_language="Một số vắng lâu chưa đủ lạ nếu trong cả không gian số luôn có vài số đang vắng.",
        statistic_name="max_current_gap",
        statistic=float(max_gap),
        p_value=any_tail,
        effect_size_name="gap divided by expected gap",
        effect_size=max_gap / expected_gap if expected_gap else 0.0,
        practical_threshold=4.0,
        sample_size=len(dataset.observations),
        parameters={"number": max_number, "expected_gap_draws": _round(expected_gap)},
    )


def _pair_co_occurrence_test(dataset: ProductDataset) -> dict[str, Any] | None:
    product = dataset.product
    pick_count = product.pick_count or 0
    if pick_count < 2 or product.pool_size < 2:
        return None
    total_pair_observations = len(dataset.observations) * math.comb(pick_count, 2)
    if total_pair_observations > 3_000_000:
        return _skipped_test(
            test_id="number_pair_co_occurrence",
            family="co_occurrence",
            algorithm="Co-occurrence Pair Chi-Square Test",
            label="Đồng xuất hiện của các cặp số",
            plain_language=(
                "Tạm hoãn kiểm định cặp đầy đủ vì số cặp quá lớn cho workflow cập nhật thường xuyên."
            ),
            sample_size=len(dataset.observations),
            parameters={
                "pair_observations": total_pair_observations,
                "limit": 3_000_000,
            },
        )
    pair_counts: Counter[tuple[int, int]] = Counter()
    for observation in dataset.observations:
        pair_counts.update(combinations(sorted(observation.values), 2))
    all_pairs = list(combinations(range(product.pool_min or 1, (product.pool_max or 0) + 1), 2))
    probability = pick_count * (pick_count - 1) / (product.pool_size * (product.pool_size - 1))
    expected = len(dataset.observations) * probability
    if expected <= 0:
        return None
    statistic = sum(((pair_counts[pair] - expected) ** 2) / expected for pair in all_pairs)
    top_pair, top_count = max(pair_counts.items(), key=lambda item: item[1])
    return _test_result(
        test_id="number_pair_co_occurrence",
        family="co_occurrence",
        algorithm="Co-occurrence Pair Chi-Square Test",
        label="Đồng xuất hiện của các cặp số",
        plain_language=(
            "Kiểm tra mạng cặp số, nhưng cần đọc thận trọng vì các cặp trong cùng một kỳ không độc lập."
        ),
        statistic_name="chi_square",
        statistic=statistic,
        degrees_of_freedom=len(all_pairs) - 1,
        p_value=_chi_square_survival_approx(statistic, len(all_pairs) - 1),
        effect_size_name="pair co-occurrence w",
        effect_size=math.sqrt(statistic / total_pair_observations)
        if total_pair_observations
        else 0.0,
        practical_threshold=0.05,
        sample_size=len(dataset.observations),
        parameters={
            "pairs": len(all_pairs),
            "expected_count_per_pair": _round(expected),
            "highest_count_pair": list(top_pair),
            "highest_count": top_count,
        },
    )


def _odd_count_test(dataset: ProductDataset) -> dict[str, Any] | None:
    product = dataset.product
    pick_count = product.pick_count or 0
    if not pick_count:
        return None
    odd_numbers = sum(1 for value in range(product.pool_min or 1, (product.pool_max or 0) + 1) if value % 2)
    even_numbers = product.pool_size - odd_numbers
    denominator = math.comb(product.pool_size, pick_count)
    expected = {}
    for odd_count in range(pick_count + 1):
        if odd_count <= odd_numbers and pick_count - odd_count <= even_numbers:
            expected[odd_count] = (
                len(dataset.observations)
                * math.comb(odd_numbers, odd_count)
                * math.comb(even_numbers, pick_count - odd_count)
                / denominator
            )
    observed = Counter(sum(value % 2 for value in observation.values) for observation in dataset.observations)
    statistic = sum(
        ((observed[count] - expected_count) ** 2) / expected_count
        for count, expected_count in expected.items()
        if expected_count > 0
    )
    return _test_result(
        test_id="number_odd_count_hypergeometric",
        family="distribution_fit",
        algorithm="Hypergeometric Odd-Count Test",
        label="Phân bố chẵn lẻ trong một bộ số",
        plain_language="Trong một bộ chọn không lặp, số lượng số lẻ phải theo phân bố siêu bội.",
        statistic_name="chi_square",
        statistic=statistic,
        degrees_of_freedom=max(1, len(expected) - 1),
        p_value=_chi_square_survival_approx(statistic, max(1, len(expected) - 1)),
        effect_size_name="odd-count w",
        effect_size=math.sqrt(statistic / len(dataset.observations)) if dataset.observations else 0.0,
        practical_threshold=0.10,
        sample_size=len(dataset.observations),
    )


def _digit_position_test(dataset: ProductDataset, outcomes: list[str]) -> dict[str, Any] | None:
    product = dataset.product
    length = product.sequence_length or 0
    if not outcomes or not length:
        return None
    position_counts = [Counter() for _ in range(length)]
    for outcome in outcomes:
        for position, char in enumerate(outcome):
            position_counts[position][int(char)] += 1
    expected = len(outcomes) / 10
    statistic = sum(
        ((counter[digit] - expected) ** 2) / expected
        for counter in position_counts
        for digit in range(10)
        if expected > 0
    )
    return _test_result(
        test_id="digit_position_chi_square",
        family="distribution_fit",
        algorithm="Position-wise Chi-Square Test",
        label="Tần suất chữ số theo vị trí",
        plain_language="Mỗi vị trí của chuỗi nên có chữ số 0 đến 9 gần đều nhau.",
        statistic_name="chi_square",
        statistic=statistic,
        degrees_of_freedom=length * 9,
        p_value=_chi_square_survival_approx(statistic, length * 9),
        effect_size_name="position digit w",
        effect_size=math.sqrt(statistic / (len(outcomes) * length)),
        practical_threshold=0.05,
        sample_size=len(outcomes),
    )


def _digit_sum_distribution_test(outcomes: list[str], length: int) -> dict[str, Any] | None:
    if not outcomes or not length:
        return None
    probabilities = _digit_sum_probabilities(length)
    observed = Counter(sum(int(char) for char in outcome) for outcome in outcomes)
    statistic = 0.0
    for total, probability in probabilities.items():
        expected = len(outcomes) * probability
        if expected > 0:
            statistic += (observed[total] - expected) ** 2 / expected
    return _test_result(
        test_id="digit_sum_distribution",
        family="distribution_fit",
        algorithm="Digit-Sum Chi-Square Test",
        label="Phân bố tổng chữ số",
        plain_language="Tổng chữ số có hình dạng kỳ vọng riêng, không phải phân bố đều.",
        statistic_name="chi_square",
        statistic=statistic,
        degrees_of_freedom=len(probabilities) - 1,
        p_value=_chi_square_survival_approx(statistic, len(probabilities) - 1),
        effect_size_name="digit-sum w",
        effect_size=math.sqrt(statistic / len(outcomes)),
        practical_threshold=0.10,
        sample_size=len(outcomes),
    )


def _repeat_rate_test(outcomes: list[str], length: int) -> dict[str, Any] | None:
    if len(outcomes) < 2 or length <= 0:
        return None
    space = 10**length
    counts = Counter(outcomes)
    observed_pairs = sum(count * (count - 1) / 2 for count in counts.values())
    expected_pairs = len(outcomes) * (len(outcomes) - 1) / (2 * space)
    if expected_pairs <= 0:
        return None
    z_score = (observed_pairs - expected_pairs) / math.sqrt(expected_pairs)
    return _test_result(
        test_id="digit_repeat_poisson",
        family="co_occurrence",
        algorithm="Poisson Repeat-Rate Test",
        label="Tỷ lệ chuỗi lặp lại",
        plain_language=(
            "Trong không gian hữu hạn, chuỗi lặp là bình thường, nhưng tỷ lệ lặp quá cao "
            "cần xem lại."
        ),
        statistic_name="z_score",
        statistic=z_score,
        p_value=_two_sided_normal_p(z_score),
        effect_size_name="repeat pairs ratio",
        effect_size=observed_pairs / expected_pairs,
        practical_threshold=1.25,
        sample_size=len(outcomes),
        parameters={
            "observed_duplicate_pairs": int(observed_pairs),
            "expected_duplicate_pairs": _round(expected_pairs),
            "outcome_space": space,
        },
    )


def _test_result(
    *,
    test_id: str,
    family: str,
    algorithm: str,
    label: str,
    plain_language: str,
    statistic_name: str,
    statistic: float,
    p_value: float,
    effect_size_name: str,
    effect_size: float,
    practical_threshold: float,
    sample_size: int,
    degrees_of_freedom: int | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": test_id,
        "family": family,
        "algorithm": algorithm,
        "label": label,
        "plain_language": plain_language,
        "statistic_name": statistic_name,
        "statistic": _round(statistic),
        "degrees_of_freedom": degrees_of_freedom,
        "p_value": _round(max(0.0, min(1.0, p_value)), 8),
        "q_value_bh": None,
        "q_value_global_bh": None,
        "effect_size_name": effect_size_name,
        "effect_size": _round(effect_size),
        "practical_effect_threshold": practical_threshold,
        "sample_size": sample_size,
        "parameters": parameters or {},
        "status": "pending",
        "interpretation": "",
    }


def _skipped_test(
    *,
    test_id: str,
    family: str,
    algorithm: str,
    label: str,
    plain_language: str,
    sample_size: int,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": test_id,
        "family": family,
        "algorithm": algorithm,
        "label": label,
        "plain_language": plain_language,
        "statistic_name": None,
        "statistic": None,
        "degrees_of_freedom": None,
        "p_value": None,
        "q_value_bh": None,
        "q_value_global_bh": None,
        "effect_size_name": None,
        "effect_size": None,
        "practical_effect_threshold": None,
        "sample_size": sample_size,
        "parameters": parameters or {},
        "status": "skipped",
        "interpretation": "Tạm hoãn để giữ workflow tự động đủ nhẹ và có thể tái lập hằng ngày.",
    }


def _apply_local_correction(tests: list[dict[str, Any]]) -> None:
    indexed = [
        (index, float(test["p_value"]))
        for index, test in enumerate(tests)
        if isinstance(test.get("p_value"), (int, float))
    ]
    q_values = _benjamini_hochberg([p_value for _, p_value in indexed])
    for (index, _), q_value in zip(indexed, q_values, strict=True):
        tests[index]["q_value_bh"] = _round(q_value, 8)


def _refresh_test_statuses(tests: list[dict[str, Any]]) -> None:
    for test in tests:
        if test.get("status") == "skipped":
            continue
        q_value = test.get("q_value_global_bh") or test.get("q_value_bh") or 1.0
        effect = abs(float(test.get("effect_size") or 0.0))
        threshold = abs(float(test.get("practical_effect_threshold") or 0.0))
        if q_value < 0.01 and effect >= threshold:
            status = "review"
            interpretation = (
                "Tín hiệu vượt ngưỡng thống kê sau hiệu chỉnh và có độ lớn đáng đọc kỹ. "
                "Cần đối chiếu nguồn dữ liệu, giả định kiểm định và dữ liệu vận hành nếu có."
            )
        elif q_value < 0.05 or (threshold and effect >= threshold):
            status = "watch"
            interpretation = (
                "Có dấu hiệu cần theo dõi, nhưng chưa đủ để kết luận nguyên nhân hay khả năng dự đoán."
            )
        else:
            status = "pass"
            interpretation = "Chưa thấy sai lệch đủ mạnh theo tiêu chí đã khóa trước."
        test["status"] = status
        test["interpretation"] = interpretation


def _audit_conclusion(tests: list[dict[str, Any]]) -> str:
    counts = Counter(test["status"] for test in tests)
    if counts["review"]:
        return (
            f"Có {counts['review']} kiểm định cần đọc kỹ. Đây là tín hiệu thống kê, "
            "không phải kết luận về quy trình vận hành."
        )
    if counts["watch"]:
        return (
            f"Có {counts['watch']} kiểm định ở mức theo dõi. Chưa đủ bằng chứng để bác bỏ "
            "mô hình ngẫu nhiên theo cách thực dụng."
        )
    return "Chưa thấy kiểm định nào vượt ngưỡng theo dõi sau hiệu chỉnh nhiều kiểm định."


def _strongest_signal(tests: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not tests:
        return None
    ranked = sorted(
        tests,
        key=lambda test: (
            {"review": 0, "watch": 1, "pass": 2}.get(test["status"], 3),
            test.get("q_value_global_bh") or test.get("q_value_bh") or 1.0,
            -abs(float(test.get("effect_size") or 0.0)),
        ),
    )
    top = ranked[0]
    return {
        "id": top["id"],
        "label": top["label"],
        "algorithm": top["algorithm"],
        "status": top["status"],
        "p_value": top.get("p_value"),
        "q_value_bh": top.get("q_value_bh"),
        "q_value_global_bh": top.get("q_value_global_bh"),
        "effect_size": top.get("effect_size"),
        "interpretation": top["interpretation"],
    }


def _global_summary(product_reports: list[dict[str, Any]]) -> dict[str, Any]:
    all_tests = [
        test
        for report in product_reports
        for test in report.get("audit", {}).get("tests", [])
    ]
    counts = Counter(test["status"] for test in all_tests)
    products_with_review = [
        report["product"]["slug"]
        for report in product_reports
        if report.get("audit", {}).get("status_counts", {}).get("review", 0)
    ]
    products_with_watch = [
        report["product"]["slug"]
        for report in product_reports
        if report.get("audit", {}).get("status_counts", {}).get("watch", 0)
    ]
    return {
        "product_count": len(product_reports),
        "test_count": len(all_tests),
        "status_counts": dict(counts),
        "products_with_review": products_with_review,
        "products_with_watch": products_with_watch,
        "strongest_signal": _strongest_signal(all_tests),
        "conclusion": _global_conclusion(counts),
    }


def _global_conclusion(counts: Counter[str]) -> str:
    if counts["review"]:
        return (
            f"Có {counts['review']} kiểm định ở mức cần đọc kỹ trên toàn bộ sản phẩm. "
            "Cần xem từng phép thử trước khi diễn giải."
        )
    if counts["watch"]:
        return (
            f"Có {counts['watch']} kiểm định ở mức theo dõi. Bộ dữ liệu hiện chưa đủ để kết luận "
            "về uy tín vận hành, nhưng đủ để lập danh sách tín hiệu cần quan sát tiếp."
        )
    return (
        "Tại snapshot hiện tại, bộ kiểm định chưa phát hiện sai lệch đủ mạnh sau hiệu chỉnh "
        "nhiều kiểm định."
    )


def _audit_interval(dataset: ProductDataset) -> int:
    if dataset.product.slug in {"keno", "bingo18"}:
        return 500
    if dataset.product.kind is AnalysisKind.DIGIT_SEQUENCE:
        return 100
    return 25


def _snapshot_id(dataset: ProductDataset) -> str:
    latest = dataset.latest
    payload = "|".join(
        (
            dataset.product.slug,
            str(len(dataset.observations)),
            latest.draw_id,
            latest.draw_date.isoformat(),
            dataset.fingerprint,
        )
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


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


def _two_sided_normal_p(z_score: float) -> float:
    return max(0.0, min(1.0, 2 * (1 - NORMAL.cdf(abs(z_score)))))


def _correlation(left: list[int], right: list[int]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_mean = fmean(left)
    right_mean = fmean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=True))
    left_denominator = math.sqrt(sum((x - left_mean) ** 2 for x in left))
    right_denominator = math.sqrt(sum((y - right_mean) ** 2 for y in right))
    denominator = left_denominator * right_denominator
    return numerator / denominator if denominator else 0.0


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


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)
