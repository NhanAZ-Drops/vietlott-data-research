# Tự động cập nhật

Lịch dưới đây được rà soát ngày 14/06/2026. Lịch công bố có thể thay đổi và thông
báo chính thức luôn có giá trị cao hơn tài liệu trong repo.

## Lịch dự kiến

| Sản phẩm | Lịch công bố |
| --- | --- |
| Keno | Hằng ngày từ 06:00, kết thúc không muộn hơn 21:52, cách 8 phút |
| Bingo18 | Hằng ngày từ 06:00, kết thúc không muộn hơn 21:53, cách 6 phút |
| Lotto 5/35 | Hằng ngày lúc 13:00 và 21:00 |
| Mega 6/45 | Thứ Tư, thứ Sáu, Chủ nhật lúc 18:00 |
| Power 6/55 | Thứ Ba, thứ Năm, thứ Bảy lúc 18:00 |
| Max 3D và Max 3D+ | Thứ Hai, thứ Tư, thứ Sáu lúc 18:00 |
| Max 3D Pro | Thứ Ba, thứ Năm, thứ Bảy lúc 18:00 |
| Max 4D | Đã ngừng, chỉ lưu lịch sử |

Nguồn lịch

- [Keno](https://vietlott.vn/vi/choi/keno/gioi-thieu-san-pham-keno)
- [Bingo18](https://vietlott.vn/vi/choi/bingo/gioi-thieu-san-pham-bingo18)
- [Mega 6/45](https://vietlott.vn/vi/choi/mega-6-45/gioi-thieu-san-pham-6-45)
- [Power 6/55](https://vietlott.vn/vi/choi/power-6-55/gioi-thieu-san-pham-power-655)
- [Max 3D](https://vietlott.vn/vi/choi/max3d/gioi-thieu-san-pham-max3d)
- [Max 3D Pro](https://vietlott.vn/vi/choi/max3dpro/gioi-thieu-san-pham-max3dpro)

## Workflow

`update-fast.yml` chạy mỗi 10 phút từ 06:05 đến 21:55 và thêm ba lượt dự phòng
trong giờ 22 theo giờ Việt Nam. Cron trong YAML được quy đổi sang UTC.

`update-scheduled.yml` chạy nhiều lượt sau các mốc 13:00, 18:00, 21:00 và thêm
một lượt 22:17. Mỗi lượt kiểm tra toàn bộ sản phẩm đang hoạt động trong nhóm quay
chậm. Việc kiểm tra thêm sản phẩm chỉ tạo vài request và giúp chịu được thay đổi lịch.

`ci.yml` chạy unit test, Ruff và kiểm tra toàn vẹn dataset khi mã nguồn thay đổi.

## Chịu lỗi và độ trễ

Lịch workflow chỉ là lịch thăm dò. Chương trình không tạo bản ghi vì đồng hồ đã
đến giờ.

- Nếu chưa có kết quả, workflow kết thúc mà không commit
- Nếu kết quả trễ, lượt sau tự lấy
- Nếu nhiều kỳ xuất hiện giữa hai lượt, chương trình đọc tiếp các trang cho đến vùng cũ
- Nếu kỳ bị hủy, không có bản ghi giả
- Nếu sản phẩm dừng lâu dài, workflow không tạo thay đổi dữ liệu
- Nếu mạng lỗi, HTTP client retry và tôn trọng `Retry-After`
- Nếu trang HTML bị Cloudflare chặn, chương trình dùng endpoint AjaxPro chính thức
- Nếu GitHub trì hoãn một lượt cron, lượt sau vẫn bắt kịp
- Nếu nguồn sửa kỳ gần đây, bước reconciliation cập nhật bản ghi
- Nếu HTML thay đổi bất thường, parser dừng thay vì đoán

GitHub cho biết workflow theo lịch có thể bị chậm hoặc bị bỏ trong lúc tải cao.
Các mốc của repo tránh phút đầu giờ và có nhiều lượt dự phòng. Repo công khai có
thể bị tắt lịch sau 60 ngày không có hoạt động, vì vậy cần kiểm tra tab Actions nếu
dữ liệu ngừng cập nhật bất thường.

## Quy trình một lượt

1. Checkout nhánh `main`.
2. Ghép phân vùng trong `datasets` thành CSV làm việc.
3. Nhập CSV vào SQLite.
4. Đọc trang chính thức và trang tiếp theo nếu có kỳ mới.
5. Đối chiếu lại hai trang gần nhất.
6. Áp dụng danh sách kỳ không được xác nhận.
7. Kiểm tra trùng, thiếu, JSON, khóa ngoại và kích thước tệp.
8. Chia lại dữ liệu theo sản phẩm và tháng.
9. Commit và push chỉ khi `datasets` thay đổi.

Hai workflow dùng cùng một concurrency group nên không ghi đè nhau. Quyền
`GITHUB_TOKEN` chỉ cấp `contents: write`.

Nếu nguồn lỗi nhưng một sản phẩm khác đã cập nhật hợp lệ, workflow vẫn kiểm tra và
lưu phần hợp lệ trước khi báo đỏ. Cách này vừa không mất dữ liệu vừa không che lỗi.

Commit do `GITHUB_TOKEN` tạo không kích hoạt workflow khác. Vì vậy mỗi workflow
cập nhật tự kiểm tra dữ liệu trước khi push. Website tĩnh trong tương lai nên được
triển khai ngay trong workflow cập nhật hoặc qua sự kiện `workflow_run`.
