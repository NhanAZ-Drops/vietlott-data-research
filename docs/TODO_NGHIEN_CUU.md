# Kế hoạch nâng cấp nghiên cứu

File này là danh sách công việc dài hạn cho dự án. Mỗi phiên làm việc có thể nhận
một hoặc vài mã công việc, hoàn thành chúng, bổ sung bằng chứng và đổi `[ ]` thành
`[x]`.

Kế hoạch được lập từ `analysis-export.json` sinh ngày 15/06/2026.

- SHA-256 của file phân tích
  `7dead8e9330a92bb577de0bcdfaeba27e25b8236f03f149f05515210c0e376e5`
- Snapshot có 379.518 dòng kỳ quay
- Có 379.457 dòng đã xác nhận và 61 dòng chưa xác nhận
- Có 72 phép kiểm định, trong đó 18 phép mang nhãn theo dõi
- Có 16 so sánh backtest và 0 so sánh thắng sau hiệu chỉnh
- Có 73 dự đoán đã đối chiếu trên 19 kỳ quay thực tế
- Có 1 dự đoán đúng toàn bộ, 0 gần đúng và 72 sai

## Cách sử dụng checklist

Trạng thái được dùng trong file

- `[ ]` chưa bắt đầu
- `[~]` đang thực hiện
- `[x]` hoàn thành và đã có bằng chứng
- `[-]` không thực hiện, phải ghi rõ lý do

Một công việc chỉ được tick hoàn thành khi đáp ứng đủ

- mã nguồn hoặc dữ liệu đầu ra đã được lưu trong repo
- có unit test, integration test hoặc phép đối chiếu tái lập phù hợp
- tài liệu phương pháp đã được cập nhật
- website và `analysis-export.json` được cập nhật nếu công việc làm thay đổi kết quả
- không làm hỏng dữ liệu lịch sử, sổ dự đoán hoặc workflow tự động
- CI đã chạy thành công

Khi hoàn thành một công việc, thêm một dòng ngay dưới công việc đó theo mẫu

```text
Hoàn thành ngày DD/MM/YYYY trong commit <sha>. Bằng chứng <đường dẫn>.
```

Không sửa số liệu mốc ở đầu file. Nếu có snapshot mới, thêm một mục nhật ký ở cuối
file để giữ lại dấu vết thay đổi.

## Thứ tự ưu tiên

| Mức | Ý nghĩa |
| --- | --- |
| P0 | Chất lượng dữ liệu và khả năng tái lập. Phải làm trước kết luận mới |
| P1 | Tính đúng đắn của kiểm định, backtest và dự đoán |
| P2 | Mở rộng phân tích, website và tự động hóa |
| P3 | Nghiên cứu thử nghiệm, chỉ làm khi P0 và P1 đủ ổn định |

## P0 - Khóa chất lượng dữ liệu

### P0.1 Định nghĩa lại trạng thái xác nhận

- [~] `DATA-001` Viết định nghĩa chính xác cho `confirmed`, `not_confirmed`,
  `unchecked` và các trạng thái nguồn khác.
  - Kết quả cần có
    - Một bảng trạng thái trong tài liệu thu thập dữ liệu
    - Điều kiện chuyển trạng thái có thể kiểm tra bằng code
    - Website không diễn giải `confirmed` thành "Vietlott đã xác nhận trực tiếp"
  - Tiêu chí hoàn thành
    - Có test cho mọi chuyển trạng thái hợp lệ và không hợp lệ
  - Đã triển khai cục bộ ngày 15/06/2026. Bằng chứng `src/vietlott_collector/provenance.py`,
    `tests/test_provenance.py` và `docs/THU_THAP_DU_LIEU.md`. Chờ CI.

- [~] `DATA-002` Tách rõ ba khái niệm "hợp lệ về cấu trúc", "đã đối chiếu nguồn"
  và "đến trực tiếp từ nguồn chính thức".
  - Kết quả cần có
    - Các trường hoặc chỉ số riêng trong metadata
    - Báo cáo tỷ lệ cho từng sản phẩm
  - Đã triển khai cục bộ ngày 15/06/2026 trong `datasets/metadata/quality-report.json`
    và `site/data/dataset-quality.json`. Chờ CI.

### P0.2 Đối chiếu đa nguồn

- [~] `DATA-003` Xây dựng bảng đối chiếu cùng kỳ giữa các nguồn cho Keno.
  - Lý do
    - Chỉ 15 trên 284.682 kỳ Keno trong snapshot mang nhãn nguồn chính thức
  - Kết quả cần có
    - Số kỳ khớp hoàn toàn
    - Số kỳ chỉ có một nguồn
    - Số kỳ xung đột
    - Danh sách xung đột có nguồn và thời điểm thu thập
  - Tiêu chí hoàn thành
    - Có thể tái chạy bằng một lệnh
    - Xung đột không bị tự động ghi đè
  - Đã có phân loại provenance và cơ chế giữ `source_history`. Chưa thể tính xung đột
    đầy đủ vì nhiều dòng lịch sử cũ không giữ toàn bộ quan sát nguồn.

- [~] `DATA-004` Xây dựng bảng đối chiếu cùng kỳ giữa các nguồn cho Bingo18.
  - Lý do
    - 958 trên 88.639 kỳ mang nhãn nguồn chính thức
    - 11.876 kỳ mang nhãn nguồn không rõ trong snapshot
  - Tiêu chí hoàn thành
    - Không còn nguồn `unknown` nếu có thể truy ngược
    - Các dòng chưa truy ngược được phải có lý do rõ ràng
  - Báo cáo hiện ghi rõ 11.876 dòng chưa truy ngược. Chưa được phép đổi chúng thành
    nguồn chính thức chỉ vì URL lịch sử có tên miền Vietlott.

- [~] `DATA-005` Tạo báo cáo `source-agreement` cho cả tám sản phẩm.
  - Chỉ số tối thiểu
    - độ phủ theo nguồn
    - tỷ lệ đồng thuận
    - tỷ lệ xung đột
    - tỷ lệ chỉ có một nguồn
    - tuổi của lần đối chiếu gần nhất
  - Đã có độ phủ nguồn, số dòng đối chiếu, nguồn đơn và trạng thái chưa rõ.
    Tuổi lần đối chiếu và tỷ lệ xung đột lịch sử còn thiếu vì raw observation cũ chưa đầy đủ.

