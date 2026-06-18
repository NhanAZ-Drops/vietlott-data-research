# Vietlott Data Research

Kho dữ liệu và chương trình Python phục vụ nghiên cứu cá nhân về khoa học dữ liệu,
xác suất và thống kê trên kết quả Vietlott.

Dự án ưu tiên nguồn công khai chính thức, lưu cả lịch sử đã thu thập và tự kiểm tra
kỳ mới bằng GitHub Actions. Mục tiêu là tạo một tập dữ liệu có nguồn gốc rõ ràng,
có thể tái lập và đủ thuận tiện cho phân tích bằng Python, R hoặc công cụ bảng tính.

Khi máy chạy GitHub bị Vietlott chặn truy cập, workflow dùng trang kết quả công
khai của Xổ Số Minh Ngọc làm nguồn dự phòng. Các dòng này được gắn nhãn chờ
đối chiếu và sẽ được thay bằng nguồn chính thức khi Vietlott truy cập được.

## Phạm vi dữ liệu

- Mega 6/45
- Power 6/55
- Lotto 5/35
- Max 3D và Max 3D+
- Max 3D Pro
- Max 4D lịch sử
- Keno
- Bingo18

Bản snapshot kiểm toán hiện có 379.518 bản ghi kỳ quay và tiếp tục tăng qua
workflow. Keno có dữ liệu từ mã `0000001` và 75 mã kỳ đã được nhiều nguồn đối
chiếu là không phát hành. Các kỳ bị thông báo không xác nhận được giữ lại với
`draw_status=not_confirmed` để bảo toàn dấu vết, nhưng phải loại khỏi mẫu phân
tích mặc định.

## Website thống kê

