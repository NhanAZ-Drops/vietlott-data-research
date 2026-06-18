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

AUDIT_SUITE_VERSION = "2.0.0"
NORMAL = NormalDist()
DIGIT_PERIOD_SEGMENTS = 3
DIGIT_PERIOD_MIN_DRAWS = 30
DIGIT_PERIOD_TOP_RESIDUALS = 5

TIER_LABELS = {
    "first": "Giải nhất",
    "second": "Giải nhì",
    "third": "Giải ba",
    "special": "Giải đặc biệt",
    "consolation_1": "Giải khuyến khích 1",
    "consolation_2": "Giải khuyến khích 2",
}

TIER_ORDER = {
    "special": 0,
    "first": 1,
    "second": 2,
    "third": 3,
    "consolation_1": 4,
    "consolation_2": 5,
}

RESULT_TYPE_DESCRIPTIONS = {
    "full_sequence": {
        "label": "Chuỗi đầy đủ",
        "usable_for_position_audit": True,
        "plain_language": "Đủ số chữ số để đi vào kiểm định vị trí.",
    },
    "wildcard_prefix": {
        "label": "Ký hiệu X ở đầu",
        "usable_for_position_audit": False,
        "plain_language": (
            "Đây là luật trùng hậu tố như X589 hoặc XX89, không phải chuỗi đầy đủ "
            "để kiểm định từng vị trí."
        ),
    },
    "unusable": {
        "label": "Không dùng được",
        "usable_for_position_audit": False,
        "plain_language": "Giá trị không khớp cấu trúc chuỗi chữ số đã khóa.",
    },
}

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

DEPENDENCY_FAMILY_DESCRIPTIONS = [
    {
        "id": "number_frequency_history",
        "label": "Tần suất số theo lịch sử",
        "plain_language": (
            "Các phép kiểm cùng đọc lịch sử xuất hiện của từng số, từ tổng tần suất "
            "đến tháng quay và khoảng vắng hiện tại."
        ),
        "correction_scope": "number-set marginal counts, calendar strata and gap history",
    },
    {
        "id": "number_ordered_summary",
        "label": "Chuỗi tổng bộ số",
        "plain_language": (
            "Các phép kiểm dùng cùng chuỗi tổng của từng kỳ để đọc nhịp cao-thấp, "
            "tự tương quan và đổi chế độ theo thời gian."
        ),
        "correction_scope": "draw-order sum statistics for number-set products",
    },
    {
        "id": "number_within_draw_structure",
        "label": "Cấu trúc trong cùng kỳ",
        "plain_language": (
            "Các phép kiểm dùng đặc trưng sinh ra từ cùng một bộ số trong một kỳ, "
            "như cặp đồng xuất hiện hoặc số lượng số lẻ."
        ),
        "correction_scope": "within-draw combination structure for number-set products",
    },
    {
        "id": "digit_frequency_distribution",
        "label": "Tần suất chữ số",
        "plain_language": (
            "Các phép kiểm cùng đọc số lần xuất hiện chữ số, có thể gộp toàn chuỗi, "
            "tách theo vị trí hoặc tách theo tháng."
        ),
        "correction_scope": "digit counts, position counts and calendar strata",
    },
    {
        "id": "digit_ordered_sequence",
        "label": "Chuỗi kết quả theo thời gian",
        "plain_language": (
            "Các phép kiểm dùng thứ tự kỳ quay của chuỗi chữ số để đọc nhịp, tự tương "
            "quan hoặc đổi chế độ."
        ),
        "correction_scope": "draw-order value and digit-sum statistics",
    },
    {
        "id": "digit_sum_structure",
        "label": "Tổng chữ số trong kết quả",
        "plain_language": "Kiểm tra phân bố tổng chữ số của từng kết quả.",
        "correction_scope": "within-outcome digit sums",
    },
    {
        "id": "digit_repeat_structure",
        "label": "Lặp chuỗi kết quả",
        "plain_language": "Kiểm tra số cặp kết quả trùng nhau trong không gian hữu hạn.",
        "correction_scope": "duplicate outcome pairs",
    },
]

