# Định hướng nghiên cứu

## Câu hỏi ban đầu

Dự án xuất phát từ nghi ngờ rằng một hệ quay cơ học, dù được thiết kế và kiểm soát
tốt, vẫn là một hệ vật lý. Khối lượng bi, đường kính, độ mòn, bề mặt in số, luồng
khí, nhiệt độ, độ rung và tình trạng máy có thể tạo ra sai lệch rất nhỏ khác 0.

Đây là giả thuyết cá nhân, không phải cáo buộc và chưa phải kết luận khoa học.
Sai lệch có thể nhỏ đến mức không thể nhận diện với số mẫu hiện có. Hệ thống cũng
có thể được bảo trì, thay máy, thay bộ bi hoặc thay quy trình, làm sai lệch không
ổn định theo thời gian.

Với trò chơi điện tử dùng RNG, giả thuyết vật lý về bi không phù hợp. Nhóm này cần
kiểm định theo hướng chuỗi giả ngẫu nhiên, thay đổi phần mềm, thay đổi cấu hình và
chất lượng công bố dữ liệu.

## Ngẫu nhiên và tính tất định

Một hệ cơ học có thể tất định ở cấp vật lý nhưng vẫn không thể dự đoán trong thực
tế vì điều kiện ban đầu không đo đủ chính xác và động lực học nhạy với nhiễu.
Việc "không ngẫu nhiên tuyệt đối" không tự động tạo ra lợi thế dự báo có thể dùng.

Muốn kết luận có thiên lệch cần chỉ ra

- hiệu ứng lớn hơn sai số lấy mẫu
- hiệu ứng ổn định ngoài mẫu
- hiệu ứng còn tồn tại sau hiệu chỉnh nhiều kiểm định
- kết quả không do thay đổi thiết bị hoặc quy trình
- dữ liệu không bị thiếu có hệ thống
- phương pháp được xác định trước khi xem kết quả cuối

## Bộ số có vẻ đẹp

Trong mô hình đồng đều, mỗi tổ hợp cụ thể hợp lệ có cùng xác suất. Ví dụ một dãy
liên tiếp cụ thể không ít khả năng hơn một tổ hợp cụ thể trông lộn xộn.

Điểm dễ gây nhầm là "các dãy có quy luật" là một lớp được con người định nghĩa,
còn "các dãy trông ngẫu nhiên" thường là một lớp lớn hơn rất nhiều. So sánh một
dãy cụ thể với cả một lớp tổ hợp không phải so sánh ngang hàng.

Mẫu số người chơi chọn có thể ảnh hưởng số người phải chia giải nếu trúng. Nó
không làm thay đổi xác suất hệ thống quay ra tổ hợp đó.

## Kế hoạch kiểm định

### Kiểm tra từng số

- tần suất và khoảng tin cậy
- kiểm định chi bình phương
- độ lệch chuẩn hóa
- hiệu chỉnh Benjamini-Hochberg hoặc Bonferroni
- phân tích theo cửa sổ thời gian

### Kiểm tra phụ thuộc

- tự tương quan theo lag
- khoảng cách giữa hai lần xuất hiện
- runs test
- mutual information
- hoán vị ngẫu nhiên để xây phân phối chuẩn thực nghiệm

### Kiểm tra cấu trúc tổ hợp

- tổng, độ trải và khoảng cách giữa số
- chẵn lẻ, thấp cao
- số liên tiếp
- entropy của biểu diễn
- tần suất cặp và bộ ba
- so sánh với mô phỏng đúng luật chơi

### Kiểm tra thay đổi chế độ

- change point theo thời gian
- so sánh trước và sau thay đổi quy trình
- mô hình phân cấp theo năm hoặc thiết bị nếu có metadata
- loại riêng các kỳ không được xác nhận

### Đánh giá dự báo

- chia dữ liệu theo thời gian, không xáo ngẫu nhiên
- khóa mô hình trước giai đoạn kiểm tra
- so sánh với baseline đồng đều
- báo cáo log loss, calibration và khoảng tin cậy
- không chọn mô hình bằng kết quả test cuối
- công bố cả kết quả âm

## Kịch bản kết quả đồng đều

Nếu không phát hiện sai lệch có ý nghĩa, đó không phải kịch bản tồi. Nó là bằng
chứng rằng trong giới hạn dữ liệu và công suất kiểm định, mô hình đồng đều chưa bị
bác bỏ. Kết quả âm vẫn hữu ích vì nó định lượng mức sai lệch tối đa mà dữ liệu có
thể phát hiện.

## Kết luận hiện tại

Các backtest đang công bố chưa cho thấy chiến lược nào vượt cách chọn ngẫu nhiên
một cách đáng tin cậy. Do đó dự án hiện không có bằng chứng để ưu tiên một bộ số
hoặc khuyên dùng một chiến lược chọn số.

Kết luận này không phủ nhận khả năng một hệ vật lý có sai lệch rất nhỏ. Nó chỉ nói
rằng sai lệch, nếu có, chưa tạo thành lợi thế dự báo ổn định trong dữ liệu hiện có.
Dataset cũng chưa có mã máy, mã bộ bi, bảo trì và điều kiện môi trường để quy một
sai lệch quan sát được cho nguyên nhân cơ học.

Đây là quan điểm hiện tại dựa trên phương pháp đã công bố. Nó phải được sửa nếu
chuỗi dự đoán lưu trước và dữ liệu tương lai cung cấp bằng chứng tốt hơn.

## Giới hạn sử dụng

Phân tích hồi cứu dễ tạo mẫu giả nếu thử đủ nhiều đặc trưng. Dự báo xổ số có không
gian kết quả lớn và tín hiệu nếu tồn tại có thể cực nhỏ. Mọi mô hình trong repo là
thí nghiệm nghiên cứu, không phải hệ thống bảo đảm trúng thưởng hay lời khuyên tài
chính.
