# ERP LiFeOOD

Hệ thống ERP nội bộ cho công ty thực phẩm LiFeOOD (2 pháp nhân: Văn phòng và Nhà máy), xây trên **Odoo 19 Community**.
Gồm 42 module riêng (`erp/addons/lfood_*`) phủ **173 nghiệp vụ**: kế toán theo Thông tư 99/2025, thuế, mua bán, kho theo lô
và hạn dùng, lương và bảo hiểm, nhân sự, chất lượng, an toàn thực phẩm. Tham số pháp lý (thuế suất, mức đóng bảo hiểm,
lương tối thiểu...) để trong app, có căn cứ và ngày hiệu lực, nên luật đổi thì sửa tham số chứ không sửa mã.

Không làm khâu sản xuất (lệnh sản xuất, định mức, giá thành lệnh). R&D là phân hệ tách riêng, kế toán không truy cập.

## Công nghệ

| Thành phần | Dùng |
|---|---|
| Nền tảng | Odoo 19 Community Edition (LGPL-3), không dùng mã Odoo Enterprise |
| Ngôn ngữ | Python 3.12 (máy chủ), XML (giao diện), OWL/JavaScript của Odoo (web) |
| Cơ sở dữ liệu | PostgreSQL 16 |
| Chạy | Docker Compose: `odoo`, `db`, `backup` (sao lưu tự động bằng `pg_dump` + tệp đính kèm, giữ theo ngày, tuần, tháng) |
| Bảo mật | Mã xác thực 2 lớp, khóa tạm khi đăng nhập sai, tự đăng xuất, nhật ký thao tác có chuỗi mã băm SHA-256 không sửa được |
| Kiểm thử | Kịch bản chạy trong `odoo shell` (803 tình huống nghiệp vụ, duyệt giao diện theo vai trò, đối chiếu số liệu) và HTTP |

## Cài nhanh

