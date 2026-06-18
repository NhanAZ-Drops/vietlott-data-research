# Độ nhạy theo trạng thái xác nhận và độ tin cậy nguồn

Tài liệu này khóa cách đọc `reliability_sensitivity` trong mỗi báo cáo fairness
audit của sản phẩm. Mục tiêu là kiểm tra liệu kết quả audit có phụ thuộc vào các
kỳ chưa xác nhận hoặc các vùng lịch sử có provenance yếu hay không.

## Phạm vi áp dụng

Audit chính chỉ dùng `dataset.observations`, tức các kỳ có `draw_status=confirmed`.
Các kỳ `not_confirmed` vẫn được đếm trong `baseline.not_confirmed_rows`, nhưng
không đi vào p-value, q-value hoặc trạng thái chính.

Sau lớp xác nhận, `reliability_sensitivity` tách các kỳ `confirmed` theo
`source_verification`:

- Nhóm đáng tin cậy: `official_direct`, `official_verified_match`,
  `multi_source_consensus`.
- Nhóm độ tin cậy thấp: `single_secondary_source`, `pending_official`, `unknown`.

Nếu nhóm đáng tin cậy còn tối thiểu 30 kỳ, báo cáo chạy lại cùng các phép kiểm
trên lát này để so sánh statistic và effect size với baseline confirmed đầy đủ.

## Cách đọc

Các trường chính:

- `baseline.total_rows`: tổng dòng draw trong repo cho sản phẩm.
- `baseline.confirmed_rows`: số dòng `confirmed` trong repo.
- `baseline.not_confirmed_rows`: số dòng đã bị loại khỏi audit chính.
- `baseline.confirmed_draws_in_audit`: số kỳ thật sự đi vào audit chính.
- `filtered_confirmed_draws`: số kỳ còn lại sau khi loại provenance yếu.
- `low_reliability_confirmed_draws`: số kỳ confirmed bị loại trong lát độ nhạy.
- `comparisons`: các phép kiểm có thể so sánh lại trên lát đáng tin cậy.
- `largest_effect_shift`: phép kiểm có `effect_size_delta` tuyệt đối lớn nhất.

Mỗi dòng trong `comparisons` có `baseline_sample_size`, `filtered_sample_size`,
`sample_size_delta`, `baseline_statistic`, `filtered_statistic`,
`statistic_delta`, `baseline_effect_size`, `filtered_effect_size` và
`effect_size_delta`.

## Trạng thái

- `available`: đã chạy lại trên lát đáng tin cậy đủ mẫu.
- `confirmed_only_baseline`: audit chính đã loại kỳ `not_confirmed`, và không có
  kỳ confirmed nào thuộc nhóm provenance thấp.
- `insufficient_reliable_history`: có provenance thấp, nhưng sau khi loại thì lát
  đáng tin cậy chưa đủ 30 kỳ.
- `missing_confirmed_history`: không có kỳ confirmed để audit.

## Không tạo kiểm định mới

`reliability_sensitivity.no_new_p_values` luôn là `true`. Trường này không tạo
p-value, q-value hoặc status mới. Nó chỉ giúp đọc độ bền của kết quả đã có khi
loại các vùng dữ liệu kém tin cậy hơn.

Nếu `effect_size_delta` lớn, ưu tiên kiểm tra lại provenance, parser và lịch sử
nguồn của vùng bị loại trước khi diễn giải tín hiệu thống kê.