### P0.3 Kiểm tra lịch sử thô

- [~] `DATA-006` Tạo lệnh kiểm tra toàn bộ dữ liệu kỳ quay thô.
  - Phải kiểm tra
    - trùng khóa `(product, draw_id)`
    - ngày hoặc mã kỳ đi lùi bất thường
    - khoảng trống trong chuỗi mã kỳ
    - kết quả ngoài miền giá trị
    - sai số lượng phần tử
    - số lặp trái luật
    - bản ghi không có nguồn
    - bản ghi nguồn phụ chưa được đối chiếu
  - Đã triển khai lệnh `vietlott-repository-data audit --source-dir datasets`.
    Báo cáo hiện không phát hiện khóa trùng, JSON lỗi hoặc sai miền cấu trúc. Chờ CI.

- [~] `DATA-007` Phân loại khoảng trống mã kỳ.
  - Nhóm cần phân biệt
    - kỳ không phát hành
    - kỳ bị hủy
    - kỳ bị thiếu dữ liệu
    - mã không liên tục do quy tắc sản phẩm
    - chưa xác định
  - Không được tự suy ra kỳ bị thiếu chỉ từ việc mã không liên tục
  - Đã phân loại `known_not_issued`, `mixed` và `unresolved`. Còn 48 mã Keno và
    162 mã Bingo18 chưa có đủ bằng chứng để kết luận.

- [~] `DATA-008` Tạo manifest tái lập cho từng snapshot.
  - Manifest tối thiểu gồm
    - hash từng tệp dữ liệu
    - số dòng
    - ngày đầu và cuối
    - phiên bản parser
    - phiên bản phương pháp
    - commit tạo snapshot
  - Đã tạo `datasets/metadata/snapshot-manifest.json` với SHA-256, số dòng,
    phiên bản parser, phiên bản phương pháp và commit hiện hành. Chờ CI.

### P0.4 Hoàn thiện dữ liệu giải thưởng

- [~] `DATA-009` Điều tra vì sao Keno chỉ có dữ liệu giải thưởng cho 30 kỳ.
  - Đã xác định lịch sử khôi phục chỉ có kết quả và quy tắc giải tĩnh. Bảng giải theo kỳ
    chỉ được lấy từ 30 trang chi tiết gần đây. Ghi tại `docs/CHAT_LUONG_DU_LIEU.md`.
- [~] `DATA-010` Điều tra vì sao Bingo18 chỉ có dữ liệu giải thưởng cho 30 kỳ.
  - Nguyên nhân giống Keno. Ghi tại `docs/CHAT_LUONG_DU_LIEU.md`.
- [~] `DATA-011` Hiển thị riêng "độ phủ kết quả" và "độ phủ giải thưởng".
  - Không hiển thị 100% nếu chỉ kết quả quay đầy đủ nhưng giải thưởng chưa đầy đủ
  - Website hiện tách hai thẻ và trang dữ liệu có bảng cho đủ tám sản phẩm. Chờ CI.

### P0.5 Kiểm tra gói xuất phân tích

- [~] `EXPORT-001` Thêm JSON Schema cho `analysis-export.json`.
  - Đã tạo `site/data/analysis-export.schema.json` theo JSON Schema 2020-12.
- [~] `EXPORT-002` Thêm test đối chiếu mọi tổng số giữa manifest, dataset summary
  và báo cáo sản phẩm.
  - Đã thêm kiểm tra schema, tổng số snapshot, báo cáo chất lượng và báo cáo sản phẩm
    trong `tests/test_static_site.py`.
- [~] `EXPORT-003` Giải thích rõ `pending_count = 58` trong khi `latest` chỉ nhúng
  28 dự đoán của 7 sản phẩm.
  - Nếu đây là chủ ý tóm tắt, thêm trường `embedded_pending_count`
  - Nếu không phải chủ ý, sửa lỗi xuất dữ liệu
  - Đã thêm `embedded_pending_count`, `pending_by_product` và ghi chú phạm vi nhúng.
- [~] `EXPORT-004` Cho phép xuất gói đầy đủ gồm dữ liệu thô hoặc danh mục tệp thô
  có hash để phần mềm khác tái tính kết quả.
  - Đã thêm `raw_data_catalog` gồm đường dẫn, số byte, số dòng và SHA-256.
- [~] `EXPORT-005` Thêm phiên bản cho từng nhóm phương pháp thay vì chỉ có một
  `methodology_version` chung.
  - Đã thêm `methodology_versions` riêng cho chất lượng dữ liệu, thống kê mô tả,
    fairness audit, backtest, sổ dự đoán và khí tượng.

## P1 - Củng cố kiểm định công bằng

### P1.1 Tách ý nghĩa thống kê và ý nghĩa thực dụng

- [~] `AUDIT-001` Sửa mô hình trạng thái để không gộp mọi lý do vào `watch`.
  - Trạng thái đề xuất
    - `statistically_notable`
    - `practically_large`
    - `both`
    - `pass`
    - `skipped`
  - Website phải giải thích p, q, độ lớn hiệu ứng và ngưỡng thực dụng riêng
  - Đã triển khai suite 2.0.0 với `statistically_notable`, `practically_large`,
    `both`, `pass` và `skipped`. Chờ tái sinh artifact và CI.

- [~] `AUDIT-002` Rà soát ngưỡng độ lớn hiệu ứng của từng phép kiểm.
  - Mỗi ngưỡng phải có
    - tài liệu tham khảo hoặc lập luận mô phỏng
    - đơn vị
    - phạm vi áp dụng
    - phân tích độ nhạy
  - Đã triển khai cục bộ ngày 15/06/2026. Bằng chứng `src/vietlott_analytics/fairness.py`,
    `docs/AUDIT_EFFECT_THRESHOLDS.md`, `site/data/audit-summary.json`,
    `tests/test_fairness_audit.py`, `tests/test_documentation.py` và `tests/test_static_site.py`.
    Chờ CI.

