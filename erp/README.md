# ERP LiFeOOD (Odoo 19 Community)

Phần 1: chứng từ mua dịch vụ có phiên bản, điều chỉnh hàng loạt, phân quyền theo vai trò,
nhật ký toàn bộ thao tác không sửa được, báo cáo chi phí nhiều kỳ theo cây khoản mục.

## Bật app

1. Mở Docker Desktop, đợi hiện **Engine running**.
2. Bấm đúp `start-erp.bat` (hoặc `docker compose up -d`), mở http://localhost:8069

Tắt: `docker compose down` (dữ liệu giữ nguyên trong volume Docker).

## Tài khoản dùng thử (chỉ trên laptop, đổi trước khi mở link cho người khác)

| Tài khoản | Vai trò | Được làm |
|---|---|---|
| `ketoanvien` | Kế toán viên | Lập, sửa nháp, Cất; xem báo cáo; xuất dữ liệu |
| `ketoantruong` | Kế toán trưởng | Thêm: duyệt, Sửa sau khi Cất, điều chỉnh hàng loạt, hoàn tác lô, duyệt tham số pháp lý, xem nhật ký |
| `giamdoc` | Giám đốc | Xem mọi chứng từ, báo cáo, nhật ký; duyệt chứng từ vượt hạn mức; không sửa số liệu |
| `nhanvien` | Nhân viên | Không xem chứng từ kế toán |
| `admin` | Quản trị hệ thống | Toàn quyền: người dùng, vai trò, pháp nhân, danh mục, cấu hình, sao lưu, xóa chứng từ đã hủy; không sửa được nhật ký |

Vai trò R&D (gán ở Quản trị > Người dùng và vai trò): tách riêng, không thấy chứng từ, báo cáo, nhật ký kế toán.
ERP không quản lý khâu sản xuất (lệnh sản xuất, định mức, giá thành lệnh).

Mật khẩu 4 tài khoản mẫu: `lfood2026` (đổi trước khi giao cho người dùng thật).
Tài khoản quản trị đăng nhập bằng email của chủ hệ thống, mật khẩu do người dùng tự đặt (My Profile > Account Security).
Kiểm thử HTTP lấy tài khoản quản trị từ biến môi trường `LFOOD_ADMIN_LOGIN`, `LFOOD_ADMIN_PASSWORD`.

## Thời gian sử dụng tài sản: nhập theo năm hay theo tháng

Thẻ tài sản và công trình xây dựng cơ bản có ô **Thời gian sử dụng** kèm ô chọn **Năm** hoặc **Tháng**. Khung thời
gian của Thông tư 45 ghi theo năm, còn tài sản đã qua sử dụng thường tính theo tháng, chọn đơn vị nào cũng được.
App luôn quy về số tháng để tính khấu hao; đổi đơn vị chỉ đổi cách hiển thị chứ không đổi số tháng đã lưu.
Tài sản nhập từ trước vẫn giữ nguyên số tháng, chỉ hiển thị lại theo năm.

## Kiểm thử

Hai cơ sở dữ liệu: `lfood` là bản làm việc (dữ liệu mẫu công ty CP Nhựa Đại An, nạp bằng `tools/seed_daian.py`,
máy chủ web chỉ phục vụ bản này),
`lfood_test` là bản sạch dành cho bộ kiểm thử nghiệp vụ. Nâng cấp module thì chạy `-u` trên cả hai.

```
docker compose run --rm -T odoo odoo shell -c /etc/odoo/odoo.conf -d lfood_test --no-http < tests/smoke_test.py
docker compose run --rm -T odoo odoo shell -c /etc/odoo/odoo.conf -d lfood --no-http < tests/ui_crawl.py
docker compose run --rm -T odoo odoo shell -c /etc/odoo/odoo.conf -d lfood --no-http < tests/data_consistency.py
```

- `ui_crawl.py`: mở mọi menu dưới 5 vai trò như trình duyệt (tải giao diện, danh sách, bản ghi, biểu mẫu mới,
  từng bộ lọc, nhóm theo, pivot, biểu đồ, mẫu in). Nối sau phần thân `smoke_test.py` để duyệt trên dữ liệu kiểm thử.
- `data_consistency.py`: đối chiếu chéo trên dữ liệu thật: sổ cân, thẻ kho = sổ cái 152/155/156, công nợ 131 từng
  khách = hóa đơn chưa thu, tuổi nợ = 131, 334 = lương chưa chi, 3335 = thuế TNCN, tờ khai GTGT = hóa đơn,
  B01 cân, B02 = 4212, B03 = số dư tiền, không lập hóa đơn vượt đơn, không lô nào tồn âm.

## Nhập liệu kiểu Excel

