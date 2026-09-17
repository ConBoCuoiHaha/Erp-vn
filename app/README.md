# ERP LiFeOOD — Tài sản cố định & Khấu hao

Nhập 4 sheet theo file `Thử AI.xlsx` → bấm **Lưu** → tự chuyển sang **màn chứng từ kết quả**
(giao diện theo MISA AMIS). Dữ liệu lưu ở `localStorage` (key `lfood_tscd_v2`).

Bản cũ (chứng từ mua dịch vụ + báo cáo cây khoản mục) được giữ nguyên ở `../app-v1/`.

## Chạy

```bash
python -m http.server 5173 --directory app
```

Hoặc có mật khẩu + tunnel cho người ở xa: `start-demo.bat` ở thư mục gốc.

## 4 sheet

| Sheet | Nhập | Tự tính |
|---|---|---|
| **1. Mua hàng (ghi tăng)** | Mã hàng, Tên TS, Loại TS (Máy móc / Xe), Kho (1/2/3), SL, Đơn giá | Thành tiền = SL × Đơn giá, dòng Tổng. Chỉ **Nhân viên kho** và **Kế toán trưởng** được nhập |
| **2. Tính khấu hao** | Ngày ghi tăng, Đơn vị sử dụng, Không tính KH, Thời gian sử dụng + Tháng/Năm, Kỳ tính | Số CT ghi tăng, nguyên giá (TK 211), KH tháng / năm (TK 214), hao mòn lũy kế, giá trị còn lại, bảng khấu hao từng tháng |
| **3. Danh sách mua hàng** | — | **1 dòng tổng** + mã riêng `DSMH00001` |
| **4. Khấu hao** | TK công nợ (627), TK kho (214), Khoản mục CP 1/2 | Số tiền khấu hao của kỳ, Tên KMCP (1 = Chi phí, 2 = Khấu hao) |

### Công thức khấu hao

- Chọn **Tháng**: KH tháng = Nguyên giá ÷ T; KH năm = Nguyên giá ÷ T × 12
- Chọn **Năm**: KH năm = Nguyên giá ÷ T; KH tháng = Nguyên giá ÷ T ÷ 12
- Hao mòn lũy kế: tháng đầu = N1, mỗi tháng sau cộng thêm KH tháng
- Giá trị còn lại = Nguyên giá − Hao mòn lũy kế
- Tháng cuối nhận phần làm tròn → tổng khấu hao **đúng bằng nguyên giá**

## Màn kết quả

Sinh ra khi bấm Lưu: số `KH00001`, tham chiếu `GT00001` + `DSMH00001`.

- Lưới **Hạch toán | Thuế**, bấm vào dòng để sửa (giống MISA), bật/tắt **Hiển thị tài khoản**
- **Tổng tiền dịch vụ** sửa được: gõ số mới + Enter → tự phân bổ lại các dòng theo tỷ trọng, không lệch đồng nào
- Thêm dòng (F9), Thêm ghi chú, Xóa hết dòng, Sàn TMĐT / Tên shop, Đính kèm (≤ 5MB)
- **Hủy / Hoãn / Cất (Ctrl+S) / Cất và Đóng / Cất và Thêm**

## Bố cục

Khung cố định: thanh trên 48px, menu trái 232px, đầu trang 52px, thân cuộn, chân trang.
Đổi mục chỉ thay nội dung bên trong nên không bị giật/lệch.
Dưới 900px menu trái thành ngăn kéo (nút ☰); dưới 600px form về 1 cột.