Website công khai tại
[nhanaz.github.io/vietlott-data-research](https://nhanaz.github.io/vietlott-data-research/).

Website có báo cáo riêng cho từng họ sản phẩm, gồm

- tần suất và khoảng tin cậy
- độ vắng theo số kỳ quay
- thống kê theo tháng đã chuẩn hóa theo số kỳ
- vị trí công bố và cấu trúc tổ hợp
- kiểm định đồng đều, entropy và kích thước hiệu ứng
- backtest cuốn chiếu so với baseline đồng đều
- sổ dự đoán có mã, phiên bản và kỳ dữ liệu cuối
- đối chiếu tự động khi kết quả thật xuất hiện

Ở snapshot hiện tại, các backtest được công bố chưa cho thấy chiến lược nào vượt
cách chọn ngẫu nhiên một cách đáng tin cậy. Đây là kết luận hiện tại của dự án,
không phải cách né tránh kết luận. Nếu dự đoán đã lưu trước trong tương lai tạo ra
bằng chứng ngược lại, kết luận trên website phải thay đổi theo.

Website chỉ đọc các tệp JSON gọn được tạo từ toàn bộ dataset. Trình duyệt không
phải tải hàng trăm MB CSV. Tạo lại báo cáo bằng lệnh

```powershell
vietlott-research-report --datasets-dir datasets --site-dir site
```

## Dùng dataset

Clone repo và cài chương trình

```powershell
git clone https://github.com/NhanAZ/vietlott-data-research.git
cd vietlott-data-research
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Ghép các phân vùng trong `datasets` thành CSV

```powershell
vietlott-repository-data hydrate --source-dir datasets --destination-dir data
```

Các tệp chính

- `data/draws.csv` chứa một dòng cho mỗi kỳ quay
- `data/prizes.csv` chứa thông tin giải thưởng theo kỳ
- `data/prize_rules.csv` chứa luật trả thưởng có cấu trúc ổn định
- `datasets/exclusions.csv` chứa các kỳ cần loại khỏi phân tích
- `datasets/metadata/dataset-summary.json` chứa thống kê bao phủ
- `datasets/metadata/quality-report.json` tách chất lượng cấu trúc, nguồn và độ phủ
- `datasets/metadata/snapshot-manifest.json` chứa hash và phiên bản để tái lập

Ví dụ đọc dữ liệu hợp lệ bằng pandas

```python
import pandas as pd

draws = pd.read_csv(
    "data/draws.csv",
    dtype={"product": "string", "draw_id": "string"},
)
sample = draws.loc[draws["draw_status"] == "confirmed"].copy()
```

Không nên bỏ điều kiện `draw_status` khi xây dựng mô hình hoặc kiểm định.
Điều kiện này chỉ chọn kỳ được xác nhận. Nó không thay thế kiểm tra
`validation_status` hoặc provenance nguồn.

Kiểm toán toàn bộ snapshot

```powershell
vietlott-repository-data audit --source-dir datasets
vietlott-repository-data validate --source-dir datasets
```

## Cập nhật

Keno và Bingo18 được kiểm tra mỗi 10 phút trong khung phát hành. Các sản phẩm
quay theo mốc giờ được kiểm tra nhiều lần sau các mốc dự kiến. Chương trình đọc
trạng thái thực tế từ nguồn chính thức thay vì tự tạo kỳ theo lịch.

Cách này xử lý được các trường hợp

- kết quả công bố chậm
- kỳ quay đổi lịch
- kỳ không diễn ra
- sản phẩm tạm dừng hoặc ngừng hoạt động
- workflow bị GitHub trì hoãn
- mạng lỗi tạm thời
- nguồn sửa kết quả gần nhất
- nguồn chính thức tạm chặn IP của GitHub

Nếu không có dữ liệu mới thì workflow không tạo commit. Khi một lần chạy bị lỡ,
lần sau tiếp tục đọc nhiều trang cho đến khi gặp vùng dữ liệu đã có.

Chạy cập nhật thủ công

```powershell
vietlott-auto-update --products keno bingo18 --output-dir data
vietlott-repository-data publish --source-dir data --destination-dir datasets
vietlott-weather-update --output-dir datasets/weather
vietlott-research-report --datasets-dir datasets --site-dir site
```

Dữ liệu khí tượng nằm tại `datasets/weather/daily.csv`. Đây là nhiệt độ và độ ẩm
ngoài trời tái phân tích từ ERA5-Land, ghép theo địa điểm quay được Vietlott công bố.
Nó là biến đại diện phục vụ sàng lọc giả thuyết, không phải nhiệt độ đo trong phòng quay.

## Tài liệu

- [Nguồn và quy trình thu thập](docs/THU_THAP_DU_LIEU.md)
- [Chất lượng dữ liệu và provenance](docs/CHAT_LUONG_DU_LIEU.md)
- [Cơ chế tự động cập nhật](docs/TU_DONG_CAP_NHAT.md)
- [Định hướng nghiên cứu](docs/NGHIEN_CUU.md)
- [Các trò chơi và cơ chế quay](docs/tro-choi/README.md)
- [Kiến trúc chương trình](docs/ARCHITECTURE.md)
- [Kế hoạch nâng cấp nghiên cứu](docs/TODO_NGHIEN_CUU.md)
- [Báo cáo lần dự đoán đúng Bingo18 kỳ 0171884](docs/DU_DOAN_BINGO18_0171884.md)
- [Từ điển dữ liệu](docs/DATA_DICTIONARY.md)
- [Nhật ký phương pháp](docs/METHODOLOGY_CHANGELOG.md)
- [Ngưỡng độ lớn hiệu ứng của fairness audit](docs/AUDIT_EFFECT_THRESHOLDS.md)
- [Ma trận phụ thuộc giữa các phép kiểm](docs/AUDIT_TEST_DEPENDENCIES.md)
- [Phân rã kiểm định theo hạng giải](docs/AUDIT_TIER_BREAKDOWN.md)
- [Phân rã kiểm định theo giai đoạn thời gian](docs/AUDIT_PERIOD_BREAKDOWN.md)
- [Phân rã kiểm định theo nguồn dữ liệu](docs/AUDIT_SOURCE_BREAKDOWN.md)
- [Độ nhạy khi loại từng nguồn dữ liệu](docs/AUDIT_SOURCE_SENSITIVITY.md)
- [Độ nhạy theo xác nhận và độ tin cậy nguồn](docs/AUDIT_RELIABILITY_SENSITIVITY.md)
- [Phân tích công suất của fairness audit](docs/AUDIT_POWER_ANALYSIS.md)
- [Permutation check giữ nguyên cấu trúc từng kỳ](docs/AUDIT_PERMUTATION_CHECKS.md)
- [Block bootstrap cho chỉ số phụ thuộc chuỗi](docs/AUDIT_BLOCK_BOOTSTRAP.md)
- [Change-point scan nhiều điểm ứng viên](docs/AUDIT_CHANGE_POINT_SCAN.md)
- [Đồng xuất hiện cặp số Keno](docs/AUDIT_KENO_PAIR_COOCCURRENCE.md)
- [Mẫu báo cáo kết quả âm](docs/templates/BAO_CAO_KET_QUA_AM.md)
- [Giao thức tái kiểm tra tín hiệu Max 3D](docs/protocols/MAX3D_POSITION_CONFIRMATION.md)

## Tinh thần nghiên cứu

Repo bắt đầu từ một câu hỏi cá nhân. Một hệ cơ học có thể chịu ảnh hưởng rất nhỏ
từ khối lượng bi, độ mòn, luồng khí, nhiệt độ hoặc sai số thiết bị hay không.
Nếu có, ảnh hưởng đó có đủ lớn và đủ ổn định để quan sát trong dữ liệu hay chỉ
là nhiễu không thể phân biệt với ngẫu nhiên.

Đây là giả thuyết cần kiểm định, không phải kết luận. Dự án cũng xem xét tần suất
số, độ phụ thuộc theo thời gian, entropy, độ đồng đều và thay đổi chế độ. Một bộ
số trông "đẹp" hoặc có quy luật không mặc nhiên ít có khả năng hơn một bộ cụ thể
khác trong mô hình đồng đều. Cảm giác hiếm thường đến từ cách con người gom nhiều
mẫu khác nhau thành một nhóm dễ nhận biết.

Website tĩnh trực quan hóa phân bố, sai lệch, độ bất định và kết quả kiểm định
ngoài mẫu. Mọi dự báo chỉ là thí nghiệm và luôn được so với baseline đồng đều.
Quan điểm của dự án được trình bày rõ, nhưng dữ liệu và phương pháp có quyền bác
bỏ quan điểm đó.

## Nguồn, pháp lý và trách nhiệm

Kết quả được lấy từ trang công khai của
[Vietlott](https://vietlott.vn/vi/trung-thuong/ket-qua-trung-thuong/)
và một số nguồn đối chiếu được ghi trong tài liệu kỹ thuật. Repo không liên kết,
đại diện hoặc được bảo trợ bởi Vietlott, MoMo hay đơn vị phát hành nào.

Dự án lưu dữ kiện kết quả và thông tin nguồn cho mục đích cá nhân, học tập và
nghiên cứu. Repo không sao chép logo của nguồn dữ liệu, giao diện, bài viết hoặc
video của nguồn.
Người sử dụng cần tự kiểm tra điều khoản, quyền sở hữu trí tuệ và quy định pháp
luật áp dụng tại thời điểm sử dụng. Nội dung trong repo không phải tư vấn pháp lý.

Website sử dụng biểu tượng
[Crystal Ball](https://www.flaticon.com/free-icon-font/crystal-ball_8034121)
từ UIcons by Flaticon và đổi màu bằng CSS. Biểu tượng tuân theo điều kiện ghi
nguồn của Flaticon.

Xổ số là hoạt động có rủi ro tài chính và dành cho người đủ điều kiện theo pháp
luật. Dữ liệu lịch sử không bảo đảm khả năng dự đoán hoặc trúng thưởng. Không nên
dùng repo làm cơ sở để vay tiền, tăng mức cược hoặc xem kết quả mô hình là lời
khuyên tài chính.

## Giấy phép

Mã nguồn được phát hành theo giấy phép MIT. Dữ liệu gốc vẫn chịu các quyền và
điều kiện của nguồn tương ứng.