- [x] `AUDIT-003` Công bố ma trận phụ thuộc giữa các phép kiểm.
  - Lý do
    - Chi-square và G-test thường trả lời câu hỏi gần giống nhau
    - Nhiều phép thử dùng chung dữ liệu và không độc lập
  - Xem xét hiệu chỉnh theo họ phép thử và toàn hệ thống
  - Hoàn thành ngày 15/06/2026 trong commit d21205769c1167cd4597bf52dfc4b4210da2994b.
    Bằng chứng `src/vietlott_analytics/fairness.py`,
    `docs/AUDIT_TEST_DEPENDENCIES.md`, `site/data/audit-summary.json`,
    `site/data/analysis-export.json`, `tests/test_fairness_audit.py`,
    `tests/test_documentation.py` và `tests/test_static_site.py`.

### P1.2 Tái kiểm tra tín hiệu Max 3D

- [~] `AUDIT-004` Khóa trước giao thức tái kiểm tra tín hiệu theo vị trí của Max 3D.
  - Mốc hiện tại
    - p = 0,00000058
    - q toàn cục = 0,00004118
    - độ lớn hiệu ứng = 0,034814
    - ngưỡng thực dụng hiện tại = 0,05
  - Giao thức phải khóa
    - kỳ bắt đầu kiểm tra tương lai
    - cỡ mẫu tối thiểu
    - phép kiểm chính
    - tiêu chí dừng
    - tiêu chí xác nhận và bác bỏ
  - Đã tạo `docs/protocols/MAX3D_POSITION_CONFIRMATION.md` với cutoff `01092`,
    300 kỳ tương lai, chi-square df 27, Bonferroni `0,025`, ngưỡng w `0,05` và
    quy tắc không kiểm định sớm. Chỉ có hiệu lực đăng ký trước sau khi push.

- [~] `AUDIT-005` Khóa trước giao thức tái kiểm tra tín hiệu theo vị trí của Max 3D Pro.
  - Mốc hiện tại
    - p = 0,00013377
    - q toàn cục = 0,00474883
    - độ lớn hiệu ứng = 0,037527
    - ngưỡng thực dụng hiện tại = 0,05
  - Dùng cùng giao thức, cutoff `00739` và 300 kỳ tương lai. Hai sản phẩm thuộc
    cùng một họ xác nhận. Chỉ có hiệu lực đăng ký trước sau khi push.

- [~] `AUDIT-006` Phân rã tín hiệu Max 3D theo vị trí và chữ số.
  - Báo cáo cần có
    - residual chuẩn hóa của từng ô
    - khoảng tin cậy
    - đóng góp vào thống kê tổng
    - kiểm tra độ ổn định theo thời gian
  - Không được chọn ô nổi bật rồi tính lại p-value trên cùng dữ liệu
  - Fairness report hiện xuất toàn bộ residual chuẩn hóa, kỳ vọng, số quan sát và
    đóng góp chi-square của mọi ô. Website hiển thị bản đồ nhiệt nhưng không tính
    p-value mới cho từng ô. Khoảng tin cậy và độ ổn định tương lai còn chờ mẫu xác nhận.

- [x] `AUDIT-007` Phân rã theo hạng giải và loại kết quả nếu cấu trúc dữ liệu cho phép.
  - Hoàn thành ngày 16/06/2026 trong commit `7a849cf8d308a27cd4738c0661f697c1b8823149`.
  - `Observation` giữ thêm `tiered_outcomes` từ `result_json.tiers` và gắn `result_type`
    (`full_sequence`, `wildcard_prefix`, `unusable`) để Max 4D vẫn ghi nhận hàng X wildcard nhưng
    không đưa vào audit theo vị trí đầy đủ.
  - `digit_position_chi_square.parameters.tier_breakdown` phân rã residual theo hạng giải cho
    Max 3D, Max 3D Pro và Max 4D, chỉ là metadata giải thích và không tạo p-value mới.
  - Website hiển thị bảng phân rã hạng giải, tài liệu hóa trong `docs/AUDIT_TIER_BREAKDOWN.md`, và
    đã kiểm chứng bằng `ruff`, toàn bộ `pytest`, `vietlott-repository-data validate` cùng report mới.
- [x] `AUDIT-008` Kiểm tra tín hiệu theo các giai đoạn thời gian không chồng lấn.
  - Hoàn thành ngày 18/06/2026.
  - `digit_position_chi_square.parameters.period_breakdown` chia lịch sử chuỗi chữ số đã xác nhận
    thành 3 giai đoạn liên tiếp, không chồng lấn, mỗi giai đoạn tối thiểu 30 kỳ.
  - Mỗi giai đoạn công bố biên kỳ, số outcome, đóng góp chi-square, độ lớn hiệu ứng,
    residual lớn nhất và `top_residuals`, nhưng `no_new_p_values = true` để không biến phần
    giải thích thành phép kiểm hậu nghiệm.
  - Website hiển thị bảng giai đoạn trong phần residual vị trí, tài liệu hóa trong
    `docs/AUDIT_PERIOD_BREAKDOWN.md`, và khóa bằng unit test cùng static-site test.
- [x] `AUDIT-009` Kiểm tra tín hiệu riêng theo nguồn để loại trừ lỗi parser hoặc mirror.
  - Hoàn thành ngày 18/06/2026.
  - `Observation` giữ metadata nguồn (`source_host`, `data_source`, `source_origin`,
    `source_verification`) khi nạp `datasets/draws`.
  - `digit_position_chi_square.parameters.source_breakdown` phân rã residual theo nguồn dữ liệu,
    đánh dấu nguồn đủ mẫu và nguồn quá nhỏ, ghi `top_residuals` nhưng không tạo p-value mới.
  - Website hiển thị bảng nguồn trong phần residual vị trí, tài liệu hóa trong
    `docs/AUDIT_SOURCE_BREAKDOWN.md`, và khóa bằng unit test cùng static-site test.
- [x] `AUDIT-010` Thực hiện phân tích công suất và hiệu ứng nhỏ nhất có thể phát hiện.
  - Hoàn thành ngày 18/06/2026.
  - Mỗi test active trong fairness audit có `power_analysis`, gồm mẫu hiệu dụng,
    công suất quan sát xấp xỉ, MDE tại 80% và 90%, cùng số mẫu cần để phát hiện ngưỡng
    thực dụng đã khóa trước.
  - Audit cấp sản phẩm và toàn hệ thống có `power_summary`, website hiển thị `MDE 80%`
    và `Công suất xấp xỉ` trong chi tiết kiểm định.
  - Tài liệu hóa trong `docs/AUDIT_POWER_ANALYSIS.md`; khóa bằng unit test, documentation
    test và static-site test. Các thang cực trị như max gap được đánh dấu `unsupported_scale`
    thay vì dùng sai công thức chuẩn.