Chứng từ > **Bảng nhập liệu**: một lưới giống sổ Nhật ký chung trong Excel, mỗi dòng là một vế Nợ - Có
(Ngày, Số chứng từ, Diễn giải, TK Nợ, TK Có, Số tiền, Đối tượng, Khoản mục). Nhiều dòng cùng Ngày và Số chứng từ
được gộp thành một bút toán. Ô Ngày, Số chứng từ, Diễn giải để trống thì lấy của dòng trên, giống kéo ô trong Excel.
Bấm **Kiểm tra** để soát cả bảng, lỗi hiện ngay trên từng dòng; **Ghi sổ** ghi một lần cho cả bảng.

Cấu hình > **Ràng buộc nhập liệu** (kế toán trưởng): đặt luật theo nhóm tài khoản - bắt buộc đối tượng, khoản mục
chi phí, diễn giải, số chứng từ; hạn mức tiền mỗi dòng; cấm hạch toán tay vào tài khoản do phân hệ khác ghi (154…).

Nút **Xuất Excel** trên bảng tạo tệp .xlsx còn sống chứ không phải ảnh chụp số liệu:

- Tên tài khoản tra bằng `VLOOKUP` sang trang danh mục ẩn `DanhMuc`;
- Cột **Kiểm tra** là công thức soát đủ ràng buộc (thiếu ngày, thiếu số chứng từ, thiếu diễn giải, số tiền không
  dương, sai tài khoản, trùng TK Nợ với TK Có, thiếu đối tượng với tài khoản công nợ), ô nào sai thì tô đỏ;
- Dòng **Cộng** dùng `SUMIF`, `SUM` và một ô báo "Nợ bằng Có" hay "Lệch …";
- Ô nhập có danh sách chọn lấy từ danh mục tài khoản, đối tượng, khoản mục của chính công ty; ngày và số tiền có
  ràng buộc kiểu dữ liệu;
- Cột công thức bị khóa, trang tính được bảo vệ, chỉ gõ được vào ô trắng; chừa sẵn 50 dòng trống.

Gõ tiếp trong Excel rồi chọn tệp ở mục **Nạp lại từ Excel** để đưa ngược vào app: app đọc các cột giá trị nên không
phụ thuộc Excel đã tính công thức hay chưa, sai danh mục thì báo rõ từng dòng trước khi thay dữ liệu.

803 kiểm tra: số liệu MDV00433, chặn quyền từng vai trò, Sửa sau khi Cất, phân bổ tổng khớp tới đồng,
báo cáo không đổi sau Sửa và sau điều chỉnh hàng loạt, hoàn tác lô, khôi phục số gốc, nhật ký
ghi đích danh, không sửa được nhật ký kể cả bằng SQL, chuỗi mã băm toàn vẹn; quản trị: tạo, đổi vai trò,
ngừng, xóa người dùng, R&D bị chặn chứng từ, CRUD nhà cung cấp và pháp nhân, xóa chứng từ đã hủy,
đồng bộ và kiểm tra bản sao lưu. Bài test tự hoàn tác
dữ liệu sau khi chạy.

`tests/http_test.ps1`: đăng nhập, đăng nhập sai, xuất Excel, đăng xuất, màn hình quản trị, tải bản sao lưu
(admin được, kế toán trưởng bị từ chối và vào nhật ký).

## Module

