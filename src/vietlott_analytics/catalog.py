from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AnalysisKind(StrEnum):
    NUMBER_SET = "number_set"
    DIGIT_SEQUENCE = "digit_sequence"


@dataclass(frozen=True, slots=True)
class AnalyticsProduct:
    slug: str
    name: str
    short_name: str
    kind: AnalysisKind
    active: bool
    pool_min: int | None = None
    pool_max: int | None = None
    pick_count: int | None = None
    special_min: int | None = None
    special_max: int | None = None
    special_count: int = 0
    sequence_length: int | None = None
    expected_outcomes_per_draw: int = 1
    note: str = ""

    @property
    def pool_size(self) -> int:
        if self.pool_min is None or self.pool_max is None:
            raise ValueError(f"{self.slug} does not have a number pool")
        return self.pool_max - self.pool_min + 1


PRODUCTS: dict[str, AnalyticsProduct] = {
    "mega645": AnalyticsProduct(
        slug="mega645",
        name="Mega 6/45",
        short_name="Mega",
        kind=AnalysisKind.NUMBER_SET,
        active=True,
        pool_min=1,
        pool_max=45,
        pick_count=6,
        note="Sáu số chính được công bố theo thứ tự tăng dần.",
    ),
    "power655": AnalyticsProduct(
        slug="power655",
        name="Power 6/55",
        short_name="Power",
        kind=AnalysisKind.NUMBER_SET,
        active=True,
        pool_min=1,
        pool_max=55,
        pick_count=6,
        special_min=1,
        special_max=55,
        special_count=1,
        note="Số đặc biệt được phân tích riêng với sáu số chính.",
    ),
    "lotto535": AnalyticsProduct(
        slug="lotto535",
        name="Lotto 5/35",
        short_name="Lotto",
        kind=AnalysisKind.NUMBER_SET,
        active=True,
        pool_min=1,
        pool_max=35,
        pick_count=5,
        special_min=1,
        special_max=12,
        special_count=1,
        note="Năm số chính và số đặc biệt thuộc hai miền giá trị khác nhau.",
    ),
    "keno": AnalyticsProduct(
        slug="keno",
        name="Keno",
        short_name="Keno",
        kind=AnalysisKind.NUMBER_SET,
        active=True,
        pool_min=1,
        pool_max=80,
        pick_count=20,
        note="Kết quả gồm 20 số trong miền 1 đến 80 và có tần suất quay cao.",
    ),
    "bingo18": AnalyticsProduct(
        slug="bingo18",
        name="Bingo18",
        short_name="Bingo18",
        kind=AnalysisKind.DIGIT_SEQUENCE,
        active=True,
        sequence_length=3,
        expected_outcomes_per_draw=1,
        note="Ba chữ số có thứ tự, mỗi vị trí nhận giá trị từ 0 đến 9.",
    ),
    "max3d": AnalyticsProduct(
        slug="max3d",
        name="Max 3D / Max 3D+",
        short_name="Max 3D",
        kind=AnalysisKind.DIGIT_SEQUENCE,
        active=True,
        sequence_length=3,
        expected_outcomes_per_draw=20,
        note="Báo cáo mô tả toàn bộ bộ ba số được công bố ở các hạng giải.",
    ),
    "max3dpro": AnalyticsProduct(
        slug="max3dpro",
        name="Max 3D Pro",
        short_name="3D Pro",
        kind=AnalysisKind.DIGIT_SEQUENCE,
        active=True,
        sequence_length=3,
        expected_outcomes_per_draw=20,
        note="Báo cáo mô tả toàn bộ bộ ba số được công bố ở các hạng giải.",
    ),
    "max4d": AnalyticsProduct(
        slug="max4d",
        name="Max 4D",
        short_name="Max 4D",
        kind=AnalysisKind.DIGIT_SEQUENCE,
        active=False,
        sequence_length=4,
        expected_outcomes_per_draw=6,
        note="Sản phẩm lịch sử. Phân tích vị trí chỉ dùng các kết quả đủ bốn chữ số.",
    ),
}


PRODUCT_ORDER = (
    "mega645",
    "power655",
    "lotto535",
    "keno",
    "bingo18",
    "max3d",
    "max3dpro",
    "max4d",
)