Cần [Docker Desktop](https://www.docker.com/products/docker-desktop/) (đang chạy) và Git. Lệnh dưới đây cho PowerShell trên Windows;
macOS, Linux thay `copy` bằng `cp` và dòng `$m = ...` bằng `m=$(ls addons | paste -sd,)`.

```powershell
git clone https://github.com/ConBoCuoiHaha/Erp-vn.git
cd Erp-vn/erp
copy .env.example .env                        # sửa DB_PASSWORD, BACKUP_DIR
copy config/odoo.conf.example config/odoo.conf  # db_password trùng DB_PASSWORD; đổi admin_passwd

# cài 42 module vào cơ sở dữ liệu lfood (lần đầu khoảng 1-3 phút)
$m = (Get-ChildItem addons -Directory).Name -join ','
docker compose run --rm odoo odoo -c /etc/odoo/odoo.conf -d lfood -i $m --stop-after-init

docker compose up -d
```

Mở http://localhost:8069, đăng nhập `admin` / `admin` rồi **đổi mật khẩu ngay** (góc phải > Hồ sơ > Bảo mật tài khoản).
Có sẵn 4 tài khoản mẫu `giamdoc`, `ketoantruong`, `ketoanvien`, `nhanvien` (mật khẩu `lfood2026`) để thử phân quyền;
đổi mật khẩu hoặc khóa chúng trước khi cho người khác dùng.

Trên Windows có thể bấm đúp `erp/start-erp.bat` để bật app. Tắt: `docker compose down` (dữ liệu giữ nguyên).

Dữ liệu mẫu 9 tháng để xem thử (tên đối tác, nhân viên đều bịa, có chữ "(mẫu)"):

```powershell
Get-Content tools/seed_demo.py -Raw | docker compose run --rm -T -e LFOOD_SEED_COMMIT=1 odoo odoo shell -c /etc/odoo/odoo.conf -d lfood --no-http
```

Cập nhật mã mới: `git pull` rồi `docker compose run --rm odoo odoo -c /etc/odoo/odoo.conf -d lfood -u <module> --stop-after-init`
và `docker compose restart odoo`. Kiểm thử, xem [erp/README.md](erp/README.md).

## Mở cho người ở nơi khác truy cập

Không cần sửa mã: `proxy_mode = True` đã bật, Odoo tự nhận địa chỉ công khai khi quản trị đăng nhập qua link đó.
Ví dụ với Microsoft Dev Tunnels:

```powershell
winget install Microsoft.devtunnel
devtunnel user login
devtunnel create lfood-erp --allow-anonymous   # tạo một lần, giữ link cố định
devtunnel port create lfood-erp -p 8069
devtunnel host lfood-erp                       # để cửa sổ này chạy; laptop phải bật và không ngủ
```

Trước khi mở link: đổi mật khẩu mọi tài khoản mẫu và `admin_passwd`, bỏ `--dev=xml` trong `erp/docker-compose.yml`,
bật mã 2 lớp cho quản trị viên.

## Cấu trúc

```
erp/
  addons/lfood_*      42 module nghiệp vụ
  config/             odoo.conf (không đưa lên git), odoo.conf.example
  backup/             kịch bản sao lưu tự động
  tests/              smoke_test.py, ui_crawl.py, data_consistency.py, http_test.ps1
  tools/              seed_demo.py (dữ liệu mẫu), set-mail-password.ps1 (mật khẩu Gmail gửi thư)
docs/                 tài liệu nghiệp vụ, cấu hình, sơ đồ dữ liệu (HTML)
```

## Nghiệp vụ (173)

<details><summary><b>Nền tảng & quản trị hệ thống</b> (13 nghiệp vụ)</summary>

- HT01 Quản lý 2 pháp nhân và kỳ kế toán
- HT02 Người dùng, nhóm quyền, phân quyền theo dòng dữ liệu
- HT03 Đăng nhập an toàn
- HT04 Luồng duyệt nhiều cấp theo hạn mức tiền
- HT05 Nhật ký thay đổi và dấu vết kiểm toán
- HT06 Chuỗi đánh số chứng từ
- HT07 Tìm kiếm nhanh toàn hệ thống
- HT08 Lưu trữ chứng từ điện tử
- HT09 Nhập, xuất Excel và chuyển dữ liệu từ MISA
- HT10 Sao lưu và khôi phục
- HT11 Bảo vệ dữ liệu cá nhân
- HT12 Nhắc hạn tự động
- HT13 Ký số chứng từ điện tử

</details>

<details><summary><b>Cấu hình pháp lý</b> (8 nghiệp vụ)</summary>

- CH01 Bảng tham số pháp lý theo ngày hiệu lực
- CH02 Cập nhật tham số khi có văn bản mới
- CH03 Mô phỏng ảnh hưởng trước khi áp dụng
- CH04 Biểu thuế lũy tiến và bảng bậc
- CH05 Địa bàn và vùng lương tối thiểu
- CH06 Lịch nghỉ lễ Tết và ngày làm việc theo năm
- CH07 Nhắc rà soát tham số
- CH08 Lịch sử tham số và gói cập nhật

</details>

<details><summary><b>Danh mục dùng chung</b> (12 nghiệp vụ)</summary>

- DM01 Đối tác
- DM02 Sản phẩm, nguyên liệu, dịch vụ
- DM03 Đơn vị tính và quy đổi
- DM04 Kho và vị trí kho
- DM05 Hệ thống tài khoản
- DM06 Cây khoản mục chi phí
- DM07 Thuế suất
- DM08 Điều khoản thanh toán
- DM09 Tiền tệ và tỷ giá
- DM10 Phòng ban, chức danh
- DM11 Tài khoản ngân hàng
- DM12 Vùng và kênh bán hàng

</details>

<details><summary><b>Mua hàng</b> (13 nghiệp vụ)</summary>

- MH01 Yêu cầu mua
- MH02 Đề nghị báo giá và so sánh báo giá
- MH03 Đơn mua hàng
- MH04 Hợp đồng mua khung
- MH05 Đối chiếu 3 bên
- MH06 Nhận và kiểm tra hóa đơn đầu vào
- MH07 ★ Chứng từ mua dịch vụ có phiên bản
- MH08 ★ Tự động tính lại số liệu chứng từ
- MH09 Trả lại hàng mua, giảm giá hàng mua
- MH10 Phân bổ chi phí mua hàng
- MH11 Thu mua nông sản không có hóa đơn
- MH12 Mua hàng nhập khẩu
- MH13 Đánh giá nhà cung cấp

</details>

<details><summary><b>Bán hàng, CRM & TMĐT</b> (14 nghiệp vụ)</summary>

- BH01 Cơ hội bán hàng
- BH02 Báo giá
- BH03 Đơn bán hàng
- BH04 Bảng giá theo kênh
- BH05 Chương trình khuyến mãi, chiết khấu thương mại
- BH06 Kiểm soát hạn mức công nợ khách hàng
- BH07 Hợp đồng và chính sách nhà phân phối
- BH08 Hóa đơn bán hàng điện tử có mã cơ quan thuế
- BH09 Hóa đơn điều chỉnh, thay thế
- BH10 Hàng bán bị trả lại
- BH11 Hàng khuyến mãi, biếu tặng, hàng mẫu
- BH12 Chi phí trade marketing, trưng bày
- BH13 Đơn sàn thương mại điện tử
- BH14 Bán hàng xuất khẩu

</details>

<details><summary><b>Kho, lô & mã vạch</b> (11 nghiệp vụ)</summary>

- KHO01 Nhập kho mua hàng theo lô
- KHO02 Xuất kho bán hàng theo hạn dùng
- KHO03 Chuyển kho nội bộ
- KHO04 Chuyển hàng giữa 2 pháp nhân
- KHO06 Nhập kho thành phẩm từ nhà máy
- KHO07 Kiểm kê kho
- KHO08 Hàng cận hạn, hết hạn, tiêu hủy
- KHO09 Cách ly hàng không đạt
- KHO10 Tồn tối thiểu và đề xuất đặt hàng
- KHO11 Quét mã vạch và in tem lô
- KHO12 Tính giá xuất kho

</details>

<details><summary><b>Nghiên cứu & phát triển (R&D, tách riêng)</b> (4 nghiệp vụ)</summary>

- RD01 Dự án sản phẩm mới
- RD02 Công thức theo phiên bản
- RD03 Mẫu thử và đánh giá
- RD04 Duyệt chốt công thức

</details>

<details><summary><b>Chất lượng & an toàn thực phẩm</b> (9 nghiệp vụ)</summary>

- CL01 Kiểm tra nguyên liệu đầu vào
- CL02 Giám sát điểm kiểm soát tới hạn HACCP
- CL03 Kiểm tra thành phẩm trước khi xuất
- CL04 Cảnh báo và hành động khắc phục
- CL05 Truy xuất nguồn gốc lô
- CL06 Thu hồi sản phẩm
- CL07 Hồ sơ công bố sản phẩm
- CL08 Lưu mẫu và kiểm nghiệm định kỳ
- CL09 Sức khỏe và tập huấn người sản xuất trực tiếp

</details>

<details><summary><b>Tài sản, công cụ, bảo trì & xe</b> (13 nghiệp vụ)</summary>

- TS01 Ghi tăng tài sản cố định
- TS02 Tách tài sản khi số lượng lớn hơn 1
- TS03 Tính và ghi sổ khấu hao hằng tháng
- TS04 Điều chỉnh nguyên giá, thời gian sử dụng
- TS05 Điều chuyển tài sản
- TS06 Thanh lý, nhượng bán tài sản
- TS07 Kiểm kê tài sản cố định
- TS08 Thẻ tài sản và sổ tài sản cố định
- TS09 Công cụ dụng cụ
- TS10 Xây dựng cơ bản dở dang
- TS11 Bảo trì thiết bị
- TS12 Quản lý đội xe
- TS13 Thuê tài sản

</details>

<details><summary><b>Kế toán tổng hợp, tiền & công nợ</b> (18 nghiệp vụ)</summary>

- KT01 Thu chi tiền mặt
- KT02 Thu chi qua ngân hàng
- KT03 Đối soát ngân hàng
- KT04 Công nợ phải thu
- KT05 Công nợ phải trả
- KT06 Bù trừ công nợ
- KT07 Tạm ứng và hoàn ứng
- KT08 Bút toán tổng hợp và điều chỉnh
- KT09 Chi phí trả trước
- KT10 Chi phí trích trước
- KT11 Đánh giá chênh lệch tỷ giá cuối kỳ
- KT12 Dự phòng
- KT13 Kết chuyển và xác định kết quả kinh doanh
- KT14 Khóa sổ kỳ và chốt báo cáo
- KT15 Kiểm tra điều kiện chứng từ
- KT16 Vay và lãi vay
- KT17 Sổ kế toán
- KT18 Giao dịch nội bộ và hợp nhất 2 pháp nhân

</details>

<details><summary><b>Khoản mục chi phí & ngân sách</b> (5 nghiệp vụ)</summary>

- NS01 Lập ngân sách trên cây khoản mục
- NS02 Duyệt và phiên bản ngân sách
- NS03 Kiểm soát ngân sách khi phát sinh chi phí
- NS04 So sánh kế hoạch và thực tế
- NS05 Phân bổ chi phí chung

</details>

<details><summary><b>Thuế</b> (13 nghiệp vụ)</summary>

- THUE01 Tính thuế GTGT theo thuế suất
- THUE02 Kiểm tra điều kiện khấu trừ GTGT đầu vào
- THUE03 Tờ khai thuế GTGT tháng hoặc quý
- THUE04 Đối chiếu hóa đơn với cơ quan thuế
- THUE05 Tạm nộp thuế TNDN theo quý
- THUE06 Quyết toán thuế TNDN năm
- THUE07 Khấu trừ thuế TNCN từ tiền lương
- THUE08 Chứng từ khấu trừ thuế TNCN điện tử
- THUE09 Quyết toán thuế TNCN năm
- THUE10 Khấu trừ thuế thu nhập vãng lai
- THUE11 Hồ sơ giao dịch liên kết
- THUE12 Lịch nghĩa vụ thuế và tiền chậm nộp
- THUE13 Thuế nhà thầu nước ngoài

</details>

<details><summary><b>Lao động & nhân sự</b> (17 nghiệp vụ)</summary>

- NSU01 Tuyển dụng
- NSU02 Hồ sơ nhân viên và người phụ thuộc
- NSU03 Hợp đồng lao động
- NSU04 Thang bảng lương và quy chế lương thưởng
- NSU05 Ca làm việc
- NSU06 Chấm công
- NSU07 Làm thêm giờ
- NSU08 Nghỉ phép, nghỉ lễ Tết
- NSU09 Ốm đau, thai sản
- NSU10 Tai nạn lao động, bệnh nghề nghiệp
- NSU11 An toàn vệ sinh lao động
- NSU12 Khen thưởng, kỷ luật lao động
- NSU13 Điều chuyển, thăng chức, điều chỉnh lương
- NSU14 Chấm dứt hợp đồng lao động
- NSU15 Báo cáo sử dụng lao động định kỳ
- NSU16 Đánh giá hiệu suất
- NSU17 Đào tạo

</details>

<details><summary><b>Tiền lương & bảo hiểm</b> (13 nghiệp vụ)</summary>

- LUONG01 Thiết lập lương tối thiểu vùng theo địa bàn
- LUONG02 Tính lương thời gian, sản phẩm, khoán
- LUONG03 Phụ cấp và trợ cấp
- LUONG04 Tiền lương làm thêm và làm đêm
- LUONG05 Tính BHXH, BHYT, BHTN
- LUONG06 Kinh phí công đoàn
- LUONG07 Khai báo tăng, giảm lao động đóng bảo hiểm
- LUONG08 Thuế TNCN trên bảng lương
- LUONG09 Tạm ứng lương
- LUONG10 Thưởng và lương tháng 13
- LUONG11 Bảng lương, phiếu lương, chi lương qua ngân hàng
- LUONG12 Hạch toán và phân bổ chi phí lương
- LUONG13 Đề nghị thanh toán và công tác phí

</details>

<details><summary><b>Báo cáo</b> (10 nghiệp vụ)</summary>

- BC01 Báo cáo tài chính
- BC02 Báo cáo phân tích chi phí nhiều kỳ theo cây
- BC03 Lãi gộp theo nhãn hàng, kênh, vùng, sản phẩm
- BC04 Nhập xuất tồn và hàng cận hạn
- BC05 Công nợ và tuổi nợ
- BC07 Bảng kê và tổng hợp thuế
- BC08 Lao động, lương, bảo hiểm
- BC09 Báo cáo hợp nhất 2 pháp nhân
- BC10 Bảng điều hành ban giám đốc
- BC11 Truy ngược từ báo cáo tới chứng từ

</details>

## Giấy phép

Các module `lfood_*` phát hành theo LGPL-3, cùng giấy phép với Odoo Community.