### P1.3 Phép kiểm bền vững hơn

- [x] `AUDIT-011` Bổ sung permutation test bảo toàn cấu trúc từng kỳ.
  - Hoàn thành ngày 18/06/2026.
  - Các phép kiểm thứ tự `runs`, `lag1_autocorrelation` và `split_half_change` có
    `parameters.permutation_check` với 499 lần hoán vị seed cố định, tráo thứ tự
    nguyên đơn vị quan sát thay vì phá cấu trúc trong từng kỳ hoặc từng kết quả.
  - Với chuỗi quá dài, permutation dùng lấy mẫu đều quyết định sẵn tối đa 5.000 đơn vị
    và công bố `full_value_count`, `permutation_value_count`, `sampling_method`.
  - Website hiển thị `Permutation p` trong chi tiết kiểm định; tài liệu hóa trong
    `docs/AUDIT_PERMUTATION_CHECKS.md` và khóa bằng unit test, documentation test,
    static-site test.
- [x] `AUDIT-012` Bổ sung block bootstrap theo thời gian cho chỉ số phụ thuộc chuỗi.
  - Hoàn thành ngày 18/06/2026.
  - Các phép kiểm thứ tự `runs`, `lag1_autocorrelation` và `split_half_change` có
    `parameters.block_bootstrap_check` với 199 lần moving-block bootstrap seed cố định.
  - Bootstrap lấy lại các block liên tiếp để giữ nhịp thời gian cục bộ, công bố
    `block_length`, khoảng 95% và trạng thái `no_multiple_testing_decision = true`.
  - Với chuỗi quá dài, bootstrap dùng lấy mẫu đều quyết định sẵn tối đa 2.500 đơn vị.
  - Website hiển thị `Block bootstrap 95%`; tài liệu hóa trong
    `docs/AUDIT_BLOCK_BOOTSTRAP.md` và khóa bằng unit test, documentation test,
    static-site test.
- [x] `AUDIT-013` Thay split-half duy nhất bằng change-point có nhiều điểm ứng viên.
  - Hoàn thành ngày 18/06/2026.
  - Hai test id `number_sum_split_half_change` và `digit_sum_split_half_change` được giữ để
    ổn định schema, nhưng thuật toán chuyển sang `pre_registered_candidate_scan`.
  - Quét các điểm cắt đã khóa trước ở 20%, 30%, 40%, 50%, 60%, 70% và 80% lịch sử,
    chọn ứng viên có `max_abs_z_score` mạnh nhất.
  - `p_value` chính dùng `adjusted_p_value` theo Bonferroni trên số ứng viên; `raw_p_value`
    chỉ phục vụ giải thích và không dùng làm quyết định chưa hiệu chỉnh.
  - Website hiển thị `Change-point scan`; tài liệu hóa trong
    `docs/AUDIT_CHANGE_POINT_SCAN.md` và khóa bằng unit test, documentation test,
    static-site test.

- [x] `AUDIT-014` Triển khai phép kiểm đồng xuất hiện Keno có thể mở rộng.
  - Hoàn thành ngày 18/06/2026.
  - Thay ngưỡng skip theo số quan sát cặp bằng bộ đếm `dense_pair_index_vector`.
  - Keno hiện đếm đầy đủ `C(80, 2) = 3.160` cặp trên hơn 54 triệu quan sát cặp,
    không lấy mẫu tùy tiện và công bố `no_sampling = true`.
  - JSON có `pair_observations`, `observed_pair_observations`, `top_pairs` và
    tỷ lệ cặp cao nhất so với kỳ vọng.
  - Tài liệu hóa trong `docs/AUDIT_KENO_PAIR_COOCCURRENCE.md`; khóa bằng unit test,
    documentation test và static-site test.

- [x] `AUDIT-015` Thêm kiểm tra độ nhạy khi loại từng nguồn dữ liệu.
  - Hoàn thành ngày 18/06/2026.
  - `digit_position_chi_square.parameters.source_leave_one_out` loại từng nguồn
    dữ liệu rồi tính lại chi-square, `effect_size`, residual nổi bật và chênh lệch
    so với baseline toàn bộ dữ liệu.
  - Bảng dùng cùng provenance với `source_breakdown`, công bố `no_new_p_values = true`
    và không thay p-value, q-value hoặc trạng thái chính của kiểm định.
  - Website hiển thị panel "Độ nhạy loại nguồn"; tài liệu hóa trong
    `docs/AUDIT_SOURCE_SENSITIVITY.md` và khóa bằng unit test, documentation test,
    static-site test.
- [x] `AUDIT-016` Thêm kiểm tra độ nhạy khi loại các kỳ chưa xác nhận và vùng lịch sử
  có độ tin cậy thấp.
  - Hoàn thành ngày 18/06/2026.
  - `audit.reliability_sensitivity` xác nhận audit chính chỉ dùng kỳ `confirmed`,
    đếm riêng kỳ `not_confirmed` đã loại và chạy lại statistic/effect trên lát
    `source_verification` đáng tin cậy khi đủ mẫu.
  - Bảng công bố `no_new_p_values = true`, không tạo p-value, q-value hoặc trạng thái
    kiểm định mới; summary và `audit-log.jsonl` có trường tóm tắt để truy vết.
  - Website hiển thị panel "Độ nhạy dữ liệu tin cậy"; tài liệu hóa trong
    `docs/AUDIT_RELIABILITY_SENSITIVITY.md` và khóa bằng unit test, documentation
    test, static-site test.

## P1 - Củng cố backtest

### P1.4 Chuẩn hóa phạm vi chiến lược

- [~] `BACKTEST-001` Đưa `recent_frequency` vào backtest đầy đủ.
  - Hiện chiến lược có trong sổ dự đoán nhưng không có trong báo cáo backtest
  - Đã triển khai cục bộ ngày 15/06/2026. Báo cáo hiện có 24 phép so sánh cho ba
    chiến lược trên tám sản phẩm, có công thức, p thô, q toàn hệ thống và khoảng
    ước lượng 95%. Bằng chứng `src/vietlott_analytics/predictions.py`,
    `site/data/manifest.json` và `tests/test_prediction_ledger.py`. Chờ CI.