TEST_DEPENDENCY_PROFILES = {
    "number_marginal_chi_square": {
        "dependency_family": "number_frequency_history",
        "dependency_cluster": "number_marginal_uniformity",
        "dependency_tags": ["number_set", "marginal_counts", "pooled_counts"],
        "data_view": "one count per drawn number across the full confirmed history",
    },
    "number_marginal_g_test": {
        "dependency_family": "number_frequency_history",
        "dependency_cluster": "number_marginal_uniformity",
        "dependency_tags": ["number_set", "marginal_counts", "pooled_counts"],
        "data_view": "one count per drawn number across the full confirmed history",
    },
    "number_sum_runs": {
        "dependency_family": "number_ordered_summary",
        "dependency_cluster": "number_sum_order",
        "dependency_tags": ["number_set", "ordered_draws", "draw_sum"],
        "data_view": "ordered series of draw sums",
    },
    "number_sum_lag1_autocorrelation": {
        "dependency_family": "number_ordered_summary",
        "dependency_cluster": "number_sum_order",
        "dependency_tags": ["number_set", "ordered_draws", "draw_sum"],
        "data_view": "ordered series of draw sums",
    },
    "number_sum_split_half_change": {
        "dependency_family": "number_ordered_summary",
        "dependency_cluster": "number_sum_change",
        "dependency_tags": ["number_set", "ordered_draws", "draw_sum", "change_point"],
        "data_view": "first-half and second-half draw sums",
    },
    "number_month_heterogeneity": {
        "dependency_family": "number_frequency_history",
        "dependency_cluster": "number_calendar_counts",
        "dependency_tags": ["number_set", "marginal_counts", "calendar_strata"],
        "data_view": "drawn number counts stratified by calendar month",
    },
    "number_current_gap_geometric": {
        "dependency_family": "number_frequency_history",
        "dependency_cluster": "number_current_gap",
        "dependency_tags": ["number_set", "marginal_history", "tail_gap"],
        "data_view": "current waiting time for each number",
    },
    "number_pair_co_occurrence": {
        "dependency_family": "number_within_draw_structure",
        "dependency_cluster": "number_pair_structure",
        "dependency_tags": ["number_set", "within_draw", "pair_counts"],
        "data_view": "pairs formed inside each draw",
    },
    "number_odd_count_hypergeometric": {
        "dependency_family": "number_within_draw_structure",
        "dependency_cluster": "number_parity_structure",
        "dependency_tags": ["number_set", "within_draw", "parity_counts"],
        "data_view": "odd-number count inside each draw",
    },
    "digit_marginal_chi_square": {
        "dependency_family": "digit_frequency_distribution",
        "dependency_cluster": "digit_marginal_uniformity",
        "dependency_tags": ["digit_sequence", "digit_counts", "pooled_digits"],
        "data_view": "digit counts pooled across positions",
    },
    "digit_marginal_g_test": {
        "dependency_family": "digit_frequency_distribution",
        "dependency_cluster": "digit_marginal_uniformity",
        "dependency_tags": ["digit_sequence", "digit_counts", "pooled_digits"],
        "data_view": "digit counts pooled across positions",
    },
    "digit_position_chi_square": {
        "dependency_family": "digit_frequency_distribution",
        "dependency_cluster": "digit_position_uniformity",
        "dependency_tags": ["digit_sequence", "digit_counts", "position_counts"],
        "data_view": "digit counts split by position",
    },
    "digit_value_runs": {
        "dependency_family": "digit_ordered_sequence",
        "dependency_cluster": "digit_value_order",
        "dependency_tags": ["digit_sequence", "ordered_draws", "numeric_value"],
        "data_view": "ordered numeric value of each outcome",
    },
    "digit_value_lag1_autocorrelation": {
        "dependency_family": "digit_ordered_sequence",
        "dependency_cluster": "digit_value_order",
        "dependency_tags": ["digit_sequence", "ordered_draws", "numeric_value"],
        "data_view": "ordered numeric value of each outcome",
    },
    "digit_sum_split_half_change": {
        "dependency_family": "digit_ordered_sequence",
        "dependency_cluster": "digit_sum_change",
        "dependency_tags": ["digit_sequence", "ordered_draws", "digit_sum", "change_point"],
        "data_view": "first-half and second-half digit sums",
    },
    "digit_month_heterogeneity": {
        "dependency_family": "digit_frequency_distribution",
        "dependency_cluster": "digit_calendar_counts",
        "dependency_tags": ["digit_sequence", "digit_counts", "calendar_strata"],
        "data_view": "digit counts stratified by calendar month",
    },
    "digit_sum_distribution": {
        "dependency_family": "digit_sum_structure",
        "dependency_cluster": "digit_sum_distribution",
        "dependency_tags": ["digit_sequence", "digit_sum", "within_outcome"],
        "data_view": "digit-sum distribution for each outcome",
    },
    "digit_repeat_poisson": {
        "dependency_family": "digit_repeat_structure",
        "dependency_cluster": "digit_duplicate_pairs",
        "dependency_tags": ["digit_sequence", "outcome_identity", "repeat_pairs"],
        "data_view": "duplicate outcome pairs across the confirmed history",
    },
}

EFFECT_THRESHOLD_SENSITIVITY_MULTIPLIERS = [0.5, 1.0, 1.5, 2.0]