| Module | Nội dung |
|---|---|
| `lfood_base` | Vai trò, 2 pháp nhân, hạn mức duyệt, menu, giao diện trắng xám |
| `lfood_audit` | Nhật ký mọi tạo, sửa, xóa trên toàn hệ thống; đăng nhập, đăng xuất, đăng nhập sai; xuất Excel/CSV; in báo cáo; trigger chặn UPDATE/DELETE/TRUNCATE; chuỗi SHA-256 |
| `lfood_admin` | Người dùng và vai trò, ma trận phân quyền, pháp nhân, nhà cung cấp, màn hình sao lưu (sao lưu ngay, kiểm tra SHA-256, tải về, xóa); tìm kiếm nhanh toàn hệ thống (chứng từ, hóa đơn, phiếu kho, đối tác, mặt hàng, mã vạch, lô, nhân viên, tài sản) theo quyền của người dùng |
| `lfood_benefit` | Ốm đau, chăm con ốm, dưỡng sức, khám thai, sảy thai, sinh con, nam nghỉ khi vợ sinh theo Luật Bảo hiểm xã hội 41/2024/QH15: số ngày tối đa theo năm đóng, ngày làm việc trừ lễ Tết, mức hưởng 75% hoặc 100% chia 24, trợ cấp một lần theo mức tham chiếu; ghi Nợ 3383 / Có 334; danh sách tăng, giảm, điều chỉnh mức đóng bảo hiểm hằng tháng (so phiếu lương tháng này với tháng trước), tệp CSV để lập mẫu D02-LT |
| `lfood_hr_records` | Phòng ban, chức danh; điều chuyển, điều chỉnh lương theo Điều 29 Bộ luật Lao động (báo trước 3 ngày làm việc, tối đa 60 ngày làm việc/năm nếu không có văn bản đồng ý, lương mới từ 85% và không dưới lương tối thiểu vùng, giữ lương cũ 30 ngày làm việc; lâu dài phải có phụ lục); xử lý kỷ luật (thời hiệu 6/12 tháng, có tổ chức đại diện, kéo dài nâng lương tối đa 6 tháng, sa thải theo Điều 125, Giám đốc quyết định); khen thưởng; báo cáo tình hình thay đổi lao động 6 tháng, cả năm (Nghị định 145/2020/NĐ-CP, Mẫu 01/PLI) có nhắc hạn 05/6, 05/12; sổ người phụ thuộc theo tháng hiệu lực (bảng lương đếm theo sổ, một người phụ thuộc không tính cho hai người nộp thuế); tai nạn lao động: tiền lương điều trị, bồi thường, trợ cấp theo tỷ lệ suy giảm (Luật An toàn, vệ sinh lao động 2015 Điều 38), bắt buộc khai báo tai nạn nặng; báo cáo tai nạn 6 tháng, năm (Nghị định 39/2016/NĐ-CP Điều 24) có nhắc hạn; huấn luyện an toàn có nhắc hạn chứng nhận; tuyển dụng: yêu cầu tuyển Giám đốc duyệt, ứng viên theo bước, phải có đồng ý xử lý dữ liệu cá nhân, nhận việc tạo hồ sơ nhân viên, tự xóa hồ sơ không trúng tuyển quá hạn lưu; đánh giá hiệu suất KPI theo kỳ (trọng số, mức đạt tối đa 120%, xếp loại A-D, thưởng theo hệ số, duyệt tạo quyết định khen thưởng vào bảng lương); đào tạo: khóa học, học viên, chứng chỉ có hạn và nhắc hạn |
| `lfood_archive` | Lưu trữ chứng từ điện tử: hồ sơ tệp gắn với chứng từ trên app, mã SHA-256 kiểm tra toàn vẹn, không thay tệp, không xóa và không rút ngắn thời hạn lưu trữ (10 năm chứng từ ghi sổ, 5 năm tài liệu khác, Nghị định 174/2016/NĐ-CP) |
| `lfood_importer` | Nhập dữ liệu ban đầu từ Excel hoặc CSV bất kỳ: đọc tiêu đề, tự đoán cột, sửa ánh xạ, kiểm tra trước (thiếu trường, sai tài khoản, kho, mặt hàng, số dư không cân) rồi mới nhập; đối tác, mặt hàng, số dư đầu kỳ tài khoản, tồn kho đầu kỳ (phiếu Tồn đầu kỳ), tài sản cố định; nhập lại không tạo trùng; chỉ Kế toán trưởng |
| `lfood_signature` | Chứng thư số: nhà cung cấp, số sê-ri, hiệu lực, người giữ token, nhắc hạn gia hạn; đánh dấu tài liệu đã ký số (chứng thư đã dùng, người ký, thời điểm ký, định dạng), chặn ghi thời điểm ký ngoài hiệu lực chứng thư. App không ký thay: việc ký làm trên phần mềm của nhà cung cấp |
| `lfood_security` | Đăng nhập an toàn: mã xác thực 2 lớp (auth_totp), độ dài mật khẩu tối thiểu, khóa tạm khi đăng nhập sai nhiều lần, tự đăng xuất khi không thao tác; màn hình cấu hình và danh sách người chưa bật mã 2 lớp; quên mật khẩu: liên kết đặt lại mật khẩu trên trang đăng nhập, gửi thư qua máy chủ Gmail (quản trị viên tự nhập mật khẩu ứng dụng trong Máy chủ thư đi), không cho người ngoài tự đăng ký |
| `lfood_quality` | Truy xuất nguồn gốc theo lô từ thẻ kho (nguồn cung cấp, khách hàng, luân chuyển, tồn theo kho, cả hai pháp nhân) theo Luật An toàn thực phẩm Điều 54 và Nghị định 46/2026/NĐ-CP; đợt thu hồi sản phẩm tự nguyện hoặc bắt buộc: cách ly lô, danh sách khách hàng, thông báo, phiếu nhập hàng thu hồi, tỷ lệ thu hồi, báo cáo kết quả; kiểm tra chất lượng khi nhập mua, nhập thành phẩm (mặt hàng đánh dấu cần kiểm tra: lô tự cách ly, phiếu theo bộ chỉ tiêu, Kế toán trưởng hoặc Giám đốc kết luận), hành động khắc phục có hạn và nhắc hạn; hàng trả lại nhập theo giá vốn đã xuất; hồ sơ công bố sản phẩm theo Nghị quyết 66.13/2026/NQ-CP và Nghị định 46/2026/NĐ-CP (phiếu kiểm nghiệm ISO/IEC 17025 trong 12 tháng, hợp quy tối đa 3 năm, hạn công bố lại 27/01/2027, 27/01/2028); kiểm nghiệm định kỳ, lưu mẫu; khám sức khỏe (Luật An toàn, vệ sinh lao động Điều 21), tập huấn an toàn thực phẩm cho người trực tiếp sản xuất; nhắc hạn; giám sát điểm kiểm soát tới hạn HACCP: giới hạn tới hạn, kết quả đo không sửa, không xóa, ngoài giới hạn tự cách ly lô và mở hành động khắc phục, xác nhận hồ sơ, nhắc khi quá một ngày làm việc chưa đo |
| `lfood_rnd` | Nghiên cứu phát triển: dự án sản phẩm mới, công thức theo phiên bản (tổng tỷ lệ 100%, chốt thì khóa, sửa bằng phiên bản mới), mẫu thử chấm cảm quan và chỉ tiêu kiểm nghiệm, Giám đốc duyệt công thức (bản cũ hết hiệu lực, ghi nhật ký), chuyển giao khi có công thức duyệt; chỉ nhóm R&D và Giám đốc truy cập, kế toán không xem được |
| `lfood_contract` | Hợp đồng mua khung (giá, sản lượng cam kết, thời hạn; đơn mua theo hợp đồng lấy giá hợp đồng, chặn giá cao hơn hoặc ngoài thời hạn); đánh giá nhà cung cấp (giao đúng hạn, tỷ lệ lô đạt kiểm tra chất lượng, điểm giá, dịch vụ theo trọng số; nhà cung cấp bị loại không đặt hàng được); hợp đồng nhà phân phối thưởng doanh số theo bậc, quyết toán bằng hóa đơn điều chỉnh giảm tách theo thuế suất (Nợ 521, 33311 / Có 131); chương trình trade marketing, trưng bày theo ngân sách, chặn chi vượt ngân sách hoặc ngoài thời gian |
| `lfood_ecommerce` | Sàn thương mại điện tử: gian hàng theo sàn, nhập đơn từ tệp CSV (mã đơn, SKU theo mã vạch hoặc mã hàng, trạng thái), lập hóa đơn nháp cho đơn hoàn thành, tồn khả dụng theo SKU (trừ lô cách ly, đơn chờ giao) xuất tệp cập nhật sàn, đối soát tiền sàn chuyển về (Nợ 112, Nợ phí sàn / Có 1311), báo đơn lệch tiền, đơn chưa có trong app, đơn chưa được thanh toán |
| `lfood_consolidation` | Hợp nhất quản trị hai pháp nhân: B02, B01 cộng hai bên, loại trừ công nợ nội bộ (cảnh báo khi hai bên lệch), doanh thu và giá vốn bán nội bộ, lãi chưa thực hiện trong tồn kho theo lô (số cuối kỳ vào B01, phần tăng trong kỳ vào giá vốn); đối chiếu từng lần bán nội bộ giữa hóa đơn bên bán và phiếu nhập bên mua; chỉ Kế toán trưởng, Giám đốc xem |
| `lfood_equipment` | Thiết bị: chu kỳ bảo trì, hạn bảo trì tự tính, phiếu bảo trì, sửa chữa, giờ dừng máy, chi phí; đội xe: hạn kiểm định, bảo hiểm, nhật ký nhiên liệu và tiêu hao lít/100 km so với định mức, bảo dưỡng theo km; chành xe theo vùng, cước/kg so với cước tham chiếu; nhắc hạn |
| `lfood_privacy` | Bảo vệ dữ liệu cá nhân (Luật 91/2025/QH15, Nghị định 356/2025/NĐ-CP): sổ căn cứ xử lý và sự đồng ý có bằng chứng, rút lại; yêu cầu của chủ thể dữ liệu có hạn phản hồi 2 ngày làm việc và hạn thực hiện theo loại, gia hạn một lần, nhắc hạn; sổ sự cố (72 giờ với dữ liệu vị trí, sinh trắc học; lưu 5 năm); nhật ký mở xem hồ sơ nhân sự, bảng lương; người phụ trách và tình trạng miễn trừ |
| `lfood_related` | Giao dịch liên kết theo Nghị định 255/2026/NĐ-CP: đánh dấu bên liên kết kèm căn cứ, bảng giao dịch với bên liên kết trong năm trên quyết toán TNDN, khống chế chi phí lãi vay thuần 30% (lợi nhuận thuần + lãi vay thuần + khấu hao), chuyển phần vượt tối đa 5 năm, tự đưa lãi vay không được trừ vào điều chỉnh; lãi tiền gửi lấy từ phiếu thu đánh dấu lãi (không lẫn chênh lệch tỷ giá); đánh giá miễn kê khai, miễn lập hồ sơ xác định giá và bản nháp số liệu hồ sơ |
| `lfood_loan` | Hợp đồng vay: giải ngân Nợ 112 / Có 3411, trích lãi theo dư nợ thực tế từng ngày Nợ 635 / Có 335 (tách phần lãi vượt 20%/năm của khoản vay ngoài tổ chức tín dụng, không được trừ theo Nghị định 320/2025/NĐ-CP), phiếu trả gốc, trả lãi có kiểm tra, tự tất toán; lịch trả gốc đều hoặc sửa tay; B01 tách phần gốc đến hạn trong 12 tháng vào vay ngắn hạn, phần còn lại dài hạn; nhắc kỳ trả gốc |
| `lfood_taxdue` | Lịch nghĩa vụ thuế tự sinh khi xác nhận tờ khai GTGT, ghi sổ tạm nộp và quyết toán TNDN (tự hủy khi hủy chứng từ gốc); phiếu nộp thuế gắn nghĩa vụ; tiền chậm nộp 0,03%/ngày từ ngày sau hạn đến ngày trước ngày nộp (Luật Quản lý thuế 108/2025/QH15, Nghị định 252/2026/NĐ-CP), ghi sổ Nợ 811 / Có 3339, phiếu nộp tiền chậm nộp |
| `lfood_trade` | Tờ khai nhập khẩu: trị giá theo tỷ giá tính thuế, thuế nhập khẩu, thuế GTGT hàng nhập khẩu (Nợ 1331 / Có 33312, khấu trừ khi có chứng từ nộp thuế), chi phí nhập khẩu phân bổ vào giá vốn, nhập kho qua 3388 có kiểm tra chất lượng, công nợ ngoại tệ; hồ sơ xuất khẩu thuế suất 0% kiểm tra đủ chứng từ theo Luật Thuế GTGT Điều 14 khoản 2; thuế nhà thầu nước ngoài: tỷ lệ TNDN theo Nghị định 320/2025 Điều 12, tỷ lệ GTGT theo Luật Thuế GTGT Điều 12 (tham số), hợp đồng giá chưa gồm thuế, ghi sổ và bảng kê khấu trừ |
| `lfood_advance` | Tạm ứng (TK 141, Thông tư 99/2025/TT-BTC): đề nghị có Kế toán trưởng hoặc Giám đốc duyệt, chặn tạm ứng mới khi còn khoản quá hạn (quy chế bật tắt theo pháp nhân), phiếu chi tạm ứng, bảng thanh toán theo chứng từ gốc, phần chi không hết lập phiếu thu hoặc trừ lương, chi quá lập phiếu chi bổ sung; hóa đơn trong bảng thanh toán lên bảng kê mua vào, kiểm ngưỡng tiền mặt |
| `lfood_bank` | Danh mục tài khoản ngân hàng, phiếu chuyển khoản gắn tài khoản (tự gắn khi công ty chỉ có một), sổ phụ nhập từ CSV, khớp tự động với sổ 112 (cùng số tiền, lệch tối đa 5 ngày, ưu tiên trùng tham chiếu), bảng đối chiếu số dư, lập phiếu cho phí và lãi ngân hàng, khoản treo chuyển sang kỳ sau |
| `lfood_intercompany` | Bán hàng giữa Nhà máy và Văn phòng (hai mã số thuế): một chứng từ tạo hóa đơn bán, xuất kho bên bán và phiếu nhập mua, thuế đầu vào, phải trả bên mua; giữ nguyên lô, hạn dùng; bắt ghi căn cứ giá giao dịch liên kết, cảnh báo giá dưới giá vốn. Pháp nhân không sản xuất ghi thành phẩm mua về vào TK 156 |
| `lfood_reminder` | Việc sắp đến hạn quét hằng ngày (tác vụ định kỳ): tờ khai thuế GTGT và tạm nộp thuế TNDN kỳ trước chưa xong, hợp đồng lao động sắp hết hạn, lô còn tồn sắp hết hạn dùng, hóa đơn quá hạn thu, tham số pháp lý sắp hết áp dụng; việc hết điều kiện tự đóng; số ngày nhắc trước đặt theo pháp nhân |
| `lfood_stock_control` | Cách ly lô (không xuất bán, xuất dùng; Kế toán trưởng hoặc Giám đốc giải phóng), biên bản hủy hàng hư hỏng, hết hạn đủ hồ sơ theo Thông tư 20/2026/TT-BTC (Giám đốc duyệt, kế toán xuất kho ghi Nợ 632, bồi thường Nợ 1388 / Có 632), tồn tối thiểu, tối đa và đề xuất lập yêu cầu mua |
| `lfood_promotion` | Chương trình khuyến mại theo Nghị định 81/2018/NĐ-CP (sửa bởi 128/2024 và 239/2026): tặng hàng kèm mua, giảm giá, tặng không kèm mua, hàng mẫu; chặn vượt hạn mức 50% và thông báo Sở Công Thương trễ; hàng tặng trên hóa đơn thành tiền 0 và xuất kho vào giá vốn; hàng mẫu, tặng không kèm mua ghi Nợ 6418 |
| `lfood_salesorder` | Kênh phân phối, bảng giá theo kênh và bậc số lượng, hạn mức công nợ khách hàng (vượt thì Kế toán trưởng hoặc Giám đốc duyệt), báo giá và đơn bán, lập hóa đơn từ phần chưa lập, giao hàng bỏ qua lô còn hạn ít hơn mức khách yêu cầu; nhãn hàng trên mặt hàng; báo cáo lãi gộp theo nhãn hàng, kênh, vùng, sản phẩm, khách hàng (doanh thu thuần theo hóa đơn, giá vốn theo phiếu kho); phân bổ chi phí chung sang khoản mục nhãn hàng, kênh, bộ phận theo tỷ lệ hoặc doanh thu (kết chuyển giữa khoản mục trên cùng tài khoản); cơ hội bán hàng theo giai đoạn (kanban), xác suất và doanh số có trọng số, thành công tạo khách hàng và báo giá, thất bại ghi lý do |
| `lfood_fx` | Ngoại tệ và số nguyên tệ trên từng dòng bút toán; đánh giá lại khoản mục tiền tệ có gốc ngoại tệ cuối kỳ theo tỷ giá mua bán chuyển khoản trung bình của ngân hàng, ghi chênh lệch theo từng tài khoản, đối tượng và ghi số thuần vào 515 hoặc 635 (Thông tư 99/2025/TT-BTC) |
| `lfood_hr` | Hợp đồng lao động (xác định thời hạn tối đa 36 tháng, thử việc 180/60/30/6 ngày, lương thử việc từ 85%), chấm công ngày có làm thêm và làm đêm (chặn vượt 50% giờ ngày, 40 giờ tháng, 200 giờ năm), đơn nghỉ và phép năm theo thâm niên; chấm dứt hợp đồng với trợ cấp thôi việc 1/2 tháng, mất việc 1 tháng (tối thiểu 2 tháng) mỗi năm, trừ thời gian đóng BHTN, làm tròn theo Nghị định 145/2020; bảng lương lấy ngày công và tiền làm thêm 150/200/300%, đêm +30%, làm thêm ban đêm +20% từ chấm công (Bộ luật Lao động 2019); ca làm việc (giờ làm, giờ làm đêm 22h-6h), lịch phân ca kiểm tra 8 giờ/ngày, 48 giờ/tuần, nghỉ 12 giờ khi chuyển ca, nghỉ hằng tuần (Bộ luật Lao động 2019 Điều 105, 106, 109, 111), tạo chấm công từ lịch ca |
| `lfood_payroll` | Nhân viên, khoản lương, bảng lương tháng; BHXH, BHYT, BHTN, KPCĐ (mức sàn lương tối thiểu vùng, trần 20 lần mức tham chiếu / lương tối thiểu vùng); thuế TNCN 5 bậc 5/10/20/30/35%; miễn thuế toàn bộ tiền lương làm thêm giờ, làm đêm và tiền lương những ngày không nghỉ phép từ kỳ tính thuế 2026 (Luật 109/2025, gắn theo tham số có ngày hiệu lực); ghi sổ, chi lương, hủy ghi sổ tự đảo; tính thử bảng lương với mức tham số chờ duyệt, so với mức đang áp dụng (không ghi vào bảng lương) |
| `lfood_pit` | Tạm ứng lương giữa kỳ (Nợ 334 / Có 111, 112), tự trừ vào phiếu lương tháng; khen thưởng có tiền tự vào bảng lương tháng khen thưởng, khoản lương tháng 13; chi trả thu nhập vãng lai: khấu trừ 10% từ 05 triệu đồng/lần (Nghị định 253/2026/NĐ-CP Điều 50, từ 01/7/2026; trước đó 02 triệu), theo yêu cầu cá nhân, cam kết thu nhập thấp có đính kèm, không cư trú 20% (Điều 64); quyết toán thuế TNCN năm: biểu lũy tiến năm, giảm trừ gia cảnh, so với số đã khấu trừ, kiểm tra điều kiện ủy quyền (Điều 51), bảng thu nhập vãng lai theo cá nhân, số liệu cho tờ khai 05/QTT-TNCN và chứng từ khấu trừ; báo cáo lao động, tiền lương, bảo hiểm, thuế TNCN theo 12 tháng |
| `lfood_budget` | Ngân sách năm trên cây khoản mục: sửa khoản cha chia xuống con theo tỷ trọng (giữ dòng khóa, khớp tới đồng), sửa con cộng lên cha, duyệt và lập phiên bản mới; báo cáo kế hoạch so với thực tế, cảnh báo vượt ngân sách khi Cất chứng từ |
| `lfood_purchase` | Yêu cầu mua (kiểm soát ngân sách theo khoản mục, duyệt theo vai trò), đơn mua hàng (vượt hạn mức phải Kế toán trưởng duyệt), nhận hàng tạo phiếu nhập kho theo đơn, đối chiếu 3 bên đơn mua – phiếu nhận – hóa đơn với dung sai khai báo ở Công ty; báo giá nhiều nhà cung cấp và so sánh (bắt buộc đủ số báo giá tối thiểu từ một mức tiền); trả lại hàng mua trừ vào số đã nhận; phân bổ chi phí mua hàng và giảm giá hàng mua vào giá gốc hàng tồn kho (VAS 02, TT99); bảng kê thu mua không có hóa đơn mẫu 02/TNDN theo TT 20/2026, tự đánh dấu khoản không được trừ khi trả tiền mặt từ 5 triệu/ngày/người bán |
| `lfood_accrual` | Chi phí trả trước TK 242 và chi phí phải trả, trích trước TK 335: lập lịch phân bổ theo tháng (kỳ đầu theo số ngày, kỳ cuối nhận phần lẻ), ghi sổ từng kỳ bằng một màn hình chạy chung, quyết toán khoản trích trước theo số thực tế (ghi tăng chi phí hoặc hoàn nhập); hợp đồng thuê tài sản (kho, xe): lịch thanh toán theo chu kỳ, kỳ trả trước tự lập chi phí trả trước 242 và phân bổ, ký quỹ 244, nhắc kỳ thanh toán và hạn hợp đồng |
| `lfood_provision` | Trích lập dự phòng theo Thông tư 48/2019/TT-BTC: nợ phải thu khó đòi lấy từng hóa đơn còn nợ, tuổi nợ 30%, 50%, 70%, 100% (mốc tháng và tỷ lệ là tham số pháp lý); giảm giá hàng tồn kho theo giá gốc so với giá trị thuần có thể thực hiện được; chỉ ghi chênh lệch so với số đã trích, Nợ 6426 / Có 2293 và Nợ 632 / Có 2294 |
| `lfood_cit` | Tạm nộp thuế TNDN theo quý và quyết toán năm: thuế suất 15%, 17%, 20% tự chọn theo tổng doanh thu năm liền kề trước (Luật 67/2025/QH15), chuyển lỗ liên tục không quá 5 năm, cảnh báo tạm nộp 4 quý thiếu so với tỷ lệ tối thiểu 80%, ghi sổ Nợ 82111 / Có 3334; bảng tính thuế in ra để nhập tờ khai 03/TNDN |
| `lfood_sale` | Ghi nhận hóa đơn bán ra đã phát hành trên hệ thống hóa đơn điện tử (NĐ 254/2026), hàng bán trả lại, giảm giá (521), thu tiền theo hóa đơn, tuổi nợ phải thu, phải trả; bảng kê bán ra lấy từ hóa đơn; hóa đơn điều chỉnh tăng, giảm và thay thế theo Thông tư 91/2026/TT-BTC Điều 10 (lý do, văn bản thỏa thuận với người mua là tổ chức, giữ hình thức đã chọn lần đầu, hóa đơn gốc Bị thay thế và đảo bút toán, số đã thu chuyển sang hóa đơn thay thế), ghi nhận thông báo sai sót 04/SS-HĐĐT; điều khoản thanh toán nhiều đợt (tỷ lệ, số ngày), gắn cho khách hàng, hóa đơn lấy hạn thanh toán và lịch thanh toán từng đợt |
| `lfood_stock` | Hàng hóa, kho, lô và hạn dùng (xuất FEFO), nhập mua có hóa đơn và thuế, xuất bán tự động từ hóa đơn, xuất dùng, chuyển kho, kiểm kê; giá xuất bình quân gia quyền từng lần phát sinh; chặn xuất âm, chặn ghi lùi ngày; kiểm kê theo đợt (chốt sổ sách theo lô, biên bản, Kế toán trưởng duyệt thì tự ghi phiếu thừa Có 3381 và thiếu Nợ 1381); nhập xuất tồn, hàng sắp hết hạn; mã vạch mặt hàng, quét mã vạch (máy quét USB) vào phiếu nhập, xuất và đợt kiểm kê (đếm lại từ 0), in tem lô Code128 dạng MÃ HÀNG/SỐ LÔ kèm hạn dùng; đơn vị quy đổi theo mặt hàng (thùng, lốc = bao nhiêu đơn vị gốc, có mã vạch riêng), nhập chứng từ theo đơn vị lớn, quét mã vạch thùng cộng đủ số đơn vị gốc |
| `lfood_vat` | Tờ khai 01/GTGT theo Thông tư 89/2026 (có [32b], [34a]), bảng kê mua vào kiểm tra điều kiện khấu trừ (hóa đơn, ngưỡng không dùng tiền mặt), bảng kê bán ra từ sổ, phụ lục giảm thuế NĐ 174/2025, chuyển số còn được khấu trừ, bút toán bù trừ 33311/133; đối chiếu hóa đơn mua vào, bán ra trong sổ với bảng kê tải từ cổng hóa đơn điện tử (Excel hoặc CSV, nhận cột theo tên): khớp, lệch tiền, sổ có mà cổng không có, cổng có mà sổ chưa ghi, hóa đơn đã hủy hoặc bị thay thế |
| `lfood_ledger` | Hệ thống tài khoản Thông tư 99/2025 (71 TK cấp 1 + chi tiết công ty), bút toán tự sinh từ chứng từ mua, khấu hao, ghi tăng, thanh lý; sửa số báo cáo thì đảo bút toán cũ; phiếu thu, phiếu chi, ủy nhiệm chi; phiếu kế toán; số dư đầu kỳ; bù trừ công nợ đối tác vừa mua vừa bán (Nợ 3311 / Có 1311, chặn vượt số nhỏ hơn); kết chuyển cuối kỳ; khóa sổ; sổ nhật ký chung, sổ cái, bảng cân đối số phát sinh, sổ chi tiết công nợ, B01-DN (Báo cáo tình hình tài chính), B02-DN, B03-DN; bảng điều hành ban giám đốc (doanh thu, chi phí, lợi nhuận so kỳ liền trước; tiền, tồn kho, công nợ cuối kỳ; 5 khoản mục chi phí lớn nhất; 5 khách nợ và 5 nhà cung cấp phải trả nhiều nhất) |
| `lfood_asset` | Tài sản cố định: ghi tăng (từ chứng từ mua hoặc nhập tay), chặn dưới ngưỡng 30 triệu và ngoài khung thời gian, lịch khấu hao đường thẳng tính theo ngày, chứng từ khấu hao tháng (KH), thanh lý, khấu hao lên báo cáo chi phí; xây dựng cơ bản dở dang: tập hợp chi phí vào 241x, nghiệm thu kết chuyển sang nguyên giá và tạo thẻ tài sản |
| `lfood_voucher` | Chứng từ mua dịch vụ, phiên bản, dòng, chênh lệch, điều chỉnh hàng loạt, lô, khoản mục chi phí, tham số pháp lý, thuế suất, báo cáo pivot; tra cứu mức mọi tham số tại một ngày, xuất và nhập gói tham số giữa bản thử và bản thật (mức nhập vào luôn ở trạng thái chờ duyệt) |

## Sao lưu

Dịch vụ `backup` trong docker-compose: hằng ngày 12:00 và 17:30, chạy bù khi bật máy nếu bản gần nhất quá 24 giờ.
Lưu tại `C:\Users\ADMIN\ERP-Backup` (daily 14 bản, weekly 8, monthly 12). Bản sao mã hóa sang OneDrive: đang tắt, bật bằng
`OFFSITE_DIR` + `BACKUP_PASSPHRASE` trong `.env`.
Khôi phục thử: `tools\test-restore.ps1`. Khôi phục: `tools\restore.ps1 -Backup <thư mục> [-Replace]`.

## Trước khi mở link cho người khác

- Đổi mật khẩu `admin` và 4 tài khoản mẫu; mỗi người một tài khoản, không dùng chung.
- `config/odoo.conf`: đổi `admin_passwd`, đặt `list_db = False`.
- Người quản trị cơ sở dữ liệu (quyền PostgreSQL) vẫn có thể gỡ trigger; chuỗi mã băm giúp phát hiện
  nếu có ai sửa. Nên xuất nhật ký định kỳ ra ngoài laptop.
