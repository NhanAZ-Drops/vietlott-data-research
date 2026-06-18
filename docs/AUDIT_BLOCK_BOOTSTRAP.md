# Block bootstrap cho chỉ số phụ thuộc chuỗi

`block_bootstrap_check` là lớp chẩn đoán bổ sung cho các phép kiểm fairness audit
dùng thứ tự thời gian. Khác với permutation check, block bootstrap không tráo rời
từng quan sát mà lấy lại các đoạn liên tiếp để giữ một phần nhịp thời gian cục bộ.

## Phạm vi áp dụng

Block bootstrap hiện gắn với cùng nhóm phép kiểm thứ tự:

- `number_sum_runs`
- `number_sum_lag1_autocorrelation`
- `number_sum_split_half_change`
- `digit_value_runs`
- `digit_value_lag1_autocorrelation`
- `digit_sum_split_half_change`

Mỗi lần bootstrap resample các block liền nhau cho đến khi tạo được chuỗi giả có
cùng độ dài với chuỗi chẩn đoán. Thống kê được tính lại trên chuỗi giả để tạo khoảng
ước lượng 95% cho thống kê chính.

## Trường JSON

Mỗi test được hỗ trợ có `parameters.block_bootstrap_check` gồm:

- `status`: `available` khi đã chạy được.
- `method`: luôn là `moving_block_bootstrap`.
- `resamples`: số lần bootstrap, hiện khóa ở `199`.
- `seed`: seed tái lập sinh từ test id và hash chuỗi giá trị.
- `statistic_name`: thống kê được bootstrap, ví dụ `z_score` hoặc `autocorrelation`.
- `observed_statistic`: thống kê quan sát trên chuỗi dùng cho bootstrap.
- `bootstrap_mean`: trung bình thống kê qua các lần bootstrap hợp lệ.
- `confidence_level`: hiện là `0.95`.
- `confidence_interval_lower` và `confidence_interval_upper`: khoảng bootstrap 95%.
- `block_length`: số đơn vị liên tiếp trong mỗi block.
- `preserve_time_structure`: luôn là `contiguous_observation_blocks`.
- `full_value_count`: số đơn vị quan sát gốc.
- `bootstrap_value_count`: số đơn vị thực sự đưa vào vòng bootstrap.
- `sampling_method`: `full_sequence` hoặc `deterministic_even_spacing`.
- `no_multiple_testing_decision`: luôn `true`.

## Giới hạn và cách đọc

Block bootstrap không thay `p_value`, `q_value_bh`, `q_value_global_bh` hoặc `status`
của phép kiểm chính. Nó công bố độ bền của thống kê khi chuỗi được lấy mẫu lại theo
block thời gian, không tạo thêm kết luận thắng thua.

Với chuỗi rất dài, workflow dùng tối đa 2.500 đơn vị lấy theo khoảng đều quyết định
sẵn để giữ thời gian chạy ổn định. Trường `bootstrap_value_count` và `sampling_method`
công bố rõ khi có lấy mẫu.

Website hiển thị `Block bootstrap 95%` trong chi tiết từng phép kiểm được hỗ trợ.
Dòng này ghi block length và nhắc rằng chẩn đoán không đổi q/status chính.