- [x] `BACKTEST-002` Đảm bảo mọi chiến lược được đánh giá trên đúng cùng tập kỳ đích.
  - Hoàn thành ngày 18/06/2026.
  - Mỗi báo cáo backtest có `target_scope` khóa danh sách kỳ mục tiêu bằng SHA-256;
    `model`, `recent_model`, `audit_model`, `baseline` và ba comparison đều phải
    dùng chung `target_scope_id` và `target_draw_count`.
  - `finalize_backtests` validate scope trước khi hiệu chỉnh Benjamini-Hochberg và
    `manifest.backtest_summary.target_scope_validation` công bố trạng thái toàn hệ
    thống.
  - Website hiển thị "Tập kỳ mục tiêu chung"; tài liệu hóa trong
    `docs/BACKTEST_TARGET_SCOPE.md` và khóa bằng unit test, documentation test,
    static-site test.
- [x] `BACKTEST-003` Công bố công thức điểm cho từng loại sản phẩm.
  - Không gộp điểm của tập số và chuỗi chữ số thành cùng một thước đo tổng
  - Hoàn thành ngày 18/06/2026.
  - Mỗi report backtest có `score_formulas` tách `number_set` với đơn vị
    `main_number_hits_per_draw` khỏi `digit_sequence` với đơn vị
    `best_position_matches_per_draw`.
  - JSON công bố `per_draw_score`, `comparison_difference`, baseline method,
    biến đầu vào và công thức của `balanced_signal`, `recent_frequency`,
    `audit_signal`; website đọc trực tiếp từ JSON này.
  - Tài liệu hóa trong `docs/BACKTEST_SCORE_FORMULAS.md` và khóa bằng unit test,
    documentation test, static-site test.

- [x] `BACKTEST-004` Thêm baseline xác suất cho cả điểm trùng một phần.
  - Baseline phải dùng phân bố chính xác khi có thể tính được
  - Không dùng một lần bốc ngẫu nhiên làm baseline
  - Hoàn thành ngày 18/06/2026.
  - `backtest.baseline.partial_match_baseline` công bố xác suất và số lượt kỳ vọng
    cho trùng một phần, gần đúng và không trùng gì trên đúng `target_scope` đã khóa.
  - Tập số dùng phân phối siêu bội exact của `main_number_hits`; chuỗi chữ số dùng
    enumeration exact của `best_position_matches` theo từng kỳ và chính sách nhiều
    outcome đã công bố.
  - Website hiển thị dòng "Baseline trùng một phần"; tài liệu hóa trong
    `docs/BACKTEST_SCORE_FORMULAS.md` và khóa bằng unit test, documentation test,
    static-site test.

### P1.5 Kiểm soát tối ưu quá mức và rò rỉ dữ liệu

- [ ] `BACKTEST-005` Thêm test tự động chứng minh mỗi dự đoán chỉ dùng dữ liệu trước kỳ đích.
- [ ] `BACKTEST-006` Tách giai đoạn chọn công thức và giai đoạn đánh giá cuối.
- [ ] `BACKTEST-007` Hiệu chỉnh nhiều phép thử trên mọi chiến lược, sản phẩm và biến thể
  tham số đã thử, không chỉ các mô hình cuối được công bố.
- [ ] `BACKTEST-008` Lưu lại cả thử nghiệm thất bại và cấu hình bị loại.
- [ ] `BACKTEST-009` Thêm kiểm tra độ nhạy theo độ dài cửa sổ 50, 200, 500 kỳ và
  các giá trị được đăng ký trước khác.

### P1.6 Ước lượng bất định đúng với chuỗi thời gian

- [ ] `BACKTEST-010` So sánh xấp xỉ chuẩn hiện tại với block bootstrap.
- [ ] `BACKTEST-011` Thêm khoảng tin cậy cho chênh lệch giữa hai chiến lược trên cùng kỳ.
- [ ] `BACKTEST-012` Thêm kiểm định paired permutation hoặc phương pháp tương đương.
- [ ] `BACKTEST-013` Báo cáo hiệu ứng tuyệt đối, hiệu ứng tương đối và ý nghĩa thực dụng.

## P1 - Chuẩn hóa sổ dự đoán

### P1.7 Mẫu số và baseline

- [~] `PRED-001` Hiển thị riêng số dòng dự đoán và số kỳ quay độc lập.
  - Mốc hiện tại là 73 dòng trên 19 kỳ
  - `outcome_summary` và từng `product_outcomes` hiện tách `evaluated_predictions`
    khỏi `evaluated_draws`. Website hiển thị cả hai số. Chờ CI.

- [ ] `PRED-002` Tính xác suất nền riêng cho mỗi sản phẩm và mỗi loại điểm.
- [ ] `PRED-003` Tính số lần đúng kỳ vọng và khoảng dự đoán dưới baseline.
- [ ] `PRED-004` Không cộng tỷ lệ đúng của các trò chơi có không gian kết quả khác nhau.
- [ ] `PRED-005` So sánh chiến lược với baseline theo từng kỳ bằng phép so sánh cặp.

### P1.8 Tính bất biến của sổ dự đoán

- [~] `PRED-006` Thêm hash nối chuỗi hoặc Merkle root cho ledger append-only.
  - Ledger phiên bản 1 hiện có `ledger_index`, `previous_event_hash` và
    `event_hash` cho 232 sự kiện. Hash gốc được xuất trong
    `site/data/predictions.json`. Chờ CI.
- [~] `PRED-007` Công bố hash ledger trước các kỳ quay theo lịch tự động.
  - Website công bố hash gốc đầy đủ. Workflow cập nhật sinh dự đoán cho kỳ kế tiếp,
    commit `predictions/ledger.jsonl` cùng `site/data` và triển khai Pages. Cần một
    lần chạy workflow thành công sau khi thay đổi này được push để hoàn tất.
- [~] `PRED-008` Thêm test phát hiện sửa, xóa hoặc chèn ngược sự kiện cũ.
  - Đã có test sửa nội dung lịch sử, sai chỉ mục, đứt hash trước và trộn sự kiện
    có niêm phong với sự kiện chưa niêm phong trong `tests/test_prediction_ledger.py`.
    Chờ CI.
