from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
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
DIGIT_SOURCE_MIN_DRAWS = 30
DIGIT_SOURCE_TOP_RESIDUALS = 5
DIGIT_SOURCE_LEAVE_ONE_OUT_TOP_RESIDUALS = 5
RELIABILITY_FILTER_MIN_DRAWS = 30

RELIABLE_SOURCE_VERIFICATIONS = {
    "official_direct",
    "official_verified_match",
    "multi_source_consensus",
}

SOURCE_LABELS = {
    "official_vietlott": "Vietlott chính thức",
    "community_mirror": "Mirror cộng đồng",
    "xosominhngoc_net_vn": "Xổ số Minh Ngọc",
    "vietlott_vn": "vietlott.vn chưa gắn data_source",
    "unknown": "Không rõ nguồn",
}

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
        "plain_language": (
            "Quét các điểm cắt lịch sử đã đăng ký trước để tìm dấu hiệu quy trình thay đổi."
        ),
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
        "data_view": "pre-registered candidate split points over ordered draw sums",
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
        "data_view": "pre-registered candidate split points over ordered digit sums",
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
POWER_ALPHA = 0.05
POWER_LEVELS = [0.8, 0.9]
POWER_PRIMARY_LEVEL = 0.8
POWER_UNSUPPORTED_EFFECTS = {"gap divided by expected gap"}
POWER_NULL_EFFECTS = {"repeat pairs ratio": 1.0}
PERMUTATION_COUNT = 499
PERMUTATION_MIN_VALUES = 20
PERMUTATION_MAX_VALUES = 5000
BLOCK_BOOTSTRAP_RESAMPLES = 199
BLOCK_BOOTSTRAP_MIN_VALUES = 30
BLOCK_BOOTSTRAP_MAX_VALUES = 2500
BLOCK_BOOTSTRAP_CONFIDENCE_LEVEL = 0.95
CHANGE_POINT_CANDIDATE_FRACTIONS = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
CHANGE_POINT_MIN_VALUES = 30
CHANGE_POINT_MIN_SEGMENT_VALUES = 10
PAIR_COOCCURRENCE_MAX_PAIR_SPACE = 250_000
PAIR_COOCCURRENCE_TOP_PAIRS = 5

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
        "scope": "Quét change-point trên các điểm cắt lịch sử đã đăng ký trước.",
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
        "scope": "Kiểm định đồng xuất hiện cặp số bằng bộ đếm cặp đầy đủ.",
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
        "power_summary": _global_power_summary(product_reports),
        "deferred_methods": DEFERRED_METHODS,
        "summary": _global_summary(product_reports),
        "products": [
            {
                "slug": report["product"]["slug"],
                "name": report["product"]["name"],
                "history_draws": report["audit"]["history_draws"],
                "status_counts": report["audit"]["status_counts"],
                "strongest_signal": report["audit"]["strongest_signal"],
                "power_summary": report["audit"].get("power_summary"),
                "reliability_sensitivity": _reliability_sensitivity_summary(
                    report["audit"].get("reliability_sensitivity", {})
                ),
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
            permutation_check = test.get("parameters", {}).get("permutation_check", {})
            block_bootstrap_check = test.get("parameters", {}).get(
                "block_bootstrap_check",
                {},
            )
            change_point_scan = test.get("parameters", {}).get("change_point_scan", {})
            strongest_change_point = change_point_scan.get("strongest_candidate", {})
            source_leave_one_out = test.get("parameters", {}).get(
                "source_leave_one_out",
                {},
            )
            strongest_source_shift = (
                source_leave_one_out.get("strongest_effect_shift") or {}
            )
            reliability_sensitivity = audit.get("reliability_sensitivity", {})
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
                "power_status": test.get("power_analysis", {}).get("status"),
                "power_effective_sample_size": test.get("power_analysis", {}).get(
                    "effective_sample_size"
                ),
                "power_observed": test.get("power_analysis", {}).get("observed_power"),
                "minimum_detectable_effect_80": _minimum_detectable_effect_for_power(
                    test,
                    POWER_PRIMARY_LEVEL,
                ),
                "permutation_status": permutation_check.get("status"),
                "permutation_p_value": permutation_check.get("empirical_p_value"),
                "permutation_preserve_unit": permutation_check.get("preserve_unit"),
                "block_bootstrap_status": block_bootstrap_check.get("status"),
                "block_bootstrap_interval_lower": block_bootstrap_check.get(
                    "confidence_interval_lower"
                ),
                "block_bootstrap_interval_upper": block_bootstrap_check.get(
                    "confidence_interval_upper"
                ),
                "block_bootstrap_block_length": block_bootstrap_check.get("block_length"),
                "change_point_candidate_count": change_point_scan.get("candidate_count"),
                "change_point_candidate_fraction": strongest_change_point.get(
                    "candidate_fraction"
                ),
                "change_point_raw_p_value": change_point_scan.get("raw_p_value"),
                "change_point_adjusted_p_value": change_point_scan.get("adjusted_p_value"),
                "source_leave_one_out_status": source_leave_one_out.get("status"),
                "source_leave_one_out_source_count": source_leave_one_out.get(
                    "source_count"
                ),
                "source_leave_one_out_eligible_sources": source_leave_one_out.get(
                    "eligible_source_count"
                ),
                "source_leave_one_out_strongest_source": strongest_source_shift.get(
                    "excluded_source_key"
                ),
                "source_leave_one_out_strongest_effect_delta": strongest_source_shift.get(
                    "effect_size_delta"
                ),
                "reliability_sensitivity_status": reliability_sensitivity.get("status"),
                "reliability_low_reliability_draws": reliability_sensitivity.get(
                    "low_reliability_confirmed_draws"
                ),
                "reliability_filtered_draws": reliability_sensitivity.get(
                    "filtered_confirmed_draws"
                ),
                "reliability_compared_test_count": reliability_sensitivity.get(
                    "compared_test_count"
                ),
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


def _reliability_sensitivity(
    dataset: ProductDataset,
    baseline_tests: list[dict[str, Any]],
) -> dict[str, Any]:
    confirmed_draws = len(dataset.observations)
    not_confirmed_rows = int(dataset.status_counts.get("not_confirmed", 0))
    total_rows = sum(dataset.status_counts.values()) or confirmed_draws
    verification_counts = Counter(
        observation.source_verification or "unknown"
        for observation in dataset.observations
    )
    reliable_observations = [
        observation
        for observation in dataset.observations
        if (observation.source_verification or "unknown") in RELIABLE_SOURCE_VERIFICATIONS
    ]
    filtered_draws = len(reliable_observations)
    low_reliability_draws = confirmed_draws - filtered_draws
    baseline = {
        "total_rows": total_rows,
        "confirmed_rows": int(dataset.status_counts.get("confirmed", confirmed_draws)),
        "not_confirmed_rows": not_confirmed_rows,
        "audit_uses_confirmed_only": True,
        "confirmed_draws_in_audit": confirmed_draws,
        "filtered_confirmed_draws": filtered_draws,
        "low_reliability_confirmed_draws": low_reliability_draws,
        "source_verification_counts": _counter_rows(verification_counts),
    }
    base_payload = {
        "method": "confirmed_only_and_reliable_source_filter",
        "basis": "draw_status plus source_verification",
        "reliable_source_verification": sorted(RELIABLE_SOURCE_VERIFICATIONS),
        "min_filtered_draws": RELIABILITY_FILTER_MIN_DRAWS,
        "baseline": baseline,
        "no_new_p_values": True,
    }
    if confirmed_draws == 0:
        return {
            **base_payload,
            "status": "missing_confirmed_history",
            "filtered_confirmed_draws": 0,
            "low_reliability_confirmed_draws": 0,
            "compared_test_count": 0,
            "comparisons": [],
            "largest_effect_shift": None,
            "interpretation": "Không có kỳ confirmed để chạy kiểm tra độ nhạy dữ liệu.",
        }

    if low_reliability_draws == 0:
        return {
            **base_payload,
            "status": "confirmed_only_baseline",
            "filtered_confirmed_draws": filtered_draws,
            "low_reliability_confirmed_draws": 0,
            "compared_test_count": 0,
            "comparisons": [],
            "largest_effect_shift": None,
            "interpretation": (
                "Audit chính đã loại kỳ not_confirmed; không còn kỳ confirmed nào thuộc "
                "nhóm source_verification độ tin cậy thấp để chạy so sánh loại trừ."
            ),
        }

    if filtered_draws < RELIABILITY_FILTER_MIN_DRAWS:
        return {
            **base_payload,
            "status": "insufficient_reliable_history",
            "filtered_confirmed_draws": filtered_draws,
            "low_reliability_confirmed_draws": low_reliability_draws,
            "compared_test_count": 0,
            "comparisons": [],
            "largest_effect_shift": None,
            "interpretation": (
                "Sau khi loại các kỳ confirmed có provenance yếu, lát còn lại chưa đủ "
                "kỳ tối thiểu để đọc độ nhạy ổn định."
            ),
        }

    filtered_dataset = _dataset_with_observations(dataset, reliable_observations)
    filtered_tests = (
        _number_set_tests(filtered_dataset)
        if dataset.product.kind is AnalysisKind.NUMBER_SET
        else _digit_sequence_tests(filtered_dataset)
    )
    filtered_by_id = {test["id"]: test for test in filtered_tests}
    comparisons = [
        row
        for test in baseline_tests
        if (row := _reliability_test_comparison(test, filtered_by_id.get(test["id"])))
        is not None
    ]
    comparisons.sort(
        key=lambda row: (
            -abs(float(row["effect_size_delta"] or 0.0)),
            str(row["test_id"]),
        )
    )
    largest_effect_shift = comparisons[0] if comparisons else None
    return {
        **base_payload,
        "status": "available",
        "filtered_confirmed_draws": filtered_draws,
        "low_reliability_confirmed_draws": low_reliability_draws,
        "compared_test_count": len(comparisons),
        "comparisons": comparisons,
        "largest_effect_shift": _largest_reliability_shift(largest_effect_shift),
        "interpretation": (
            "So sánh lại cùng phép kiểm trên lát kỳ confirmed có source_verification đáng tin cậy. "
            "Các dòng chỉ công bố statistic, effect và chênh lệch mẫu; không tạo p-value, "
            "q-value hoặc status mới."
        ),
    }


def _dataset_with_observations(
    dataset: ProductDataset,
    observations: list[Any],
) -> ProductDataset:
    draw_ids = {observation.draw_id for observation in observations}
    return ProductDataset(
        product=dataset.product,
        observations=list(observations),
        source_counts=Counter(observation.source_host for observation in observations),
        data_source_counts=Counter(observation.data_source for observation in observations),
        status_counts=Counter({"confirmed": len(observations)}),
        validation_counts=Counter(),
        source_origin_counts=Counter(
            observation.source_origin for observation in observations
        ),
        source_verification_counts=Counter(
            observation.source_verification for observation in observations
        ),
        latest_fetched_at=dataset.latest_fetched_at,
        jackpot_values=[
            item
            for item in dataset.jackpot_values
            if item[0] in draw_ids
        ],
    )


def _reliability_test_comparison(
    baseline_test: dict[str, Any],
    filtered_test: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if filtered_test is None:
        return None
    baseline_statistic = baseline_test.get("statistic")
    filtered_statistic = filtered_test.get("statistic")
    baseline_effect = baseline_test.get("effect_size")
    filtered_effect = filtered_test.get("effect_size")
    if not isinstance(baseline_effect, (int, float)) or not isinstance(
        filtered_effect,
        (int, float),
    ):
        return None
    statistic_delta = (
        _round(float(filtered_statistic) - float(baseline_statistic))
        if isinstance(baseline_statistic, (int, float))
        and isinstance(filtered_statistic, (int, float))
        else None
    )
    baseline_sample = int(baseline_test.get("sample_size") or 0)
    filtered_sample = int(filtered_test.get("sample_size") or 0)
    return {
        "test_id": baseline_test["id"],
        "label": baseline_test["label"],
        "algorithm": baseline_test["algorithm"],
        "family": baseline_test["family"],
        "baseline_sample_size": baseline_sample,
        "filtered_sample_size": filtered_sample,
        "sample_size_delta": filtered_sample - baseline_sample,
        "baseline_statistic": baseline_statistic,
        "filtered_statistic": filtered_statistic,
        "statistic_delta": statistic_delta,
        "baseline_effect_size": baseline_effect,
        "filtered_effect_size": filtered_effect,
        "effect_size_delta": _round(float(filtered_effect) - float(baseline_effect)),
        "baseline_effect_size_name": baseline_test.get("effect_size_name"),
        "filtered_effect_size_name": filtered_test.get("effect_size_name"),
    }


def _largest_reliability_shift(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "test_id": row["test_id"],
        "label": row["label"],
        "baseline_sample_size": row["baseline_sample_size"],
        "filtered_sample_size": row["filtered_sample_size"],
        "effect_size_delta": row["effect_size_delta"],
        "statistic_delta": row["statistic_delta"],
    }


def _reliability_sensitivity_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {}
    largest = payload.get("largest_effect_shift") or {}
    return {
        "status": payload.get("status"),
        "method": payload.get("method"),
        "not_confirmed_rows": payload.get("baseline", {}).get("not_confirmed_rows"),
        "confirmed_draws_in_audit": payload.get("baseline", {}).get(
            "confirmed_draws_in_audit"
        ),
        "filtered_confirmed_draws": payload.get("filtered_confirmed_draws"),
        "low_reliability_confirmed_draws": payload.get(
            "low_reliability_confirmed_draws"
        ),
        "compared_test_count": payload.get("compared_test_count"),
        "largest_effect_shift": largest,
        "no_new_p_values": payload.get("no_new_p_values"),
    }


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
        "power_summary": _power_summary(tests),
        "reliability_sensitivity": _reliability_sensitivity(dataset, tests),
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
            label="Quét điểm đổi chế độ của tổng bộ số",
            values=draw_sums,
            plain_language=(
                "Nếu quy trình ổn định, trung bình tổng bộ số không nên lệch lớn "
                "ở bất kỳ điểm cắt lịch sử đã đăng ký trước nào."
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
            label="Quét điểm đổi chế độ của tổng chữ số",
            values=digit_sums,
            plain_language=(
                "Nếu quy trình ổn định, trung bình tổng chữ số không nên lệch lớn "
                "ở bất kỳ điểm cắt lịch sử đã đăng ký trước nào."
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
        power_sample_size=effect_denominator,
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
        power_sample_size=effect_denominator,
    )


def _runs_statistics(values: list[int], center: float) -> dict[str, float | int] | None:
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
    return {"z_score": z_score, "runs": runs, "expected_runs": expected, "total": total}


def _lag1_autocorrelation(values: list[int]) -> float | None:
    if len(values) < 8:
        return None
    return _correlation(values[:-1], values[1:])


def _change_point_candidate_indices(value_count: int) -> list[int]:
    if value_count < CHANGE_POINT_MIN_VALUES:
        return []
    min_segment = max(CHANGE_POINT_MIN_SEGMENT_VALUES, round(value_count * 0.1))
    candidates = {
        round(value_count * fraction)
        for fraction in CHANGE_POINT_CANDIDATE_FRACTIONS
    }
    return sorted(
        index
        for index in candidates
        if min_segment <= index <= value_count - min_segment
    )


def _change_point_candidate_statistics(
    values: list[int],
    candidate_index: int,
) -> dict[str, float]:
    first = values[:candidate_index]
    second = values[candidate_index:]
    first_mean = fmean(first)
    second_mean = fmean(second)
    first_sd = stdev(first)
    second_sd = stdev(second)
    standard_error = math.sqrt((first_sd**2 / len(first)) + (second_sd**2 / len(second)))
    difference = second_mean - first_mean
    z_score = difference / standard_error if standard_error else 0.0
    pooled = math.sqrt((first_sd**2 + second_sd**2) / 2) if first_sd or second_sd else 0.0
    effect = abs(difference) / pooled if pooled else 0.0
    return {
        "candidate_index": float(candidate_index),
        "candidate_fraction": candidate_index / len(values),
        "first_segment_count": float(len(first)),
        "second_segment_count": float(len(second)),
        "first_segment_mean": first_mean,
        "second_segment_mean": second_mean,
        "difference": difference,
        "z_score": z_score,
        "max_abs_z_score": abs(z_score),
        "raw_p_value": _two_sided_normal_p(z_score),
        "effect": effect,
        "power_sample_size": 1 / ((1 / len(first)) + (1 / len(second))),
    }


def _public_change_point_candidate(row: dict[str, float]) -> dict[str, float | int]:
    return {
        "candidate_index": int(row["candidate_index"]),
        "candidate_fraction": _round(row["candidate_fraction"], 4),
        "first_segment_count": int(row["first_segment_count"]),
        "second_segment_count": int(row["second_segment_count"]),
        "first_segment_mean": _round(row["first_segment_mean"]),
        "second_segment_mean": _round(row["second_segment_mean"]),
        "difference": _round(row["difference"]),
        "z_score": _round(row["z_score"]),
        "raw_p_value": _round(row["raw_p_value"], 8),
        "effect": _round(row["effect"]),
    }


def _change_point_scan_statistics(values: list[int]) -> dict[str, Any] | None:
    candidate_indices = _change_point_candidate_indices(len(values))
    if not candidate_indices:
        return None
    rows = [
        _change_point_candidate_statistics(values, candidate_index)
        for candidate_index in candidate_indices
    ]
    strongest = min(
        rows,
        key=lambda row: (row["raw_p_value"], -row["max_abs_z_score"], row["candidate_index"]),
    )
    raw_p_value = strongest["raw_p_value"]
    adjusted_p_value = min(1.0, raw_p_value * len(rows))
    public_candidates = [_public_change_point_candidate(row) for row in rows]
    public_strongest = _public_change_point_candidate(strongest)
    public_strongest["adjusted_p_value"] = _round(adjusted_p_value, 8)
    return {
        **strongest,
        "candidate_count": len(rows),
        "candidate_fractions": CHANGE_POINT_CANDIDATE_FRACTIONS,
        "raw_p_value": raw_p_value,
        "bonferroni_p_value": adjusted_p_value,
        "adjusted_p_value": adjusted_p_value,
        "multiple_candidate_correction": "bonferroni",
        "scan": {
            "status": "available",
            "method": "pre_registered_candidate_scan",
            "candidate_fractions": CHANGE_POINT_CANDIDATE_FRACTIONS,
            "candidate_count": len(rows),
            "minimum_segment_values": max(
                CHANGE_POINT_MIN_SEGMENT_VALUES,
                round(len(values) * 0.1),
            ),
            "multiple_candidate_correction": "bonferroni",
            "statistic_name": "max_abs_z_score",
            "raw_p_value": _round(raw_p_value, 8),
            "adjusted_p_value": _round(adjusted_p_value, 8),
            "strongest_candidate": public_strongest,
            "candidates": public_candidates,
            "no_unadjusted_search_decision": True,
        },
    }


def _diagnostic_sample_values(values: list[int], max_values: int) -> tuple[list[int], str]:
    if len(values) <= max_values:
        return list(values), "full_sequence"
    step = len(values) / max_values
    sampled = [
        values[min(len(values) - 1, int(index * step))]
        for index in range(max_values)
    ]
    return sampled, "deterministic_even_spacing"


def _diagnostic_seed(
    *,
    test_id: str,
    values: list[int],
    method_version: str,
) -> tuple[str, str]:
    values_hash = hashlib.sha256(",".join(str(value) for value in values).encode()).hexdigest()
    seed_hex = hashlib.sha256(
        f"{test_id}:{len(values)}:{values_hash}:{method_version}".encode()
    ).hexdigest()[:16]
    return seed_hex, values_hash


def _permutation_check(
    *,
    test_id: str,
    values: list[int],
    statistic_name: str,
    statistic_fn: Callable[[list[int]], float | None],
    preserve_unit: str,
) -> dict[str, Any]:
    full_count = len(values)
    if full_count < PERMUTATION_MIN_VALUES:
        return {
            "status": "not_available",
            "method": "whole_observation_label_permutation",
            "reason": "Không đủ quan sát để chạy permutation check đã khóa.",
            "minimum_values": PERMUTATION_MIN_VALUES,
            "full_value_count": full_count,
            "no_multiple_testing_decision": True,
        }

    sampled_values, sampling_method = _diagnostic_sample_values(values, PERMUTATION_MAX_VALUES)
    observed = statistic_fn(sampled_values)
    if observed is None:
        return {
            "status": "not_available",
            "method": "whole_observation_label_permutation",
            "reason": "Thống kê không xác định trên mẫu giữ nguyên đơn vị quan sát.",
            "full_value_count": full_count,
            "permutation_value_count": len(sampled_values),
            "sampling_method": sampling_method,
            "no_multiple_testing_decision": True,
        }

    seed_hex, _values_hash = _diagnostic_seed(
        test_id=test_id,
        values=values,
        method_version="permutation-v1",
    )
    rng = random.Random(int(seed_hex, 16))
    extreme = 0
    for _ in range(PERMUTATION_COUNT):
        shuffled = list(sampled_values)
        rng.shuffle(shuffled)
        candidate = statistic_fn(shuffled)
        if candidate is not None and abs(candidate) >= abs(observed) - 1e-12:
            extreme += 1

    return {
        "status": "available",
        "method": "whole_observation_label_permutation",
        "alternative": "two_sided_absolute_statistic",
        "permutations": PERMUTATION_COUNT,
        "seed": seed_hex,
        "statistic_name": statistic_name,
        "observed_statistic": _round(observed),
        "empirical_p_value": _round((extreme + 1) / (PERMUTATION_COUNT + 1), 6),
        "extreme_count": extreme,
        "full_value_count": full_count,
        "permutation_value_count": len(sampled_values),
        "sampling_method": sampling_method,
        "preserve_unit": preserve_unit,
        "no_multiple_testing_decision": True,
        "interpretation": (
            "Hoán vị chỉ tráo thứ tự các đơn vị quan sát đã có, giữ nguyên cấu trúc "
            "bên trong từng kỳ hoặc từng kết quả và không đổi q/status chính."
        ),
    }


def _block_bootstrap_check(
    *,
    test_id: str,
    values: list[int],
    statistic_name: str,
    statistic_fn: Callable[[list[int]], float | None],
) -> dict[str, Any]:
    full_count = len(values)
    if full_count < BLOCK_BOOTSTRAP_MIN_VALUES:
        return {
            "status": "not_available",
            "method": "moving_block_bootstrap",
            "reason": "Không đủ quan sát để chạy block bootstrap đã khóa.",
            "minimum_values": BLOCK_BOOTSTRAP_MIN_VALUES,
            "full_value_count": full_count,
            "no_multiple_testing_decision": True,
        }

    sampled_values, sampling_method = _diagnostic_sample_values(
        values,
        BLOCK_BOOTSTRAP_MAX_VALUES,
    )
    observed = statistic_fn(sampled_values)
    if observed is None:
        return {
            "status": "not_available",
            "method": "moving_block_bootstrap",
            "reason": "Thống kê không xác định trên mẫu block bootstrap.",
            "full_value_count": full_count,
            "bootstrap_value_count": len(sampled_values),
            "sampling_method": sampling_method,
            "no_multiple_testing_decision": True,
        }

    block_length = _block_bootstrap_length(len(sampled_values))
    starts = list(range(0, max(1, len(sampled_values) - block_length + 1)))
    seed_hex, _values_hash = _diagnostic_seed(
        test_id=test_id,
        values=values,
        method_version="block-bootstrap-v1",
    )
    rng = random.Random(int(seed_hex, 16))
    statistics: list[float] = []
    for _ in range(BLOCK_BOOTSTRAP_RESAMPLES):
        bootstrapped: list[int] = []
        while len(bootstrapped) < len(sampled_values):
            start = rng.choice(starts)
            bootstrapped.extend(sampled_values[start : start + block_length])
        candidate = statistic_fn(bootstrapped[: len(sampled_values)])
        if candidate is not None and math.isfinite(candidate):
            statistics.append(candidate)

    if not statistics:
        return {
            "status": "not_available",
            "method": "moving_block_bootstrap",
            "reason": "Không tạo được thống kê bootstrap hợp lệ.",
            "full_value_count": full_count,
            "bootstrap_value_count": len(sampled_values),
            "block_length": block_length,
            "sampling_method": sampling_method,
            "no_multiple_testing_decision": True,
        }

    ordered = sorted(statistics)
    alpha = 1 - BLOCK_BOOTSTRAP_CONFIDENCE_LEVEL
    lower = _percentile(ordered, alpha / 2)
    upper = _percentile(ordered, 1 - alpha / 2)
    return {
        "status": "available",
        "method": "moving_block_bootstrap",
        "resamples": BLOCK_BOOTSTRAP_RESAMPLES,
        "seed": seed_hex,
        "statistic_name": statistic_name,
        "observed_statistic": _round(observed),
        "bootstrap_mean": _round(fmean(statistics)),
        "confidence_level": BLOCK_BOOTSTRAP_CONFIDENCE_LEVEL,
        "confidence_interval_lower": _round(lower),
        "confidence_interval_upper": _round(upper),
        "block_length": block_length,
        "full_value_count": full_count,
        "bootstrap_value_count": len(sampled_values),
        "sampling_method": sampling_method,
        "preserve_time_structure": "contiguous_observation_blocks",
        "no_multiple_testing_decision": True,
        "interpretation": (
            "Block bootstrap resample các đoạn liên tiếp để giữ nhịp thời gian cục bộ. "
            "Khoảng bootstrap chỉ là chẩn đoán độ bền và không đổi p/q/status chính."
        ),
    }


def _block_bootstrap_length(value_count: int) -> int:
    return max(4, min(50, round(math.sqrt(value_count))))


def _percentile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        return 0.0
    position = (len(sorted_values) - 1) * max(0.0, min(1.0, probability))
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return sorted_values[lower_index]
    fraction = position - lower_index
    return sorted_values[lower_index] * (1 - fraction) + sorted_values[upper_index] * fraction


def _permutation_preserve_unit(test_id: str) -> str:
    if test_id.startswith("number_"):
        return "whole_draw_sum"
    if "digit_sum" in test_id:
        return "whole_digit_sum"
    if test_id.startswith("digit_"):
        return "whole_digit_value"
    return "whole_observation"


def _runs_test(
    *,
    test_id: str,
    label: str,
    values: list[int],
    center: float,
    plain_language: str,
) -> dict[str, Any] | None:
    stats = _runs_statistics(values, center)
    if stats is None:
        return None
    z_score = float(stats["z_score"])
    total = int(stats["total"])

    def statistic_fn(sample: list[int]) -> float | None:
        sample_stats = _runs_statistics(sample, center)
        return None if sample_stats is None else float(sample_stats["z_score"])

    permutation_check = _permutation_check(
        test_id=test_id,
        values=values,
        statistic_name="z_score",
        statistic_fn=statistic_fn,
        preserve_unit=_permutation_preserve_unit(test_id),
    )
    block_bootstrap_check = _block_bootstrap_check(
        test_id=test_id,
        values=values,
        statistic_name="z_score",
        statistic_fn=statistic_fn,
    )
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
        parameters={
            "center": _round(center),
            "runs": int(stats["runs"]),
            "expected_runs": _round(float(stats["expected_runs"])),
            "permutation_check": permutation_check,
            "block_bootstrap_check": block_bootstrap_check,
        },
    )


def _autocorrelation_test(
    *,
    test_id: str,
    label: str,
    values: list[int],
    plain_language: str,
) -> dict[str, Any] | None:
    coefficient = _lag1_autocorrelation(values)
    if coefficient is None:
        return None
    z_score = coefficient * math.sqrt(len(values) - 1)
    permutation_check = _permutation_check(
        test_id=test_id,
        values=values,
        statistic_name="autocorrelation",
        statistic_fn=_lag1_autocorrelation,
        preserve_unit=_permutation_preserve_unit(test_id),
    )
    block_bootstrap_check = _block_bootstrap_check(
        test_id=test_id,
        values=values,
        statistic_name="autocorrelation",
        statistic_fn=_lag1_autocorrelation,
    )
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
        sample_size=len(values) - 1,
        parameters={
            "lag": 1,
            "permutation_check": permutation_check,
            "block_bootstrap_check": block_bootstrap_check,
        },
    )


def _split_half_change_test(
    *,
    test_id: str,
    label: str,
    values: list[int],
    plain_language: str,
) -> dict[str, Any] | None:
    stats = _change_point_scan_statistics(values)
    if stats is None:
        return None
    max_abs_z_score = stats["max_abs_z_score"]
    effect = stats["effect"]

    def statistic_fn(sample: list[int]) -> float | None:
        sample_stats = _change_point_scan_statistics(sample)
        return None if sample_stats is None else sample_stats["max_abs_z_score"]

    permutation_check = _permutation_check(
        test_id=test_id,
        values=values,
        statistic_name="max_abs_z_score",
        statistic_fn=statistic_fn,
        preserve_unit=_permutation_preserve_unit(test_id),
    )
    block_bootstrap_check = _block_bootstrap_check(
        test_id=test_id,
        values=values,
        statistic_name="max_abs_z_score",
        statistic_fn=statistic_fn,
    )
    return _test_result(
        test_id=test_id,
        family="change_point",
        algorithm="Pre-Registered Multi-Candidate Change-Point Scan",
        label=label,
        plain_language=plain_language,
        statistic_name="max_abs_z_score",
        statistic=max_abs_z_score,
        p_value=stats["bonferroni_p_value"],
        effect_size_name="standardized mean difference",
        effect_size=effect,
        practical_threshold=0.15,
        sample_size=len(values),
        power_sample_size=stats["power_sample_size"],
        parameters={
            "first_segment_mean": _round(stats["first_segment_mean"]),
            "second_segment_mean": _round(stats["second_segment_mean"]),
            "first_half_mean": _round(stats["first_segment_mean"]),
            "second_half_mean": _round(stats["second_segment_mean"]),
            "change_point_scan": stats["scan"],
            "permutation_check": permutation_check,
            "block_bootstrap_check": block_bootstrap_check,
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
        power_sample_size=total,
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
        power_sample_size=total_digits,
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


def _pair_vector_index(left: int, right: int, pool_min: int, pool_size: int) -> int:
    left_index = left - pool_min
    right_index = right - pool_min
    return (
        left_index * (2 * pool_size - left_index - 1) // 2
        + (right_index - left_index - 1)
    )


def _dense_pair_counts(
    dataset: ProductDataset,
    *,
    pool_min: int,
    pool_max: int,
) -> tuple[list[int], list[tuple[int, int]], int]:
    pool = list(range(pool_min, pool_max + 1))
    pair_labels = list(combinations(pool, 2))
    counts = [0] * len(pair_labels)
    observed_pair_count = 0
    pool_size = len(pool)
    for observation in dataset.observations:
        values = sorted({
            value
            for value in observation.values
            if pool_min <= value <= pool_max
        })
        observed_pair_count += math.comb(len(values), 2) if len(values) >= 2 else 0
        for left_offset, left in enumerate(values[:-1]):
            for right in values[left_offset + 1 :]:
                counts[_pair_vector_index(left, right, pool_min, pool_size)] += 1
    return counts, pair_labels, observed_pair_count


def _top_pair_rows(
    pair_counts: list[int],
    pair_labels: list[tuple[int, int]],
    *,
    expected: float,
) -> list[dict[str, Any]]:
    top_indices = sorted(
        range(len(pair_counts)),
        key=lambda index: pair_counts[index],
        reverse=True,
    )[:PAIR_COOCCURRENCE_TOP_PAIRS]
    return [
        {
            "pair": list(pair_labels[index]),
            "count": pair_counts[index],
            "expected_count": _round(expected),
            "ratio_to_expected": _round(pair_counts[index] / expected) if expected else 0.0,
        }
        for index in top_indices
    ]


def _pair_co_occurrence_test(dataset: ProductDataset) -> dict[str, Any] | None:
    product = dataset.product
    pick_count = product.pick_count or 0
    if pick_count < 2 or product.pool_size < 2:
        return None
    total_pair_observations = len(dataset.observations) * math.comb(pick_count, 2)
    pool_min = product.pool_min or 1
    pool_max = product.pool_max or 0
    pair_space = math.comb(product.pool_size, 2)
    if pair_space > PAIR_COOCCURRENCE_MAX_PAIR_SPACE:
        return _skipped_test(
            test_id="number_pair_co_occurrence",
            family="co_occurrence",
            algorithm="Co-occurrence Pair Chi-Square Test",
            label="Đồng xuất hiện của các cặp số",
            plain_language=(
                "Tạm hoãn kiểm định cặp đầy đủ vì không gian cặp quá lớn cho workflow cập nhật thường xuyên."
            ),
            sample_size=len(dataset.observations),
            parameters={
                "pair_space": pair_space,
                "pair_space_limit": PAIR_COOCCURRENCE_MAX_PAIR_SPACE,
                "pair_observations": total_pair_observations,
                "no_sampling": True,
            },
        )
    pair_counts, pair_labels, observed_pair_count = _dense_pair_counts(
        dataset,
        pool_min=pool_min,
        pool_max=pool_max,
    )
    probability = pick_count * (pick_count - 1) / (product.pool_size * (product.pool_size - 1))
    expected = len(dataset.observations) * probability
    if expected <= 0:
        return None
    statistic = sum(((count - expected) ** 2) / expected for count in pair_counts)
    top_index = max(range(len(pair_counts)), key=pair_counts.__getitem__)
    top_pair = pair_labels[top_index]
    top_count = pair_counts[top_index]
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
        degrees_of_freedom=pair_space - 1,
        p_value=_chi_square_survival_approx(statistic, pair_space - 1),
        effect_size_name="pair co-occurrence w",
        effect_size=math.sqrt(statistic / total_pair_observations)
        if total_pair_observations
        else 0.0,
        practical_threshold=0.05,
        sample_size=len(dataset.observations),
        power_sample_size=total_pair_observations,
        parameters={
            "counting_method": "dense_pair_index_vector",
            "no_sampling": True,
            "pairs": pair_space,
            "pair_space": pair_space,
            "pair_observations": total_pair_observations,
            "observed_pair_observations": observed_pair_count,
            "expected_count_per_pair": _round(expected),
            "highest_count_pair": list(top_pair),
            "highest_count": top_count,
            "highest_count_ratio_to_expected": _round(top_count / expected),
            "top_pairs": _top_pair_rows(pair_counts, pair_labels, expected=expected),
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
        power_sample_size=len(outcomes) * length,
        parameters={
            "expected_per_position_digit": _round(expected),
            "position_residuals": residuals,
            "tier_breakdown": _digit_tier_breakdown(dataset, symbols),
            "period_breakdown": _digit_period_breakdown(dataset, symbols),
            "source_breakdown": _digit_source_breakdown(dataset, symbols),
            "source_leave_one_out": _digit_source_leave_one_out(dataset, symbols),
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


def _digit_source_groups(
    dataset: ProductDataset,
    length: int,
) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for observation in dataset.observations:
        outcomes = [
            outcome
            for outcome in observation.outcomes
            if len(outcome) == length and outcome.isdigit()
        ]
        if not outcomes:
            continue
        source_key = _observation_source_key(observation)
        group = groups.setdefault(
            source_key,
            {
                "observations": [],
                "outcomes": [],
                "source_hosts": Counter(),
                "source_origins": Counter(),
                "source_verification": Counter(),
            },
        )
        group["observations"].append(observation)
        group["outcomes"].extend(outcomes)
        group["source_hosts"][observation.source_host or "unknown"] += 1
        group["source_origins"][observation.source_origin or "unknown"] += 1
        group["source_verification"][observation.source_verification or "unknown"] += 1

    return groups


def _digit_position_profile(
    outcomes: list[str],
    symbols: list[int],
    length: int,
    *,
    top_residual_limit: int,
) -> dict[str, Any]:
    if not outcomes or not symbols or length <= 0:
        return {
            "expected_per_position_digit": None,
            "statistic": 0.0,
            "effect_size": 0.0,
            "max_abs_standardized_residual": 0.0,
            "top_residuals": [],
        }

    position_counts = [Counter() for _ in range(length)]
    for outcome in outcomes:
        for position, char in enumerate(outcome):
            position_counts[position][int(char)] += 1
    expected = len(outcomes) / len(symbols)
    residuals = []
    raw_statistic = 0.0
    for position, counter in enumerate(position_counts):
        for digit in symbols:
            contribution = (
                ((counter[digit] - expected) ** 2) / expected if expected > 0 else 0.0
            )
            raw_statistic += contribution
            residuals.append(
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
                    "chi_square_contribution": _round(contribution),
                }
            )
    max_abs_residual = max(
        (abs(float(item["standardized_residual"])) for item in residuals),
        default=0.0,
    )
    top_residuals = sorted(
        residuals,
        key=lambda item: abs(float(item["standardized_residual"])),
        reverse=True,
    )[:top_residual_limit]
    return {
        "expected_per_position_digit": _round(expected),
        "statistic": _round(raw_statistic),
        "effect_size": _round(
            math.sqrt(raw_statistic / (len(outcomes) * length))
            if outcomes and length
            else 0.0
        ),
        "max_abs_standardized_residual": _round(max_abs_residual),
        "top_residuals": top_residuals,
    }


def _digit_source_leave_one_out(
    dataset: ProductDataset,
    symbols: list[int],
) -> dict[str, Any]:
    product = dataset.product
    length = product.sequence_length or 0
    groups = _digit_source_groups(dataset, length)
    if not groups:
        return {
            "status": "missing_source_metadata",
            "basis": "attributes_json.data_source with source_url host fallback",
            "method": "source_leave_one_out",
            "min_source_draws": DIGIT_SOURCE_MIN_DRAWS,
            "source_count": 0,
            "eligible_source_count": 0,
            "baseline": None,
            "excluded_sources": [],
            "no_new_p_values": True,
            "interpretation": (
                "Không có outcome dùng được để chạy độ nhạy khi loại từng nguồn."
            ),
        }

    baseline_outcomes = [
        outcome
        for group in groups.values()
        for outcome in group["outcomes"]
    ]
    baseline = _digit_position_profile(
        baseline_outcomes,
        symbols,
        length,
        top_residual_limit=DIGIT_SOURCE_LEAVE_ONE_OUT_TOP_RESIDUALS,
    )
    baseline_draws = sum(len(group["observations"]) for group in groups.values())
    baseline_summary = {
        "draws": baseline_draws,
        "outcomes": len(baseline_outcomes),
        "statistic": baseline["statistic"],
        "effect_size": baseline["effect_size"],
        "max_abs_standardized_residual": baseline["max_abs_standardized_residual"],
    }
    if len(groups) == 1:
        return {
            "status": "single_source",
            "basis": "attributes_json.data_source with source_url host fallback",
            "method": "source_leave_one_out",
            "min_source_draws": DIGIT_SOURCE_MIN_DRAWS,
            "source_count": 1,
            "eligible_source_count": 0,
            "baseline": baseline_summary,
            "excluded_sources": [],
            "strongest_effect_shift": None,
            "no_new_p_values": True,
            "interpretation": (
                "Chỉ có một nguồn có outcome dùng được, nên không thể loại một nguồn "
                "mà vẫn còn lát dữ liệu đối chứng."
            ),
        }

    rows = [
        _digit_source_leave_one_out_row(
            source_key=source_key,
            group=group,
            groups=groups,
            baseline=baseline,
            symbols=symbols,
            length=length,
        )
        for source_key, group in groups.items()
    ]
    rows.sort(
        key=lambda item: (
            -abs(float(item["effect_size_delta"] or 0.0)),
            -int(item["excluded_outcomes"]),
            str(item["excluded_source_key"]),
        )
    )
    eligible_rows = [item for item in rows if item["sample_status"] == "usable"]
    if not eligible_rows:
        status = "insufficient_remaining_data"
    elif len(eligible_rows) < len(rows):
        status = "limited_comparison"
    else:
        status = "available"
    strongest_row = eligible_rows[0] if eligible_rows else rows[0]
    strongest_effect_shift = {
        "excluded_source_key": strongest_row["excluded_source_key"],
        "excluded_source_label": strongest_row["excluded_source_label"],
        "sample_status": strongest_row["sample_status"],
        "remaining_draws": strongest_row["remaining_draws"],
        "remaining_outcomes": strongest_row["remaining_outcomes"],
        "statistic_delta": strongest_row["statistic_delta"],
        "effect_size_delta": strongest_row["effect_size_delta"],
        "relative_effect_shift": strongest_row["relative_effect_shift"],
    }
    return {
        "status": status,
        "basis": "attributes_json.data_source with source_url host fallback",
        "method": "source_leave_one_out",
        "min_source_draws": DIGIT_SOURCE_MIN_DRAWS,
        "source_count": len(groups),
        "eligible_source_count": len(eligible_rows),
        "baseline": baseline_summary,
        "excluded_sources": rows,
        "strongest_effect_shift": strongest_effect_shift,
        "no_new_p_values": True,
        "interpretation": (
            "Loại từng nguồn rồi tính lại thống kê và độ lớn hiệu ứng để xem kết luận "
            "mô tả có phụ thuộc quá mạnh vào một parser, mirror hoặc vùng provenance hay không. "
            "Bảng này không sinh p-value, q-value hoặc trạng thái mới."
        ),
    }


def _digit_source_leave_one_out_row(
    *,
    source_key: str,
    group: dict[str, Any],
    groups: dict[str, dict[str, Any]],
    baseline: dict[str, Any],
    symbols: list[int],
    length: int,
) -> dict[str, Any]:
    remaining_observations = [
        observation
        for other_key, other_group in groups.items()
        if other_key != source_key
        for observation in other_group["observations"]
    ]
    remaining_outcomes = [
        outcome
        for other_key, other_group in groups.items()
        if other_key != source_key
        for outcome in other_group["outcomes"]
    ]
    profile = _digit_position_profile(
        remaining_outcomes,
        symbols,
        length,
        top_residual_limit=DIGIT_SOURCE_LEAVE_ONE_OUT_TOP_RESIDUALS,
    )
    baseline_statistic = float(baseline["statistic"] or 0.0)
    baseline_effect = float(baseline["effect_size"] or 0.0)
    statistic_delta = float(profile["statistic"] or 0.0) - baseline_statistic
    effect_delta = float(profile["effect_size"] or 0.0) - baseline_effect
    sample_status = (
        "usable"
        if len(remaining_observations) >= DIGIT_SOURCE_MIN_DRAWS
        and len(remaining_outcomes) > 0
        else "too_small"
    )
    return {
        "excluded_source_key": source_key,
        "excluded_source_label": SOURCE_LABELS.get(source_key, source_key.replace("_", " ")),
        "excluded_draws": len(group["observations"]),
        "excluded_outcomes": len(group["outcomes"]),
        "excluded_source_hosts": _counter_rows(group["source_hosts"]),
        "excluded_source_origins": _counter_rows(group["source_origins"]),
        "excluded_source_verification": _counter_rows(group["source_verification"]),
        "remaining_draws": len(remaining_observations),
        "remaining_outcomes": len(remaining_outcomes),
        "sample_status": sample_status,
        "expected_per_position_digit": profile["expected_per_position_digit"],
        "statistic": profile["statistic"],
        "statistic_delta": _round(statistic_delta),
        "effect_size": profile["effect_size"],
        "effect_size_delta": _round(effect_delta),
        "relative_effect_shift": _round(effect_delta / baseline_effect)
        if baseline_effect
        else None,
        "max_abs_standardized_residual": profile["max_abs_standardized_residual"],
        "top_residuals": profile["top_residuals"],
        "sample_note": (
            "Phần còn lại chưa đủ kỳ tối thiểu nên dòng này chỉ dùng để rà provenance."
            if sample_status == "too_small"
            else ""
        ),
    }


def _digit_source_breakdown(
    dataset: ProductDataset,
    symbols: list[int],
) -> dict[str, Any]:
    product = dataset.product
    length = product.sequence_length or 0
    groups = _digit_source_groups(dataset, length)
    if not groups:
        return {
            "status": "missing_source_metadata",
            "basis": "attributes_json.data_source with source_url host fallback",
            "sources": [],
            "min_source_draws": DIGIT_SOURCE_MIN_DRAWS,
            "no_new_p_values": True,
            "interpretation": "Không có outcome dùng được để phân rã tín hiệu theo nguồn.",
        }

    sources = [
        _digit_source_row(
            source_key=source_key,
            group=group,
            symbols=symbols,
            length=length,
        )
        for source_key, group in groups.items()
    ]
    sources.sort(key=lambda item: (-int(item["outcomes"]), str(item["source_key"])))
    eligible_sources = [item for item in sources if item["sample_status"] == "usable"]
    if len(sources) == 1:
        status = "single_source"
    elif len(eligible_sources) < 2:
        status = "limited_comparison"
    else:
        status = "available"
    return {
        "status": status,
        "basis": "attributes_json.data_source with source_url host fallback",
        "min_source_draws": DIGIT_SOURCE_MIN_DRAWS,
        "source_count": len(sources),
        "eligible_source_count": len(eligible_sources),
        "independent_source_check": "complete"
        if len(eligible_sources) >= 2
        else "limited_by_source_coverage",
        "sources": sources,
        "no_new_p_values": True,
        "interpretation": (
            "Các hàng theo nguồn giúp kiểm tra tín hiệu có tập trung ở một parser hoặc mirror hay không. "
            "Nguồn quá ít kỳ chỉ dùng để rà dữ liệu, không dùng làm đối chứng thống kê."
        ),
    }


def _digit_source_row(
    *,
    source_key: str,
    group: dict[str, Any],
    symbols: list[int],
    length: int,
) -> dict[str, Any]:
    observations = list(group["observations"])
    outcomes = list(group["outcomes"])
    base = {
        "source_key": source_key,
        "source_label": SOURCE_LABELS.get(source_key, source_key.replace("_", " ")),
        "draws": len(observations),
        "outcomes": len(outcomes),
        "source_hosts": _counter_rows(group["source_hosts"]),
        "source_origins": _counter_rows(group["source_origins"]),
        "source_verification": _counter_rows(group["source_verification"]),
        "sample_status": "usable"
        if len(observations) >= DIGIT_SOURCE_MIN_DRAWS
        else "too_small",
    }
    if len(observations) < DIGIT_SOURCE_MIN_DRAWS:
        return {
            **base,
            "expected_per_position_digit": None,
            "chi_square_contribution": None,
            "effect_size": None,
            "max_abs_standardized_residual": None,
            "top_residuals": [],
            "sample_note": (
                "Nguồn này chưa đủ kỳ tối thiểu để đọc residual ổn định; "
                "chỉ dùng để rà parser hoặc dữ liệu nguồn."
            ),
        }

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
    )[:DIGIT_SOURCE_TOP_RESIDUALS]
    return {
        **base,
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


def _observation_source_key(observation: Any) -> str:
    if observation.data_source and observation.data_source != "unknown":
        return str(observation.data_source)
    if observation.source_host and observation.source_host != "unknown":
        return str(observation.source_host).replace(".", "_").replace("-", "_")
    return observation.data_source or observation.source_origin or "unknown"


def _counter_rows(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"key": str(key), "count": count}
        for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


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
        power_sample_size=expected_pairs,
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
    power_sample_size: float | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dependency = _test_dependency_metadata(test_id)
    power_analysis = _power_analysis(
        effect_size_name=effect_size_name,
        effect_size=effect_size,
        practical_threshold=practical_threshold,
        sample_size=sample_size,
        power_sample_size=power_sample_size,
    )
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
        "power_analysis": power_analysis,
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
        "power_analysis": {
            "status": "not_applicable",
            "method": "not_run_for_skipped_test",
            "reason": "Phép kiểm tạm hoãn nên không tính công suất cho snapshot này.",
        },
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


def _power_analysis(
    *,
    effect_size_name: str,
    effect_size: float,
    practical_threshold: float,
    sample_size: int,
    power_sample_size: float | None = None,
) -> dict[str, Any]:
    if effect_size_name in POWER_UNSUPPORTED_EFFECTS:
        return {
            "status": "unsupported_scale",
            "method": "not_available_for_extreme_value_ratio",
            "effect_size_name": effect_size_name,
            "sample_size": sample_size,
            "reason": (
                "Thang hiệu ứng này là tỷ lệ khoảng vắng cực trị; cần mô hình riêng "
                "thay vì xấp xỉ chuẩn theo căn cỡ mẫu."
            ),
        }

    effective_sample = float(power_sample_size if power_sample_size is not None else sample_size)
    if effective_sample <= 1:
        return {
            "status": "insufficient_sample",
            "method": "normal_approximation",
            "effect_size_name": effect_size_name,
            "sample_size": sample_size,
            "effective_sample_size": _round(max(0.0, effective_sample)),
            "reason": "Mẫu hiệu dụng quá nhỏ để ước lượng công suất.",
        }

    null_effect = POWER_NULL_EFFECTS.get(effect_size_name, 0.0)
    observed_delta = abs(float(effect_size) - null_effect)
    threshold_delta = abs(float(practical_threshold) - null_effect)
    z_alpha = NORMAL.inv_cdf(1 - POWER_ALPHA / 2)
    target_powers = [
        _power_target_row(
            power=power,
            effective_sample=effective_sample,
            null_effect=null_effect,
            threshold_delta=threshold_delta,
        )
        for power in POWER_LEVELS
    ]
    primary = next(
        row
        for row in target_powers
        if math.isclose(float(row["power"]), POWER_PRIMARY_LEVEL)
    )
    return {
        "status": "available",
        "method": "normal_approximation",
        "alpha": POWER_ALPHA,
        "tail": "two_sided",
        "primary_power": POWER_PRIMARY_LEVEL,
        "effect_size_name": effect_size_name,
        "sample_size": sample_size,
        "effective_sample_size": _round(effective_sample),
        "null_effect_size": _round(null_effect),
        "observed_effect_delta": _round(observed_delta),
        "observed_power": _round(
            _two_sided_power_from_delta(observed_delta, effective_sample, z_alpha),
            4,
        ),
        "practical_threshold_delta": _round(threshold_delta),
        "practical_threshold_detectable_at_primary_power": bool(
            primary["practical_threshold_detectable"]
        ),
        "target_powers": target_powers,
        "interpretation": (
            "MDE là hiệu ứng nhỏ nhất xấp xỉ có thể phát hiện ở alpha 0,05 hai phía "
            "với mẫu hiệu dụng hiện tại. Đây là phân tích công suất mô tả, không tạo p-value mới."
        ),
    }


def _power_target_row(
    *,
    power: float,
    effective_sample: float,
    null_effect: float,
    threshold_delta: float,
) -> dict[str, Any]:
    z_alpha = NORMAL.inv_cdf(1 - POWER_ALPHA / 2)
    z_power = NORMAL.inv_cdf(power)
    mde_delta = (z_alpha + z_power) / math.sqrt(effective_sample)
    sample_needed = (
        math.ceil(((z_alpha + z_power) / threshold_delta) ** 2)
        if threshold_delta > 0
        else None
    )
    row: dict[str, Any] = {
        "power": power,
        "minimum_detectable_effect_delta": _round(mde_delta),
        "minimum_detectable_effect": _round(null_effect + mde_delta),
        "practical_threshold_detectable": threshold_delta >= mde_delta,
        "sample_size_needed_for_practical_threshold": sample_needed,
    }
    if not math.isclose(null_effect, 0.0):
        row["minimum_detectable_effect_lower"] = _round(max(0.0, null_effect - mde_delta))
    return row


def _two_sided_power_from_delta(
    effect_delta: float,
    effective_sample: float,
    z_alpha: float,
) -> float:
    signal = abs(effect_delta) * math.sqrt(effective_sample)
    return (1 - NORMAL.cdf(z_alpha - signal)) + NORMAL.cdf(-z_alpha - signal)


def _power_summary(tests: list[dict[str, Any]]) -> dict[str, Any]:
    active = [test for test in tests if test.get("status") != "skipped"]
    available = [
        test
        for test in active
        if test.get("power_analysis", {}).get("status") == "available"
    ]
    detectable = [
        test
        for test in available
        if test["power_analysis"].get("practical_threshold_detectable_at_primary_power")
    ]
    unsupported = [
        test
        for test in active
        if test.get("power_analysis", {}).get("status") == "unsupported_scale"
    ]
    return {
        "method": "normal_approximation",
        "alpha": POWER_ALPHA,
        "primary_power": POWER_PRIMARY_LEVEL,
        "test_count": len(active),
        "supported_test_count": len(available),
        "unsupported_test_count": len(unsupported),
        "threshold_detectable_count": len(detectable),
        "threshold_detectable_rate": _round(len(detectable) / len(available))
        if available
        else None,
        "interpretation": (
            "Đếm số phép kiểm mà mẫu hiện tại đủ để phát hiện ngưỡng thực dụng đã khóa "
            "ở công suất xấp xỉ 80%. Các thang cực trị được đánh dấu riêng."
        ),
    }


def _global_power_summary(product_reports: list[dict[str, Any]]) -> dict[str, Any]:
    tests = [
        test
        for report in product_reports
        for test in report.get("audit", {}).get("tests", [])
    ]
    return _power_summary(tests)


def _minimum_detectable_effect_for_power(
    test: dict[str, Any],
    power: float,
) -> float | None:
    for row in test.get("power_analysis", {}).get("target_powers", []):
        if math.isclose(float(row.get("power", -1.0)), power):
            value = row.get("minimum_detectable_effect")
            return float(value) if isinstance(value, (int, float)) else None
    return None


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