EFFECT_THRESHOLD_REGISTRY = [
    {
        "id": "cohen_w_0_05",
        "effect_size_name": "Cohen's w",
        "threshold": 0.05,
        "unit": "w = sqrt(chi_square / pooled category observations)",
        "scope": "Kiểm định phân bố biên cho tập số và chuỗi chữ số.",
        "reference_or_rationale": (
            "Cohen thường xem w=0,10 là hiệu ứng nhỏ. Dự án dùng 0,05 như ngưỡng "
            "sàng lọc bảo thủ hơn vì sai lệch xổ số, nếu có, được kỳ vọng rất nhỏ "
            "và vẫn phải vượt hiệu chỉnh nhiều kiểm định."
        ),
        "sensitivity_method": (
            "Đếm lại số phép kiểm đạt ngưỡng khi nhân ngưỡng đã khóa với 0,5; 1,0; 1,5; 2,0."
        ),
        "applies_to": [
            "number_marginal_chi_square",
            "digit_marginal_chi_square",
        ],
    },
    {
        "id": "likelihood_w_0_05",
        "effect_size_name": "likelihood w",
        "threshold": 0.05,
        "unit": "w = sqrt(g_statistic / pooled category observations)",
        "scope": "G-test cho cùng câu hỏi phân bố biên với chi-square.",
        "reference_or_rationale": (
            "Dùng cùng mốc 0,05 với Cohen's w để hai phép kiểm cùng họ không tạo "
            "hai tiêu chuẩn thực dụng khác nhau cho cùng một sai lệch phân bố."
        ),
        "sensitivity_method": (
            "Đếm lại số phép kiểm đạt ngưỡng khi nhân ngưỡng đã khóa với 0,5; 1,0; 1,5; 2,0."
        ),
        "applies_to": [
            "number_marginal_g_test",
            "digit_marginal_g_test",
        ],
    },
    {
        "id": "absolute_z_per_sqrt_n_0_10",
        "effect_size_name": "absolute z per sqrt(n)",
        "threshold": 0.10,
        "unit": "|z| / sqrt(n)",
        "scope": "Runs test trên chuỗi tổng bộ số hoặc giá trị chuỗi.",
        "reference_or_rationale": (
            "Chuẩn hóa z theo căn cỡ mẫu để mẫu rất lớn không tự biến sai lệch nhỏ "
            "thành tín hiệu thực dụng. Mốc 0,10 là mức tối thiểu trước khi coi nhịp "
            "cao-thấp là đủ lớn để theo dõi."
        ),
        "sensitivity_method": (
            "Đếm lại số phép kiểm đạt ngưỡng khi nhân ngưỡng đã khóa với 0,5; 1,0; 1,5; 2,0."
        ),
        "applies_to": [
            "number_sum_runs",
            "digit_value_runs",
        ],
    },
    {
        "id": "absolute_correlation_0_05",
        "effect_size_name": "absolute correlation",
        "threshold": 0.05,
        "unit": "|r|",
        "scope": "Tự tương quan lag-1 của tổng bộ số hoặc giá trị chuỗi.",
        "reference_or_rationale": (
            "Tương quan 0,05 là hiệu ứng rất nhỏ theo thang r, nhưng vẫn đủ đáng chú ý "
            "trong bối cảnh xổ số nếu ổn định ngoài mẫu và vượt hiệu chỉnh."
        ),
        "sensitivity_method": (
            "Đếm lại số phép kiểm đạt ngưỡng khi nhân ngưỡng đã khóa với 0,5; 1,0; 1,5; 2,0."
        ),
        "applies_to": [
            "number_sum_lag1_autocorrelation",
            "digit_value_lag1_autocorrelation",
        ],
    },
    {
        "id": "standardized_mean_difference_0_15",
        "effect_size_name": "standardized mean difference",
        "threshold": 0.15,
        "unit": "|mean_2 - mean_1| / pooled_sd",
        "scope": "So sánh split-half giữa nửa đầu và nửa sau lịch sử.",
        "reference_or_rationale": (
            "Mốc này thấp hơn quy ước small-effect 0,20 của standardized mean "
            "difference để phục vụ cảnh báo sớm, nhưng vẫn buộc sai lệch phải lớn "
            "hơn nhiễu rất nhỏ của mẫu lớn."
        ),
        "sensitivity_method": (
            "Đếm lại số phép kiểm đạt ngưỡng khi nhân ngưỡng đã khóa với 0,5; 1,0; 1,5; 2,0."
        ),
        "applies_to": [
            "number_sum_split_half_change",
            "digit_sum_split_half_change",
        ],
    },
    {
        "id": "cramers_style_w_0_05",
        "effect_size_name": "Cramer's style w",
        "threshold": 0.05,
        "unit": "w = sqrt(chi_square / stratified observations)",
        "scope": "Kiểm định dị biệt theo tháng cho số hoặc chữ số.",
        "reference_or_rationale": (
            "Dùng cùng mốc sàng lọc 0,05 với các kiểm định chi-square phân bố, vì "
            "đây vẫn là độ lệch chuẩn hóa từ bảng phân loại nhưng có thêm tầng tháng."
        ),
        "sensitivity_method": (
            "Đếm lại số phép kiểm đạt ngưỡng khi nhân ngưỡng đã khóa với 0,5; 1,0; 1,5; 2,0."
        ),
        "applies_to": [
            "number_month_heterogeneity",
            "digit_month_heterogeneity",
        ],
    },
    {
        "id": "gap_ratio_4_0",
        "effect_size_name": "gap divided by expected gap",
        "threshold": 4.0,
        "unit": "current_gap_draws / expected_gap_draws",
        "scope": "Số đang vắng lâu nhất trong sản phẩm chọn tập số.",
        "reference_or_rationale": (
            "Khoảng vắng phải đạt ít nhất bốn lần khoảng vắng kỳ vọng mới được xem "
            "là lớn về thực dụng, vì trong không gian nhiều số luôn có một số đang vắng lâu."
        ),
        "sensitivity_method": (
            "Đếm lại số phép kiểm đạt ngưỡng khi nhân ngưỡng đã khóa với 0,5; 1,0; 1,5; 2,0."
        ),
        "applies_to": ["number_current_gap_geometric"],
    },
    {
        "id": "pair_co_occurrence_w_0_05",
        "effect_size_name": "pair co-occurrence w",
        "threshold": 0.05,
        "unit": "w = sqrt(chi_square / pair observations)",
        "scope": "Kiểm định đồng xuất hiện cặp số khi workflow đủ bộ nhớ để chạy.",
        "reference_or_rationale": (
            "Giữ cùng mốc 0,05 với kiểm định phân bố, nhưng diễn giải thận trọng hơn "
            "vì các cặp trong cùng một kỳ không độc lập hoàn toàn."
        ),
        "sensitivity_method": (
            "Đếm lại số phép kiểm đạt ngưỡng khi nhân ngưỡng đã khóa với 0,5; 1,0; 1,5; 2,0."
        ),
        "applies_to": ["number_pair_co_occurrence"],
    },
    {
        "id": "odd_count_w_0_10",
        "effect_size_name": "odd-count w",
        "threshold": 0.10,
        "unit": "w = sqrt(chi_square / draws)",
        "scope": "Phân bố số lượng số lẻ trong một bộ chọn không lặp.",
        "reference_or_rationale": (
            "Số chẵn-lẻ là đặc trưng tổng hợp thô nên yêu cầu mốc 0,10, tránh báo "
            "tín hiệu thực dụng từ dao động nhỏ của vài ô phân bố."
        ),
        "sensitivity_method": (
            "Đếm lại số phép kiểm đạt ngưỡng khi nhân ngưỡng đã khóa với 0,5; 1,0; 1,5; 2,0."
        ),
        "applies_to": ["number_odd_count_hypergeometric"],
    },
    {
        "id": "position_digit_w_0_05",
        "effect_size_name": "position digit w",
        "threshold": 0.05,
        "unit": "w = sqrt(chi_square / position-digit observations)",
        "scope": "Kiểm định chữ số theo vị trí cho Max 3D, Max 3D Pro, Max 4D và Bingo18.",
        "reference_or_rationale": (
            "Đây là tín hiệu đang cần tái kiểm tra ngoài mẫu nên giữ ngưỡng nhạy 0,05, "
            "nhưng không tách từng ô thành kiểm định mới trên cùng dữ liệu."
        ),
        "sensitivity_method": (
            "Đếm lại số phép kiểm đạt ngưỡng khi nhân ngưỡng đã khóa với 0,5; 1,0; 1,5; 2,0."
        ),
        "applies_to": ["digit_position_chi_square"],
    },
    {
        "id": "digit_sum_w_0_10",
        "effect_size_name": "digit-sum w",
        "threshold": 0.10,
        "unit": "w = sqrt(chi_square / outcomes)",
        "scope": "Phân bố tổng chữ số của sản phẩm chuỗi chữ số.",
        "reference_or_rationale": (
            "Tổng chữ số gộp nhiều cấu hình khác nhau, vì vậy dùng mốc 0,10 để chỉ "
            "đánh dấu sai lệch tổng hợp đủ lớn."
        ),
        "sensitivity_method": (
            "Đếm lại số phép kiểm đạt ngưỡng khi nhân ngưỡng đã khóa với 0,5; 1,0; 1,5; 2,0."
        ),
        "applies_to": ["digit_sum_distribution"],
    },
    {
        "id": "repeat_pairs_ratio_1_25",
        "effect_size_name": "repeat pairs ratio",
        "threshold": 1.25,
        "unit": "observed duplicate pairs / expected duplicate pairs",
        "scope": "Tỷ lệ chuỗi kết quả lặp trong không gian hữu hạn.",
        "reference_or_rationale": (
            "Chuỗi lặp là bình thường trong không gian hữu hạn; chỉ khi số cặp lặp "
            "cao hơn kỳ vọng ít nhất 25% mới xem là đủ lớn để theo dõi."
        ),
        "sensitivity_method": (
            "Đếm lại số phép kiểm đạt ngưỡng khi nhân ngưỡng đã khóa với 0,5; 1,0; 1,5; 2,0."
        ),
        "applies_to": ["digit_repeat_poisson"],
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
    _apply_dependency_family_correction(tests)
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
        audit["dependency_matrix"] = _dependency_matrix(audit["tests"])

    return {
        "schema_version": 1,
        "suite_version": AUDIT_SUITE_VERSION,
        "title": "Bộ kiểm định công bằng thống kê",
        "scope": (
            "Kiểm tra dấu hiệu lệch khỏi mô hình ngẫu nhiên trên dữ liệu công khai. "
            "Đây không phải kết luận pháp lý hay kiểm toán vận hành."
        ),
        "families": FAMILY_DESCRIPTIONS,
        "dependency_families": _dependency_family_metadata(),
        "dependency_matrix": _global_dependency_matrix(product_reports),
        "multiple_testing": _multiple_testing_metadata(),
        "effect_thresholds": _effect_threshold_metadata(),
        "threshold_sensitivity": _effect_threshold_sensitivity(product_reports),
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
                "dependency_family": test.get("dependency_family"),
                "dependency_family_label": test.get("dependency_family_label"),
                "dependency_cluster": test.get("dependency_cluster"),
                "algorithm": test["algorithm"],
                "status": test["status"],
                "statistic": test.get("statistic"),
                "p_value": test.get("p_value"),
                "q_value_bh": test.get("q_value_bh"),
                "q_value_dependency_family_bh": test.get("q_value_dependency_family_bh"),
                "q_value_global_bh": test.get("q_value_global_bh"),
                "effect_size": test.get("effect_size"),
                "practical_effect_threshold": test.get("practical_effect_threshold"),
                "effect_threshold_id": test.get("effect_threshold_id"),
                "statistically_notable": test.get("statistically_notable"),
                "practically_large": test.get("practically_large"),
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
        "dependency_families": _dependency_family_metadata(),
        "dependency_matrix": _dependency_matrix(tests),
        "multiple_testing": _multiple_testing_metadata(),
        "effect_thresholds": _effect_threshold_metadata(),
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
    symbols = _sequence_symbols(product)
    symbol_count = len(symbols)
    observations = dataset.observations
    outcomes = [
        outcome
        for observation in observations
        for outcome in observation.outcomes
        if len(outcome) == length and outcome.isdigit()
    ]
    digit_counts = Counter(int(char) for outcome in outcomes for char in outcome)
    expected_per_symbol = len(outcomes) * length / symbol_count if outcomes else 0
    numeric_values = [int(outcome) for outcome in outcomes]
    digit_sums = [sum(int(char) for char in outcome) for outcome in outcomes]

    tests = [
        _chi_square_test(
            test_id="digit_marginal_chi_square",
            family="distribution_fit",
            algorithm="Chi-Square Goodness-of-Fit Test",
            label=f"Tần suất giá trị {product.sequence_min} đến {product.sequence_max}",
            plain_language="Mỗi giá trị hợp lệ nên xuất hiện gần đều trên toàn bộ vị trí quan sát.",
            observed=[digit_counts[digit] for digit in symbols],
            expected=[expected_per_symbol for _ in symbols],
            sample_size=len(outcomes),
            effect_denominator=len(outcomes) * length,
            effect_label="Cohen's w",
            practical_threshold=0.05,
        ),
        _g_test(
            test_id="digit_marginal_g_test",
            family="distribution_fit",
            label="G-test cho tần suất giá trị",
            plain_language="Đo độ lệch giá trị bằng tỷ lệ hợp lý likelihood.",
            observed=[digit_counts[digit] for digit in symbols],
            expected=[expected_per_symbol for _ in symbols],
            sample_size=len(outcomes),
            effect_denominator=len(outcomes) * length,
            practical_threshold=0.05,
        ),
        _digit_position_test(dataset, outcomes, symbols),
        _digit_sum_distribution_test(outcomes, length, symbols),
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
        _repeat_rate_test(outcomes, length, symbols),
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
    symbols = _sequence_symbols(product)
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
        expected = month_outcomes[month] * length / len(symbols)
        total_digits += month_outcomes[month] * length
        for digit in symbols:
            if expected > 0:
                statistic += (month_counts[month][digit] - expected) ** 2 / expected
    degrees = max(1, (len(months) - 1) * (len(symbols) - 1))
    return _test_result(
        test_id="digit_month_heterogeneity",
        family="seasonality",
        algorithm="Month-by-Digit Chi-Square Test",
        label="Tần suất giá trị theo tháng",
        plain_language="So từng tháng với tần suất nền của các giá trị hợp lệ.",
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


def _digit_position_test(
    dataset: ProductDataset,
    outcomes: list[str],
    symbols: list[int],
) -> dict[str, Any] | None:
    product = dataset.product
    length = product.sequence_length or 0
    if not outcomes or not length:
        return None
    position_counts = [Counter() for _ in range(length)]
    for outcome in outcomes:
        for position, char in enumerate(outcome):
            position_counts[position][int(char)] += 1
    expected = len(outcomes) / len(symbols)
    residuals = [
        {
            "position": position + 1,
            "digit": digit,
            "observed": counter[digit],
            "expected": _round(expected),
            "standardized_residual": _round(
                (counter[digit] - expected) / math.sqrt(expected)
                if expected > 0
                else 0.0
            ),
            "chi_square_contribution": _round(
                ((counter[digit] - expected) ** 2) / expected
                if expected > 0
                else 0.0
            ),
        }
        for position, counter in enumerate(position_counts)
        for digit in symbols
    ]
    statistic = sum(
        ((counter[digit] - expected) ** 2) / expected
        for counter in position_counts
        for digit in symbols
        if expected > 0
    )
    return _test_result(
        test_id="digit_position_chi_square",
        family="distribution_fit",
        algorithm="Position-wise Chi-Square Test",
        label="Tần suất giá trị theo vị trí",
        plain_language="Mỗi vị trí của chuỗi nên có các giá trị hợp lệ gần đều nhau.",
        statistic_name="chi_square",
        statistic=statistic,
        degrees_of_freedom=length * (len(symbols) - 1),
        p_value=_chi_square_survival_approx(statistic, length * (len(symbols) - 1)),
        effect_size_name="position digit w",
        effect_size=math.sqrt(statistic / (len(outcomes) * length)),
        practical_threshold=0.05,
        sample_size=len(outcomes),
        parameters={
            "expected_per_position_digit": _round(expected),
            "position_residuals": residuals,
            "tier_breakdown": _digit_tier_breakdown(dataset, symbols),
            "period_breakdown": _digit_period_breakdown(dataset, symbols),
            "residual_note": (
                "Residual được công bố để giải thích đóng góp vào kiểm định tổng. "
                "Không dùng từng ô như một kiểm định độc lập mới."
            ),
        },
    )


def _digit_tier_breakdown(
    dataset: ProductDataset,
    symbols: list[int],
) -> dict[str, Any]:
    product = dataset.product
    length = product.sequence_length or 0
    tiered_count = sum(len(observation.tiered_outcomes) for observation in dataset.observations)
    if not tiered_count:
        return {
            "status": "not_applicable",
            "basis": "result_json.tiers",
            "reason": "Kết quả sản phẩm này không có cấu trúc hạng giải trong result_json.",
            "result_types": [],
            "tiers": [],
            "no_new_p_values": True,
        }

    result_type_counts = Counter(
        entry.result_type
        for observation in dataset.observations
        for entry in observation.tiered_outcomes
    )
    usable_by_tier: dict[str, list[str]] = {}
    draws_by_tier: dict[str, set[str]] = {}
    for observation in dataset.observations:
        seen_tiers: set[str] = set()
        for entry in observation.tiered_outcomes:
            if entry.result_type != "full_sequence":
                continue
            if len(entry.outcome) != length or not entry.outcome.isdigit():
                continue
            usable_by_tier.setdefault(entry.tier, []).append(entry.outcome)
            seen_tiers.add(entry.tier)
        for tier in seen_tiers:
            draws_by_tier.setdefault(tier, set()).add(observation.draw_id)

    result_types = [
        {
            "result_type": result_type,
            "label": RESULT_TYPE_DESCRIPTIONS.get(result_type, {}).get(
                "label",
                result_type,
            ),
            "outcomes": count,
            "usable_for_position_audit": bool(
                RESULT_TYPE_DESCRIPTIONS.get(result_type, {}).get(
                    "usable_for_position_audit",
                    False,
                )
            ),
            "plain_language": RESULT_TYPE_DESCRIPTIONS.get(result_type, {}).get(
                "plain_language",
                "",
            ),
        }
        for result_type, count in sorted(result_type_counts.items())
    ]

    tiers = [
        _digit_tier_row(
            tier=tier,
            outcomes=outcomes,
            draw_count=len(draws_by_tier.get(tier, set())),
            symbols=symbols,
            length=length,
        )
        for tier, outcomes in sorted(
            usable_by_tier.items(),
            key=lambda item: (TIER_ORDER.get(item[0], 99), item[0]),
        )
    ]
    status = "available" if tiers else "no_full_sequence_tiers"
    return {
        "status": status,
        "basis": "result_json.tiers",
        "usable_result_type": "full_sequence",
        "result_types": result_types,
        "tiers": tiers,
        "no_new_p_values": True,
        "interpretation": (
            "Các hàng theo hạng giải chỉ phân rã đóng góp của kiểm định vị trí tổng. "
            "Không tính p-value riêng cho từng hạng trên cùng dữ liệu."
        ),
    }


def _digit_tier_row(
    *,
    tier: str,
    outcomes: list[str],
    draw_count: int,
    symbols: list[int],
    length: int,
) -> dict[str, Any]:
    position_counts = [Counter() for _ in range(length)]
    for outcome in outcomes:
        for position, char in enumerate(outcome):
            position_counts[position][int(char)] += 1
    expected = len(outcomes) / len(symbols) if symbols else 0.0
    residuals = [
        {
            "position": position + 1,
            "digit": digit,
            "observed": counter[digit],
            "expected": _round(expected),
            "standardized_residual": _round(
                (counter[digit] - expected) / math.sqrt(expected)
                if expected > 0
                else 0.0
            ),
            "chi_square_contribution": _round(
                ((counter[digit] - expected) ** 2) / expected
                if expected > 0
                else 0.0
            ),
        }
        for position, counter in enumerate(position_counts)
        for digit in symbols
    ]
    statistic = sum(item["chi_square_contribution"] for item in residuals)
    max_abs_residual = max(
        (abs(float(item["standardized_residual"])) for item in residuals),
        default=0.0,
    )
    return {
        "tier": tier,
        "tier_label": TIER_LABELS.get(tier, tier),
        "draws": draw_count,
        "outcomes": len(outcomes),
        "expected_per_position_digit": _round(expected),
        "chi_square_contribution": _round(statistic),
        "effect_size": _round(
            math.sqrt(statistic / (len(outcomes) * length))
            if outcomes and length
            else 0.0
        ),
        "max_abs_standardized_residual": _round(max_abs_residual),
        "position_residuals": residuals,
    }


def _digit_period_breakdown(
    dataset: ProductDataset,
    symbols: list[int],
) -> dict[str, Any]:
    product = dataset.product
    length = product.sequence_length or 0
    usable_observations = [
        observation
        for observation in dataset.observations
        if any(len(outcome) == length and outcome.isdigit() for outcome in observation.outcomes)
    ]
    if len(usable_observations) < DIGIT_PERIOD_SEGMENTS * DIGIT_PERIOD_MIN_DRAWS:
        return {
            "status": "insufficient_data",
            "basis": "confirmed_draw_order",
            "segment_count": DIGIT_PERIOD_SEGMENTS,
            "min_segment_draws": DIGIT_PERIOD_MIN_DRAWS,
            "observed_draws": len(usable_observations),
            "segments": [],
            "no_new_p_values": True,
            "interpretation": (
                "Mẫu chưa đủ để chia thành các giai đoạn thời gian không chồng lấn có kích thước tối thiểu."
            ),
        }

    segments = [
        _digit_period_row(
            segment_index=index + 1,
            observations=usable_observations[
                len(usable_observations) * index // DIGIT_PERIOD_SEGMENTS:
                len(usable_observations) * (index + 1) // DIGIT_PERIOD_SEGMENTS
            ],
            symbols=symbols,
            length=length,
        )
        for index in range(DIGIT_PERIOD_SEGMENTS)
    ]
    return {
        "status": "available",
        "basis": "confirmed_draw_order",
        "segment_count": DIGIT_PERIOD_SEGMENTS,
        "min_segment_draws": DIGIT_PERIOD_MIN_DRAWS,
        "observed_draws": len(usable_observations),
        "segments": segments,
        "no_new_p_values": True,
        "interpretation": (
            "Các giai đoạn là những khối lịch sử liên tiếp, không chồng lấn. "
            "Chỉ công bố đóng góp và residual để đọc độ ổn định, không tính p-value riêng cho từng khối."
        ),
    }


def _digit_period_row(
    *,
    segment_index: int,
    observations: list[Any],
    symbols: list[int],
    length: int,
) -> dict[str, Any]:
    outcomes = [
        outcome
        for observation in observations
        for outcome in observation.outcomes
        if len(outcome) == length and outcome.isdigit()
    ]
    position_counts = [Counter() for _ in range(length)]
    for outcome in outcomes:
        for position, char in enumerate(outcome):
            position_counts[position][int(char)] += 1
    expected = len(outcomes) / len(symbols) if symbols else 0.0
    residuals = [
        {
            "position": position + 1,
            "digit": digit,
            "observed": counter[digit],
            "expected": _round(expected),
            "standardized_residual": _round(
                (counter[digit] - expected) / math.sqrt(expected)
                if expected > 0
                else 0.0
            ),
            "chi_square_contribution": _round(
                ((counter[digit] - expected) ** 2) / expected
                if expected > 0
                else 0.0
            ),
        }
        for position, counter in enumerate(position_counts)
        for digit in symbols
    ]
    statistic = sum(item["chi_square_contribution"] for item in residuals)
    max_abs_residual = max(
        (abs(float(item["standardized_residual"])) for item in residuals),
        default=0.0,
    )
    top_residuals = sorted(
        residuals,
        key=lambda item: abs(float(item["standardized_residual"])),
        reverse=True,
    )[:DIGIT_PERIOD_TOP_RESIDUALS]
    first = observations[0]
    last = observations[-1]
    return {
        "segment_index": segment_index,
        "segment_label": f"Giai đoạn {segment_index}",
        "start_draw_id": first.draw_id,
        "end_draw_id": last.draw_id,
        "start_date": first.draw_date.isoformat(),
        "end_date": last.draw_date.isoformat(),
        "draws": len(observations),
        "outcomes": len(outcomes),
        "expected_per_position_digit": _round(expected),
        "chi_square_contribution": _round(statistic),
        "effect_size": _round(
            math.sqrt(statistic / (len(outcomes) * length))
            if outcomes and length
            else 0.0
        ),
        "max_abs_standardized_residual": _round(max_abs_residual),
        "top_residuals": top_residuals,
    }


def _digit_sum_distribution_test(
    outcomes: list[str],
    length: int,
    symbols: list[int],
) -> dict[str, Any] | None:
    if not outcomes or not length:
        return None
    probabilities = _sequence_sum_probabilities(length, symbols)
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


def _repeat_rate_test(
    outcomes: list[str],
    length: int,
    symbols: list[int],
) -> dict[str, Any] | None:
    if len(outcomes) < 2 or length <= 0:
        return None
    space = len(symbols) ** length
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
    dependency = _test_dependency_metadata(test_id)
    return {
        "id": test_id,
        "family": family,
        **dependency,
        "algorithm": algorithm,
        "label": label,
        "plain_language": plain_language,
        "statistic_name": statistic_name,
        "statistic": _round(statistic),
        "degrees_of_freedom": degrees_of_freedom,
        "p_value": _round(max(0.0, min(1.0, p_value)), 8),
        "q_value_bh": None,
        "q_value_dependency_family_bh": None,
        "q_value_global_bh": None,
        "effect_size_name": effect_size_name,
        "effect_size": _round(effect_size),
        "practical_effect_threshold": practical_threshold,
        "effect_threshold_id": _effect_threshold_id(effect_size_name, practical_threshold),
        "sample_size": sample_size,
        "parameters": parameters or {},
        "status": "pending",
        "statistically_notable": False,
        "practically_large": False,
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
    dependency = _test_dependency_metadata(test_id)
    return {
        "id": test_id,
        "family": family,
        **dependency,
        "algorithm": algorithm,
        "label": label,
        "plain_language": plain_language,
        "statistic_name": None,
        "statistic": None,
        "degrees_of_freedom": None,
        "p_value": None,
        "q_value_bh": None,
        "q_value_dependency_family_bh": None,
        "q_value_global_bh": None,
        "effect_size_name": None,
        "effect_size": None,
        "practical_effect_threshold": None,
        "effect_threshold_id": None,
        "sample_size": sample_size,
        "parameters": parameters or {},
        "status": "skipped",
        "statistically_notable": False,
        "practically_large": False,
        "interpretation": "Tạm hoãn để giữ workflow tự động đủ nhẹ và có thể tái lập hằng ngày.",
    }


def _test_dependency_metadata(test_id: str) -> dict[str, Any]:
    profile = TEST_DEPENDENCY_PROFILES.get(test_id)
    if profile is None:
        return {
            "dependency_family": "unclassified",
            "dependency_family_label": "Chưa phân nhóm",
            "dependency_cluster": "unclassified",
            "dependency_tags": [],
            "dependency_data_view": "not classified",
        }
    dependency_family = str(profile["dependency_family"])
    return {
        "dependency_family": dependency_family,
        "dependency_family_label": _dependency_family_label(dependency_family),
        "dependency_cluster": str(profile["dependency_cluster"]),
        "dependency_tags": list(profile["dependency_tags"]),
        "dependency_data_view": str(profile["data_view"]),
    }


def _dependency_family_label(dependency_family: str) -> str:
    for entry in DEPENDENCY_FAMILY_DESCRIPTIONS:
        if entry["id"] == dependency_family:
            return str(entry["label"])
    return dependency_family


def _dependency_family_metadata() -> list[dict[str, Any]]:
    test_ids_by_family: dict[str, list[str]] = {
        str(entry["id"]): [] for entry in DEPENDENCY_FAMILY_DESCRIPTIONS
    }
    for test_id, profile in TEST_DEPENDENCY_PROFILES.items():
        test_ids_by_family.setdefault(str(profile["dependency_family"]), []).append(test_id)
    return [
        {
            **entry,
            "test_ids": sorted(test_ids_by_family.get(str(entry["id"]), [])),
        }
        for entry in DEPENDENCY_FAMILY_DESCRIPTIONS
    ]


def _multiple_testing_metadata() -> dict[str, Any]:
    return {
        "method": "benjamini_hochberg",
        "primary_decision_q": "q_value_global_bh",
        "fallback_decision_q": "q_value_bh before global finalization",
        "diagnostic_family_q": "q_value_dependency_family_bh",
        "alpha": 0.05,
        "plain_language": (
            "Trạng thái thống kê ưu tiên q toàn hệ thống. q theo họ phụ thuộc chỉ "
            "giúp đọc các phép kiểm dùng chung lát dữ liệu hoặc cùng câu hỏi."
        ),
    }


def _effect_threshold_metadata() -> list[dict[str, Any]]:
    return [
        {
            **entry,
            "applies_to": list(entry["applies_to"]),
        }
        for entry in EFFECT_THRESHOLD_REGISTRY
    ]


def _effect_threshold_id(effect_size_name: str, threshold: float) -> str:
    for entry in EFFECT_THRESHOLD_REGISTRY:
        if entry["effect_size_name"] == effect_size_name and math.isclose(
            float(entry["threshold"]),
            float(threshold),
        ):
            return str(entry["id"])
    return "unregistered"


def _effect_threshold_sensitivity(
    product_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    tests = [
        {
            "product": report["product"]["slug"],
            **test,
        }
        for report in product_reports
        for test in report.get("audit", {}).get("tests", [])
        if isinstance(test.get("effect_size"), (int, float))
        and isinstance(test.get("practical_effect_threshold"), (int, float))
    ]
    return {
        "method": "threshold_multiplier_sweep",
        "multipliers": EFFECT_THRESHOLD_SENSITIVITY_MULTIPLIERS,
        "global": [
            _effect_sensitivity_row(tests, multiplier)
            for multiplier in EFFECT_THRESHOLD_SENSITIVITY_MULTIPLIERS
        ],
        "by_threshold": [
            {
                "id": entry["id"],
                "effect_size_name": entry["effect_size_name"],
                "base_threshold": entry["threshold"],
                "unit": entry["unit"],
                "test_count": sum(
                    test.get("effect_threshold_id") == entry["id"] for test in tests
                ),
                "scenarios": [
                    _effect_sensitivity_row(
                        [
                            test
                            for test in tests
                            if test.get("effect_threshold_id") == entry["id"]
                        ],
                        multiplier,
                    )
                    for multiplier in EFFECT_THRESHOLD_SENSITIVITY_MULTIPLIERS
                ],
            }
            for entry in EFFECT_THRESHOLD_REGISTRY
        ],
    }


def _effect_sensitivity_row(
    tests: list[dict[str, Any]],
    multiplier: float,
) -> dict[str, Any]:
    practically_large = [
        test
        for test in tests
        if abs(float(test["effect_size"]))
        >= abs(float(test["practical_effect_threshold"])) * multiplier
    ]
    both = [
        test
        for test in practically_large
        if float(_test_q_value(test)) < 0.05
    ]
    return {
        "threshold_multiplier": multiplier,
        "test_count": len(tests),
        "practically_large_count": len(practically_large),
        "both_count": len(both),
    }


def _dependency_matrix(tests: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = [
        pair
        for left, right in combinations(sorted(tests, key=lambda test: test["id"]), 2)
        if (pair := _dependency_pair(left, right)) is not None
    ]
    counts = Counter(pair["dependency_strength"] for pair in pairs)
    return {
        "scope": "single_product",
        "test_count": len(tests),
        "pair_count": len(pairs),
        "counts": {
            "high": counts["high"],
            "medium": counts["medium"],
            "low": counts["low"],
        },
        "pairs": pairs,
        "note": (
            "Ma trận là bản đồ phụ thuộc phương pháp, không phải ma trận tương quan "
            "ước lượng từ dữ liệu. Cặp high thường dùng cùng dữ liệu và cùng câu hỏi; "
            "medium dùng chung họ phụ thuộc; low chỉ chia sẻ miền sản phẩm."
        ),
    }


def _global_dependency_matrix(product_reports: list[dict[str, Any]]) -> dict[str, Any]:
    pair_counts: Counter[tuple[str, str, str, str]] = Counter()
    examples: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for report in product_reports:
        audit = report.get("audit", {})
        matrix = audit.get("dependency_matrix")
        if not isinstance(matrix, dict):
            matrix = _dependency_matrix(audit.get("tests", []))
        for pair in matrix.get("pairs", []):
            key = (
                str(pair["left_id"]),
                str(pair["right_id"]),
                str(pair["dependency_strength"]),
                str(pair["relationship"]),
            )
            pair_counts[key] += 1
            examples.setdefault(key, pair)
    pairs = [
        {
            **examples[key],
            "product_count": product_count,
        }
        for key, product_count in sorted(pair_counts.items())
    ]
    counts = Counter(
        pair["dependency_strength"]
        for pair in pairs
        for _ in range(int(pair["product_count"]))
    )
    return {
        "scope": "all_products_by_test_definition",
        "pair_definition_count": len(pairs),
        "pair_occurrence_count": sum(pair_counts.values()),
        "counts": {
            "high": counts["high"],
            "medium": counts["medium"],
            "low": counts["low"],
        },
        "pairs": pairs,
        "note": (
            "Bản toàn hệ thống gom các quan hệ xuất hiện trong từng sản phẩm và đếm "
            "số sản phẩm có cùng cặp phép kiểm."
        ),
    }


def _dependency_pair(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any] | None:
    left_tags = set(left.get("dependency_tags") or [])
    right_tags = set(right.get("dependency_tags") or [])
    shared_tags = sorted(left_tags & right_tags)
    if not shared_tags:
        return None

    same_cluster = (
        left.get("dependency_cluster")
        and left.get("dependency_cluster") == right.get("dependency_cluster")
    )
    same_family = (
        left.get("dependency_family")
        and left.get("dependency_family") == right.get("dependency_family")
    )
    if same_cluster:
        strength = "high"
        relationship = "same_question"
        rationale = (
            "Hai phép kiểm dùng cùng lát dữ liệu và trả lời gần như cùng một câu hỏi, "
            "nên không nên đọc như hai bằng chứng độc lập."
        )
    elif same_family:
        strength = "medium"
        relationship = "same_dependency_family"
        rationale = (
            "Hai phép kiểm dùng chung họ dữ liệu hoặc đặc trưng dẫn xuất, vì vậy kết "
            "quả có thể cùng phản ánh một sai lệch nền."
        )
    elif {"number_set", "digit_sequence"} & set(shared_tags):
        strength = "low"
        relationship = "same_product_domain"
        rationale = (
            "Hai phép kiểm cùng thuộc một miền sản phẩm nhưng nhìn các đặc trưng khác nhau."
        )
    else:
        return None

    return {
        "left_id": left["id"],
        "left_label": left["label"],
        "right_id": right["id"],
        "right_label": right["label"],
        "dependency_strength": strength,
        "relationship": relationship,
        "shared_tags": shared_tags,
        "rationale": rationale,
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


def _apply_dependency_family_correction(tests: list[dict[str, Any]]) -> None:
    indexes_by_family: dict[str, list[tuple[int, float]]] = {}
    for index, test in enumerate(tests):
        if not isinstance(test.get("p_value"), (int, float)):
            continue
        family = str(test.get("dependency_family") or "unclassified")
        indexes_by_family.setdefault(family, []).append((index, float(test["p_value"])))

    for indexed in indexes_by_family.values():
        q_values = _benjamini_hochberg([p_value for _, p_value in indexed])
        for (index, _), q_value in zip(indexed, q_values, strict=True):
            tests[index]["q_value_dependency_family_bh"] = _round(q_value, 8)


def _refresh_test_statuses(tests: list[dict[str, Any]]) -> None:
    for test in tests:
        if test.get("status") == "skipped":
            continue
        q_value = test.get("q_value_global_bh")
        if q_value is None:
            q_value = test.get("q_value_bh")
        if q_value is None:
            q_value = 1.0
        effect = abs(float(test.get("effect_size") or 0.0))
        threshold = abs(float(test.get("practical_effect_threshold") or 0.0))
        statistically_notable = float(q_value) < 0.05
        practically_large = bool(threshold and effect >= threshold)
        test["statistically_notable"] = statistically_notable
        test["practically_large"] = practically_large
        if statistically_notable and practically_large:
            status = "both"
            interpretation = (
                "Tín hiệu vừa vượt ngưỡng thống kê sau hiệu chỉnh, vừa đạt ngưỡng độ lớn thực dụng. "
                "Cần đối chiếu nguồn dữ liệu, giả định kiểm định và dữ liệu vận hành nếu có."
            )
        elif statistically_notable:
            status = "statistically_notable"
            interpretation = (
                "Kết quả vượt ngưỡng thống kê sau hiệu chỉnh nhưng chưa đạt ngưỡng độ lớn thực dụng. "
                "Mẫu lớn có thể làm sai lệch rất nhỏ trở nên nổi bật."
            )
        elif practically_large:
            status = "practically_large"
            interpretation = (
                "Độ lớn đạt ngưỡng thực dụng đã khóa trước nhưng q chưa vượt ngưỡng thống kê. "
                "Cần thêm dữ liệu hoặc kiểm tra độ nhạy trước khi diễn giải."
            )
        else:
            status = "pass"
            interpretation = (
                "Chưa vượt ngưỡng thống kê sau hiệu chỉnh và chưa đạt ngưỡng độ lớn thực dụng."
            )
        test["status"] = status
        test["interpretation"] = interpretation


def _audit_conclusion(tests: list[dict[str, Any]]) -> str:
    counts = Counter(test["status"] for test in tests)
    if counts["both"]:
        return (
            f"Có {counts['both']} kiểm định đồng thời nổi bật về thống kê và độ lớn thực dụng. "
            "Đây vẫn chưa phải kết luận về nguyên nhân hay quy trình vận hành."
        )
    one_condition = counts["statistically_notable"] + counts["practically_large"]
    if one_condition:
        return (
            f"Có {one_condition} kiểm định chỉ đạt một trong hai điều kiện thống kê hoặc "
            "độ lớn thực dụng. Cần đọc riêng lý do thay vì gộp thành một nhãn theo dõi."
        )
    return "Chưa thấy kiểm định nào vượt ngưỡng theo dõi sau hiệu chỉnh nhiều kiểm định."


def _strongest_signal(tests: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not tests:
        return None
    ranked = sorted(
        tests,
        key=lambda test: (
            {
                "both": 0,
                "statistically_notable": 1,
                "practically_large": 2,
                "pass": 3,
            }.get(test["status"], 4),
            _test_q_value(test),
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
        "q_value_dependency_family_bh": top.get("q_value_dependency_family_bh"),
        "q_value_global_bh": top.get("q_value_global_bh"),
        "dependency_family": top.get("dependency_family"),
        "dependency_family_label": top.get("dependency_family_label"),
        "effect_size": top.get("effect_size"),
        "practical_effect_threshold": top.get("practical_effect_threshold"),
        "statistically_notable": top.get("statistically_notable"),
        "practically_large": top.get("practically_large"),
        "interpretation": top["interpretation"],
    }


def _global_summary(product_reports: list[dict[str, Any]]) -> dict[str, Any]:
    all_tests = [
        test
        for report in product_reports
        for test in report.get("audit", {}).get("tests", [])
    ]
    counts = Counter(test["status"] for test in all_tests)
    products_with_both = [
        report["product"]["slug"]
        for report in product_reports
        if report.get("audit", {}).get("status_counts", {}).get("both", 0)
    ]
    products_with_single_condition = [
        report["product"]["slug"]
        for report in product_reports
        if (
            report.get("audit", {}).get("status_counts", {}).get(
                "statistically_notable", 0
            )
            or report.get("audit", {}).get("status_counts", {}).get(
                "practically_large", 0
            )
        )
    ]
    return {
        "product_count": len(product_reports),
        "test_count": len(all_tests),
        "status_counts": dict(counts),
        "products_with_both": products_with_both,
        "products_with_single_condition": products_with_single_condition,
        "strongest_signal": _strongest_signal(all_tests),
        "conclusion": _global_conclusion(counts),
    }


def _global_conclusion(counts: Counter[str]) -> str:
    if counts["both"]:
        return (
            f"Có {counts['both']} kiểm định đồng thời nổi bật về thống kê và độ lớn thực dụng. "
            "Cần kiểm tra nguồn, giả định và khả năng tái lập trước khi diễn giải."
        )
    one_condition = counts["statistically_notable"] + counts["practically_large"]
    if one_condition:
        return (
            f"Có {one_condition} kiểm định chỉ đạt một trong hai điều kiện thống kê hoặc độ lớn "
            "thực dụng. Bộ dữ liệu chưa đủ để kết luận về uy tín vận hành."
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


def _sequence_symbols(product) -> list[int]:
    return list(range(product.sequence_min, product.sequence_max + 1))


def _sequence_sum_probabilities(length: int, symbols: list[int]) -> dict[int, float]:
    counts = Counter({0: 1})
    for _ in range(length):
        next_counts = Counter()
        for subtotal, count in counts.items():
            for symbol in symbols:
                next_counts[subtotal + symbol] += count
        counts = next_counts
    total = len(symbols) ** length
    return {value: count / total for value, count in sorted(counts.items())}


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _test_q_value(test: dict[str, Any]) -> float:
    global_value = test.get("q_value_global_bh")
    if isinstance(global_value, (int, float)):
        return float(global_value)
    local_value = test.get("q_value_bh")
    if isinstance(local_value, (int, float)):
        return float(local_value)
    return 1.0