- [~] `PRED-009` Ghi rõ timezone cho cutoff, thời điểm sinh và thời điểm công bố kết quả.
  - Dự đoán mới ghi `generated_at_timezone = UTC` và
    `dataset_cutoff_timezone = Asia/Ho_Chi_Minh`. Thời điểm quan sát kết quả dùng
    timestamp có offset. Chưa có thời điểm Vietlott công bố chính xác cho toàn lịch sử.
- [~] `PRED-010` Lưu phiên bản code, tham số và hash dataset cho mọi dự đoán.
  - Dự đoán mới ghi `model_version`, `code_version`, toàn bộ `parameters` và
    SHA-256 của toàn bộ lịch sử đã dùng. Test xác nhận fingerprint thay đổi khi
    một quan sát cũ bị sửa. Chờ CI.

### P1.9 Quy tắc kết luận dự đoán

- [ ] `PRED-011` Đặt cỡ mẫu tối thiểu trước khi website dùng từ "tốt hơn baseline".
- [~] `PRED-012` Đặt tiêu chí cho "gần đúng" riêng từng sản phẩm.
  - Quy tắc hiện yêu cầu thiếu đúng một số hoặc một vị trí so với kết quả đầy đủ.
    Quy tắc được xuất trong JSON và hiển thị trên website. Cần đăng ký riêng các
    biến thể điểm đặc biệt trước khi chuyển sang `[x]`.
- [~] `PRED-013` Báo cáo số lần trùng một phần nhưng không gọi là gần đúng nếu chưa đạt
  quy tắc đã khóa.
  - `partial_matches`, `zero_matches` và phân bố số đơn vị trùng được báo cáo riêng;
    các lượt dưới ngưỡng vẫn mang trạng thái `wrong`. Chờ CI.
- [~] `PRED-014` Viết báo cáo riêng cho lần đúng Bingo18 `231`, kỳ `0171884`.
  - Phải nêu xác suất nền và số lần thử
  - Không trình bày như bằng chứng dự báo nếu chưa vượt baseline
  - Đã viết `docs/DU_DOAN_BINGO18_0171884.md`. Báo cáo nêu xác suất nền `1/216`,
    10 lượt thử của chiến lược, 32 lượt Bingo18 trên tám kỳ độc lập và cảnh báo
    phụ thuộc giữa các chiến lược. Chờ CI.

## P2 - Nâng cấp phân tích thời tiết

- [~] `WEATHER-001` Kiểm tra lại lịch sử địa điểm quay và ngày chuyển địa điểm.
  - Metadata ghi Lạc Trung đến 21/01/2025 và Tam Trinh từ 22/01/2025 theo thông báo
    Vietlott. Giai đoạn Lạc Trung trước thông báo vẫn là giả định liên tục cần thêm
    nguồn lịch sử.
- [~] `WEATHER-002` Lưu phiên bản nguồn ERA5-Land, tọa độ và ngày dữ liệu được tải.
  - `datasets/weather/metadata.json` hiện lưu model, endpoint, tài liệu nguồn, tọa
    độ từng địa điểm, khoảng ngày và `generated_at`. Chờ CI.
- [~] `WEATHER-003` Thêm kiểm tra dữ liệu thiếu, ngày trùng và thay đổi tọa độ.
  - Updater từ chối payload thiếu biến, dùng khóa ngày để không tạo dòng trùng và
    lưu cả tọa độ yêu cầu lẫn ô lưới thực tế. Chưa có báo cáo sai lệch tọa độ riêng.
- [~] `WEATHER-004` Công bố rõ thời tiết ngoài trời chỉ là biến đại diện.
  - Metadata, README, website và từng báo cáo sản phẩm đều ghi rõ đây không phải
    cảm biến trong phòng quay. Chờ CI.
- [~] `WEATHER-005` Thêm mô hình độ nhạy theo mùa, xu hướng năm và địa điểm.
  - Phép sàng lọc hiện trừ trung bình trong từng khối tháng-năm-địa điểm trước khi
    tính tương quan và hoán vị trong khối. Đây là kiểm soát phân tầng, chưa phải
    mô hình xu hướng liên tục.
- [ ] `WEATHER-006` Kiểm tra quan hệ phi tuyến bằng spline đã đăng ký trước.
- [ ] `WEATHER-007` Hiệu chỉnh nhiều phép thử cho toàn bộ sản phẩm và biến khí tượng.
- [~] `WEATHER-008` Không dùng ngôn ngữ nhân quả khi chưa có nhiệt độ phòng, mã máy,
  mã bộ bi và dữ liệu bảo trì.
  - Kết luận tự động chỉ dùng "liên hệ cần theo dõi" và nêu không chứng minh nguyên
    nhân trong phòng quay. Chờ CI và rà soát nội dung định kỳ.
- [~] `WEATHER-009` Lập danh sách dữ liệu vận hành cần xin hoặc tìm từ nguồn công khai.
  - nhiệt độ và độ ẩm trong phòng
  - thời điểm quay chính xác
  - mã máy quay
  - mã bộ bi
  - lần bảo trì và thay thiết bị
  - Danh sách đã xuất hiện trong metadata, trang phương pháp và tài liệu nghiên cứu.
    Chưa tìm được nguồn công khai đủ chi tiết để thu thập các trường này.

## P2 - Nâng cấp website

- [~] `WEB-001` Thêm bảng chất lượng nguồn cho từng sản phẩm.
  - Đã thêm bảng ở `site/du-lieu.html`, đọc từ `site/data/dataset-quality.json`.
- [~] `WEB-002` Hiển thị độ phủ giải thưởng tách khỏi độ phủ kết quả.
  - Đã thêm thẻ riêng trên báo cáo tương tác và cột riêng trong bảng chất lượng nguồn.
- [~] `WEB-003` Hiển thị p, q, độ lớn hiệu ứng và ngưỡng thực dụng cạnh nhau.
  - Đã hiển thị cạnh nhau trong từng dòng kiểm định và có hướng dẫn cách đọc.
- [~] `WEB-004` Thay nhãn `watch` chung bằng lý do cụ thể.
  - Đã tách nổi bật thống kê, độ lớn thực dụng và đạt cả hai điều kiện.
