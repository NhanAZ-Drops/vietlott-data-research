# Nhật ký phương pháp

Nhật ký này chỉ ghi thay đổi có thể làm đổi số liệu, trạng thái kiểm định, kết quả
backtest hoặc cách đọc website. Thay đổi giao diện thuần túy không cần mục riêng.

## 15/06/2026

### Fairness audit 2.0.0

- Tách trạng thái `statistically_notable`, `practically_large`, `both`, `pass`
  và `skipped`
- Không còn gộp mọi lý do vào nhãn `watch`
- Công bố riêng p-value, q-value, độ lớn hiệu ứng và ngưỡng thực dụng
- Khóa registry ngưỡng độ lớn hiệu ứng, đơn vị, phạm vi áp dụng và phân tích độ
  nhạy theo hệ số ngưỡng trong `site/data/audit-summary.json`
- Công bố họ phụ thuộc, ma trận cặp kiểm định và q-value Benjamini-Hochberg theo
  từng họ phụ thuộc để đọc các phép kiểm dùng chung dữ liệu
- Phân rã kiểm định vị trí chữ số theo hạng giải và loại kết quả khi
  `result_json.tiers` có đủ cấu trúc, không sinh p-value mới cho từng hạng
- Kết quả snapshot có 2 phép nổi bật thống kê, 16 phép có hiệu ứng vượt ngưỡng
  thực dụng và 0 phép đạt đồng thời cả hai điều kiện

### Backtest 2.0.0

- Đưa `recent_frequency` vào walk-forward đầy đủ
- Tăng phạm vi hiệu chỉnh từ 16 lên 24 phép so sánh
- Giữ baseline kỳ vọng chính xác thay vì một lần bốc ngẫu nhiên
- Kết quả snapshot có 0 tín hiệu thắng sau hiệu chỉnh và 2 tín hiệu thô thuộc
  Max 3D

### Prediction ledger 3.0.0

- Thêm chuỗi SHA-256 append-only
- Thêm hash toàn bộ lịch sử dữ liệu dùng cho mỗi dự đoán mới
- Thêm timezone và phiên bản code
- Thêm test phát hiện sửa, xóa, chèn và nối sự kiện chưa niêm phong

### Data quality 1.0.0

- Tách hợp lệ cấu trúc, nguồn gốc và mức đối chiếu nguồn
- Thêm quality report cho tám sản phẩm
- Thêm snapshot manifest có hash và số dòng
- Giữ lịch sử nguồn khi một quan sát mới thay thế quan sát cũ

## Quy tắc cập nhật

Mỗi thay đổi phương pháp cần ghi

- ngày áp dụng
- phiên bản cũ và mới
- phạm vi dữ liệu bị ảnh hưởng
- thay đổi công thức hoặc ngưỡng
- kết quả trước và sau nếu có
- đường dẫn test tái lập
