# Phân rã kiểm định theo hạng giải và loại kết quả

Tài liệu này khóa cách đọc `tier_breakdown` trong tham số của phép kiểm
`digit_position_chi_square`. Mục tiêu là giải thích tín hiệu vị trí của các sản
phẩm chuỗi chữ số theo hạng giải hoặc loại kết quả khi dữ liệu gốc có cấu trúc
đó.

## Phạm vi áp dụng

`tier_breakdown` chỉ dùng cho sản phẩm có `result_json.tiers`, hiện gồm Max 3D,
Max 3D Pro và Max 4D. Bingo18 chỉ có một kết quả ba vị trí trong mỗi kỳ nên không
có hạng giải để phân rã. Các sản phẩm tập số không dùng phép kiểm vị trí chữ số.

Mỗi hạng giải được đọc từ kết quả quay đã lưu trong `datasets/draws`, không đọc
từ số người trúng thưởng. Bảng giải thưởng có ích cho phân tích doanh thu và độ
phủ giải, nhưng không thay thế kết quả quay khi kiểm định phân bố chữ số.

## Loại kết quả

Các dòng `result_types` trong JSON cho biết outcome nào đi vào kiểm định vị trí:

- `full_sequence`: chuỗi đủ độ dài, ví dụ `7589`, được dùng để đếm chữ số theo
  vị trí
- `wildcard_prefix`: chuỗi có ký hiệu `X` ở đầu, ví dụ `X589` hoặc `XX89`, chỉ
  mô tả luật trùng hậu tố và không đi vào kiểm định vị trí đầy đủ
- `unusable`: giá trị không khớp cấu trúc đã khóa, chỉ được ghi để kiểm tra dữ
  liệu

## Cách đọc

Mỗi hàng trong `tiers` có

- `tier` và `tier_label`: hạng giải trong `result_json.tiers`
- `draws`: số kỳ có hạng giải đó
- `outcomes`: số chuỗi đầy đủ trong hạng
- `expected_per_position_digit`: kỳ vọng mỗi chữ số ở mỗi vị trí nếu phân bố đều
- `chi_square_contribution`: phần đóng góp mô tả vào kiểm định vị trí
- `effect_size`: độ lệch chuẩn hóa trong riêng hạng đó
- `max_abs_standardized_residual`: residual tuyệt đối lớn nhất để định hướng đọc
- `position_residuals`: residual từng ô vị trí và chữ số

Các số này là phân rã mô tả của kiểm định tổng, không phải một bộ kiểm định mới.
Không tính p-value riêng cho từng hạng sau khi đã nhìn thấy tín hiệu tổng, vì làm
vậy sẽ biến phần giải thích thành khai thác hậu nghiệm.

## Giới hạn

Nếu một hạng giải có ít outcome, residual có thể dao động mạnh hơn chỉ vì mẫu nhỏ.
Do đó `tier_breakdown` chỉ giúp xác định tín hiệu tổng tập trung ở hạng nào để
đọc lại parser và dữ liệu nguồn. Mọi xác nhận thống kê vẫn phải dùng giao thức
tái kiểm tra đã khóa trước hoặc mẫu tương lai độc lập.