- [~] `WEB-005` Hiển thị 0/16 chiến lược thắng sau hiệu chỉnh và 2 tín hiệu thắng thô
  mà không gây nhầm lẫn.
  - Sau khi thêm `recent_frequency`, website hiển thị đúng mốc mới là 0 trên 24
    phép so sánh thắng sau hiệu chỉnh và hai tín hiệu thô. Chờ CI.
- [~] `WEB-006` Thêm biểu đồ residual theo vị trí cho Max 3D và Max 3D Pro.
  - Đã thêm bản đồ nhiệt residual cho mọi sản phẩm chuỗi chữ số, gồm Max 3D và
    Max 3D Pro. Tooltip nêu quan sát, kỳ vọng và residual. QA cục bộ xác nhận Max 3D
    có đủ 3 hàng và 30 ô, không tràn ngang. Chờ CI.
- [~] `WEB-007` Hiển thị số kỳ độc lập trong báo cáo dự đoán.
  - Website hiện tách "Kỳ đã đối chiếu" và "Lượt dự đoán" theo từng sản phẩm,
    đồng thời nêu tổng số kỳ độc lập toàn hệ thống. Chờ CI.
- [ ] `WEB-008` Hiển thị baseline kỳ vọng cạnh kết quả dự đoán thực tế.
- [ ] `WEB-009` Thêm trang lịch sử kết luận để người đọc thấy kết luận thay đổi theo snapshot.
- [~] `WEB-010` Cho phép tải gói phân tích đầy đủ kèm schema, manifest và hash.
  - Trang dữ liệu hiện liên kết trực tiếp export, schema, báo cáo chất lượng và manifest.
- [~] `WEB-011` Thêm chú thích dễ hiểu cho p-value, q-value, hiệu ứng và khoảng tin cậy.
  - Đã có hướng dẫn ngay trong bảng kiểm định và trang phương pháp. Chờ CI.
- [ ] `WEB-012` Kiểm tra giao diện desktop, mobile, keyboard và screen reader.

## P2 - Tự động hóa và giám sát

- [~] `AUTO-001` Chạy kiểm toán dữ liệu đầy đủ theo lịch và sau thay đổi parser.
  - Workflow dùng chung hiện chạy `publish`, `validate`, `audit`, research report và
    test. CI cũng chạy lại khi mã nguồn hoặc parser thay đổi. Chờ CI.
- [~] `AUTO-002` Chạy fairness audit sau mỗi ngưỡng số kỳ riêng của sản phẩm.
  - Fairness audit hiện chạy sau mọi lần cập nhật, tức thường xuyên hơn ngưỡng kỳ.
    Chưa có cơ chế bỏ qua thông minh khi chưa đạt thêm số kỳ tối thiểu.
- [~] `AUTO-003` Lưu artifact gồm báo cáo trước và sau để phát hiện thay đổi bất thường.
  - Workflow dataset và khí tượng hiện lưu thư mục `before` và `after` trong artifact
    14 ngày, gồm quality, manifest, audit và prediction summary. Chờ CI.
- [~] `AUTO-004` Cảnh báo khi một nguồn không cập nhật quá thời gian cho phép.
  - `scripts/check_quality_regressions.py` dùng ngưỡng riêng cho sản phẩm quay dày
    và sản phẩm quay theo ngày cố định. Cảnh báo không tự suy thành mất kỳ. Chờ CI.
- [~] `AUTO-005` Cảnh báo khi tỷ lệ nguồn phụ hoặc nguồn không rõ tăng.
  - Bộ giám sát so tỷ lệ trước và sau, đồng thời cảnh báo mọi mức tăng của số dòng
    `unknown`. Báo cáo JSON được lưu trong artifact. Chờ CI.
- [~] `AUTO-006` Cảnh báo khi số kỳ chưa xác nhận tăng liên tục.
  - Hiện cảnh báo khi số kỳ chưa xác nhận tăng so với snapshot trước. Artifact
    trước và sau cho phép đọc chuỗi nhiều lần chạy; chưa tự gộp thành xu hướng dài.
- [~] `AUTO-007` Cảnh báo khi export, website và dataset có tổng số không khớp.
  - `tests/test_static_site.py` đối chiếu manifest, báo cáo sản phẩm, quality report,
    snapshot manifest và export. Workflow dừng nếu test thất bại. Chờ CI.
- [~] `AUTO-008` Chạy test ledger trước khi commit dự đoán mới.
  - `PredictionLedger.load` xác thực chuỗi hash trước khi thêm sự kiện. Workflow
    chạy pytest và sinh lại báo cáo trước khi commit. Chờ CI.
- [ ] `AUTO-009` Tạo issue tự động khi kiểm định đã khóa trước vượt ngưỡng.
- [~] `AUTO-010` Không tự động kết luận gian lận trong issue hoặc website.
  - Mẫu issue tín hiệu thống kê bắt buộc xác nhận không kết luận gian lận. Website
    tách tín hiệu thống kê, hiệu ứng thực dụng và nguyên nhân vận hành. Chờ CI.

## P2 - Tài liệu và khả năng tái lập

- [~] `DOC-001` Viết giao thức nghiên cứu đăng ký trước cho Max 3D.
  - Đã tạo `docs/protocols/MAX3D_POSITION_CONFIRMATION.md`. Giao thức ghi rõ chỉ
    có hiệu lực sau commit công khai để không nhận dữ liệu đã biết làm holdout.
- [~] `DOC-002` Viết data dictionary đầy đủ cho dataset và export.
  - Đã tạo `docs/DATA_DICTIONARY.md` cho kỳ quay, giải thưởng, khí tượng, provenance,
    ledger và toàn bộ artifact website. Chờ CI và rà soát khi schema thay đổi.
- [~] `DOC-003` Viết tài liệu giải thích từng thuật toán bằng ngôn ngữ phổ thông.
  - Trang phương pháp đã giải thích ba chiến lược backtest, baseline, p, q và độ
    lớn hiệu ứng. Các phép kiểm chuyên sâu còn cần rà soát ngôn ngữ.
- [~] `DOC-004` Thêm công thức, giả định và giới hạn cho từng phép kiểm.
  - Đã công bố công thức điểm, walk-forward, baseline chính xác, kiểm định ghép cặp,
    khoảng ước lượng và hiệu chỉnh Benjamini-Hochberg cho backtest. Chưa hoàn tất
    toàn bộ fairness suite.
