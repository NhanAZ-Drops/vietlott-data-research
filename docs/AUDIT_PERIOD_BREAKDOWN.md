# Phân rã kiểm định theo giai đoạn thời gian

Tài liệu này khóa cách đọc `period_breakdown` trong tham số của phép kiểm
`digit_position_chi_square`. Mục tiêu là xem tín hiệu vị trí chữ số có ổn định
qua các đoạn lịch sử không chồng lấn hay chỉ tập trung vào một giai đoạn.

## Phạm vi áp dụng

`period_breakdown` chỉ áp dụng cho sản phẩm chuỗi chữ số có đủ kết quả đầy đủ
để chia lịch sử đã xác nhận thành ba đoạn liên tiếp. Mỗi đoạn cần tối thiểu 30
kỳ quay có outcome dùng được. Nếu không đủ mẫu, trường này trả về
`status = "insufficient_data"` và không hiển thị bảng giai đoạn trên website.

Các đoạn được chia theo thứ tự kỳ quay đã xác nhận trong dữ liệu, sau khi sắp xếp
theo ngày quay và mã kỳ. Một kỳ chỉ nằm trong đúng một đoạn, nên các đoạn là
không chồng lấn.

## Cách đọc

Mỗi dòng trong `segments` có:

- `segment_label`: nhãn giai đoạn.
- `start_draw_id`, `end_draw_id`, `start_date`, `end_date`: biên lịch sử của đoạn.
- `draws`: số kỳ quay trong đoạn.
- `outcomes`: số chuỗi đầy đủ dùng được trong đoạn.
- `expected_per_position_digit`: kỳ vọng mỗi chữ số ở mỗi vị trí nếu phân bố đều.
- `chi_square_contribution`: đóng góp mô tả của đoạn vào độ lệch vị trí.
- `effect_size`: độ lệch chuẩn hóa trong riêng đoạn.
- `max_abs_standardized_residual`: residual tuyệt đối lớn nhất của đoạn.
- `top_residuals`: các ô vị trí và chữ số nổi bật nhất để đọc nhanh.

`period_breakdown.no_new_p_values` luôn là `true`. Các chỉ số này chỉ mô tả độ
ổn định theo thời gian của một phép kiểm đã có, không phải một bộ kiểm định mới.
Không tính p-value riêng cho từng giai đoạn sau khi đã nhìn tín hiệu tổng, vì
làm vậy sẽ tăng nguy cơ khai thác hậu nghiệm.

## Diễn giải

Nếu cùng một nhóm vị trí và chữ số tiếp tục đứng đầu trong nhiều giai đoạn, đó là
tín hiệu cần theo dõi kỹ hơn bằng giao thức đã khóa trước hoặc mẫu tương lai độc
lập. Nếu tín hiệu chỉ xuất hiện trong một giai đoạn, cần ưu tiên đọc lại dữ liệu
nguồn, parser và thay đổi quy trình công bố trước khi suy diễn thống kê.

Phân rã này không kết luận nguyên nhân. Nó chỉ giúp người đọc thấy tín hiệu tổng
đến từ toàn lịch sử hay từ một vùng thời gian cụ thể.
