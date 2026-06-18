# Công thức điểm của backtest

Tài liệu này khóa cách đọc `backtest.score_formulas` trong từng báo cáo sản phẩm.
Mục tiêu là công bố công thức điểm theo đúng loại sản phẩm, không gộp tập số và
chuỗi chữ số vào cùng một thước đo tổng.

## Tập số

Với sản phẩm `number_set`, đơn vị điểm là
`main_number_hits_per_draw`.

Điểm từng kỳ:

```text
hit_count_t = |predicted_main_numbers_t ∩ actual_main_numbers_t|
```

Chênh lệch ghép cặp:

```text
d_t = hit_count_t - E_uniform(hit_count_t)
```

Baseline dùng `exact_hypergeometric_expectation`. Số đặc biệt chưa được đưa vào
điểm backtest này và được ghi rõ bằng
`special_numbers_policy = special_numbers_not_scored_in_backtest`.

Baseline trùng một phần được công bố tại
`backtest.baseline.partial_match_baseline`. Với tập số, trường này dùng cùng
phân phối siêu bội của `hit_count_t`:

- `partial_match_probability`: xác suất `0 < hit_count_t < pick_count`.
- `near_probability`: xác suất `hit_count_t == pick_count - 1` và chưa đúng toàn bộ.
- `zero_match_probability`: xác suất `hit_count_t == 0`.
- `expected_partial_match_count`, `expected_near_count` và `expected_zero_match_count`:
  số lượt kỳ vọng trên đúng tập kỳ walk-forward đã khóa.

Chiến lược:

- `balanced_signal`: `0.40*short_z + 0.30*recent_z - 0.15*long_z + 0.15*(overdue_ratio - 1)`.
- `recent_frequency`: `0.60*short_z + 0.40*recent_z`.
- `audit_signal`: `0.45*clip(long_z) + 0.25*clip(recent_z) + 0.15*clip(short_z) + 0.15*pair_pressure`,
  sau đó chọn tham lam theo `audit_score + 0.12*selected_pair_bonus`.

## Chuỗi chữ số

Với sản phẩm `digit_sequence`, đơn vị điểm là
`best_position_matches_per_draw`.

Điểm từng kỳ:

```text
best_position_matches_t = max_actual sum_i 1[predicted_digit_i = actual_digit_i]
```

Nếu một kỳ có nhiều kết quả công bố, điểm là số vị trí khớp cao nhất so với các
kết quả đó. Chênh lệch ghép cặp:

```text
d_t = best_position_matches_t - E_uniform(best_position_matches_t | actual outcomes_t)
```

Baseline dùng `exact_sequence_enumeration`.

Baseline trùng một phần cũng được công bố tại
`backtest.baseline.partial_match_baseline`. Với chuỗi chữ số, trường này cộng
phân phối exact của `best_position_matches_t` theo từng kỳ:

- `partial_match_probability`: xác suất `0 < best_position_matches_t < sequence_length`.
- `near_probability`: xác suất `best_position_matches_t == sequence_length - 1` và chưa đúng toàn bộ.
- `zero_match_probability`: xác suất `best_position_matches_t == 0`.
- `expected_partial_match_count`, `expected_near_count` và `expected_zero_match_count`:
  số lượt kỳ vọng trên đúng tập kỳ walk-forward đã khóa.

Chiến lược:

- `balanced_signal`: `0.40*short_z + 0.30*recent_z - 0.20*long_z`.
- `recent_frequency`: `0.60*short_z + 0.40*recent_z`.
- `audit_signal`: `0.45*clip(long_z) + 0.35*clip(recent_z) + 0.20*clip(short_z)`.

## Trường bắt buộc

Mỗi `score_formulas` phải có `product_kind`, `score_unit`,
`per_draw_score`, `comparison_metric`, `comparison_difference`,
`baseline_method`, `variables` và `strategies`.

Các trường này chỉ công bố công thức và đơn vị đọc kết quả. Chúng không tự thay
p-value, q-value hoặc kết luận thắng baseline.

`partial_match_baseline` là baseline phụ của phần phân phối điểm. Trường này
không thay `comparison`, không tạo p-value mới và không được dùng một mình để
gọi chiến lược là tốt hơn baseline.