- [~] `DOC-005` Ghi rõ phép kiểm nào bị hoãn và lý do.
  - JSON audit và giao diện hiện giữ trạng thái `skipped` cùng lý do. Cần bổ sung
    một bảng tài liệu tĩnh tổng hợp trước khi chuyển sang `[x]`.
- [~] `DOC-006` Tạo changelog phương pháp.
  - Đã tạo `docs/METHODOLOGY_CHANGELOG.md` với thay đổi fairness audit, backtest,
    ledger và data quality ngày 15/06/2026. Chờ CI.
- [~] `DOC-007` Tạo mẫu báo cáo kết quả âm.
  - Đã tạo `docs/templates/BAO_CAO_KET_QUA_AM.md`, yêu cầu lưu câu hỏi, snapshot,
    phép kiểm, hiệu ứng, công suất, giới hạn và artifact ngay cả khi không bác bỏ
    mô hình nền. Chờ CI.
- [~] `DOC-008` Tạo mẫu issue cho lỗi dữ liệu, lỗi nguồn và tín hiệu thống kê.
  - Đã tạo ba GitHub Issue Forms trong `.github/ISSUE_TEMPLATE`. Mẫu tín hiệu thống
    kê bắt buộc xác nhận không kết luận gian lận và vẫn lưu kết quả âm. Chờ CI.
- [~] `DOC-009` Thêm liên kết đến file checklist này trong README.
  - Đã thêm liên kết trong README. Chờ CI.

## P3 - Nghiên cứu mở rộng có kiểm soát

Chỉ bắt đầu các mục này sau khi các mục P0 và phần cốt lõi P1 đã hoàn thành.

- [ ] `RESEARCH-001` Phân tích entropy và mutual information bằng null model đúng luật chơi.
- [ ] `RESEARCH-002` Thử spectral analysis trên đặc trưng đã xác định trước.
- [ ] `RESEARCH-003` Thử Bayesian hierarchical model để ước lượng hiệu ứng nhỏ theo vị trí.
- [ ] `RESEARCH-004` Thử Bayesian posterior predictive checks.
- [ ] `RESEARCH-005` Xây dựng mô phỏng Monte Carlo dùng để kiểm tra công suất của toàn bộ audit.
- [ ] `RESEARCH-006` Nghiên cứu change-point theo thay đổi địa điểm hoặc quy trình đã công bố.
- [ ] `RESEARCH-007` Đánh giá mô hình máy học chỉ khi có baseline, holdout và tiêu chí dừng.
- [ ] `RESEARCH-008` Chỉ dùng deep learning khi chứng minh mô hình đơn giản không đủ và
  có cỡ mẫu hiệu dụng phù hợp.

## Những việc chưa nên làm

- [ ] `HOLD-001` Không chạy hàng loạt thuật toán rồi chỉ công bố kết quả có p nhỏ.
- [ ] `HOLD-002` Không dùng NIST, Dieharder hoặc TestU01 trước khi có ánh xạ sang bit
  được biện minh và kiểm tra.
- [ ] `HOLD-003` Không dùng LSTM, Transformer hoặc mô hình lớn để tạo vẻ phức tạp.
- [ ] `HOLD-004` Không suy nguyên nhân cơ học chỉ từ tần suất đầu ra.
- [ ] `HOLD-005` Không gọi một lần dự đoán đúng là lợi thế dự báo.
- [ ] `HOLD-006` Không dùng dữ liệu giải thưởng Keno và Bingo18 cho kết luận lịch sử
  trước khi hoàn thiện độ phủ.

Các mục `HOLD` được giữ ở `[ ]` như các quy tắc đang có hiệu lực. Chỉ đổi thành `[-]`
nếu dự án có bằng chứng và giao thức mới cho phép gỡ bỏ quy tắc.

## Mốc hoàn thành

### Mốc A - Dataset có thể kiểm toán

- [ ] Hoàn thành `DATA-001` đến `DATA-011`
- [ ] Hoàn thành `EXPORT-001` đến `EXPORT-005`
- [ ] Mọi sản phẩm có báo cáo nguồn và độ phủ giải thưởng

### Mốc B - Kết luận thống kê có thể bảo vệ

- [ ] Hoàn thành `AUDIT-001` đến `AUDIT-016`
- [ ] Tín hiệu Max 3D có giao thức tái kiểm tra độc lập
- [ ] Website phân biệt rõ ý nghĩa thống kê và ý nghĩa thực dụng

### Mốc C - Đánh giá dự đoán công bằng

- [ ] Hoàn thành `BACKTEST-001` đến `BACKTEST-013`
- [ ] Hoàn thành `PRED-001` đến `PRED-014`
- [ ] Mọi chiến lược được so với baseline trên cùng kỳ đích

### Mốc D - Công bố nghiên cứu tái lập

- [ ] Workflow tự động kiểm tra dữ liệu, phương pháp và ledger
- [ ] Website công bố lịch sử kết luận
- [ ] Gói phân tích có schema, manifest, hash và đường dẫn dữ liệu thô

## Nhật ký snapshot

### 15/06/2026

- Tạo kế hoạch từ `analysis-export.json`
- Kết luận gốc là chưa có chiến lược nào thắng baseline sau hiệu chỉnh
- Ghi nhận hai tín hiệu theo vị trí ở Max 3D và Max 3D Pro cần tái kiểm tra
- Ghi nhận giới hạn nguồn của Keno, Bingo18 và dữ liệu giải thưởng
- Thêm phân loại provenance, quality report, snapshot manifest và JSON Schema
- Nâng fairness audit lên phiên bản 2.0.0, tách ý nghĩa thống kê và thực dụng
- Mở rộng backtest lên ba chiến lược, 24 phép so sánh. Kết quả vẫn là 0 tín hiệu
  thắng sau hiệu chỉnh và hai tín hiệu thô thuộc Max 3D
- Niêm phong 232 sự kiện dự đoán bằng chuỗi SHA-256. Hash gốc snapshot là
  `386583fc6d9230bf7fd95d8f19af396ed2e5f537422b04bedbf9adb02a8fec7c`
- Chạy cục bộ thành công 75 test, Ruff và kiểm tra 379.518 dòng kỳ quay
