# Phần 3: Kho, R&D, Chất lượng
from core import E, R, M

M('kho', 'Kho, lô & mã vạch', 'Inventory, Barcode', 'GĐ2',
  'Sản phẩm theo 5 nhãn hàng, đơn vị tính quy đổi, nhiều kho và vị trí, lô và hạn sử dụng, xuất FEFO, quét mã vạch, dán nhãn, chuyển kho, kiểm kê, tồn tối thiểu tự đặt hàng, định giá tồn kho tự động ghi sổ.')

E('kho', 'SAN_PHAM', 'Sản phẩm', 'product.product', 'Nguyên vật liệu, bán thành phẩm, thành phẩm, dịch vụ, công cụ.', """
id|id|PK|Mã nội bộ
ma|text|UK|Mã hàng
ten|text||Tên
loai|enum||NVL, bán thành phẩm, thành phẩm, dịch vụ, công cụ
nhom_id|id|FK|Nhóm sản phẩm
thuong_hieu_id|id|FK|Nhãn hàng
dvt_id|id|FK|ĐVT tồn kho
dvt_mua_id|id|FK|ĐVT mua
ma_vach|text|UK|Mã vạch
theo_doi_lo|bool||Quản lý theo lô
so_ngay_hsd|int||Hạn sử dụng tính từ ngày sản xuất
so_ngay_canh_bao|int||Cảnh báo trước khi hết hạn
phuong_phap_gia|enum||bình quân, FIFO, giá chuẩn
gia_von_chuan|money||Giá thành định mức
gia_ban|money||Giá bán niêm yết
thue_mua_id|id|FK|Thuế mua mặc định
thue_ban_id|id|FK|Thuế bán mặc định
tk_chi_phi_id|id|FK|TK chi phí khi là dịch vụ
""")
E('kho', 'NHOM_SAN_PHAM', 'Nhóm sản phẩm', 'product.category', 'Cây nhóm, mang tài khoản kho, giá vốn, doanh thu mặc định.', """
id|id|PK|Mã nội bộ
ten|text||Tên nhóm
nhom_cha_id|id|FK|Nhóm cha
tk_kho_id|id|FK|TK kho, 152, 155
tk_gia_von_id|id|FK|TK giá vốn, 632
tk_doanh_thu_id|id|FK|TK doanh thu, 511
""")
E('kho', 'THUONG_HIEU', 'Nhãn hàng', 'product.brand (tùy biến)', "Life's Nest, Beauty Nest, Nutri Life's, Lifes Food, Lifes Chef.", """
id|id|PK|Mã nội bộ
ten|text|UK|Tên nhãn
khoan_muc_id|id|FK|Khoản mục marketing của nhãn
""")
E('kho', 'DON_VI_TINH', 'Đơn vị tính', 'uom.uom', 'Hũ, lốc, thùng, kg, lít; có tỷ lệ quy đổi.', """
id|id|PK|Mã nội bộ
ten|text||Tên
nhom|text||Nhóm quy đổi
ty_le|rate||Hệ số so với đơn vị chuẩn của nhóm
""")
E('kho', 'KHO', 'Kho', 'stock.warehouse', 'Kho NVL, kho thành phẩm, kho cách ly...', """
id|id|PK|Mã nội bộ
cong_ty_id|id|FK|Công ty
ma|text|UK|Mã kho
ten|text||Tên kho
dia_chi|text||Địa chỉ
""")
E('kho', 'VI_TRI_KHO', 'Vị trí kho', 'stock.location', 'Kệ, ô; và vị trí ảo: nhà cung cấp, khách hàng, nhà máy, hao hụt.', """
id|id|PK|Mã nội bộ
kho_id|id|FK|Kho
ten|text||Tên vị trí
vi_tri_cha_id|id|FK|Vị trí cha
loai|enum||nội bộ, nhà cung cấp, khách hàng, nhà máy, hao hụt, cách ly, đang vận chuyển
ma_vach|text|UK|Mã vạch vị trí
""")
E('kho', 'LO_HANG', 'Lô hàng', 'stock.lot', 'Lô NVL và lô thành phẩm, gốc của truy xuất nguồn gốc.', """
id|id|PK|Mã nội bộ
san_pham_id|id|FK|Sản phẩm
so_lo|text|UK|Số lô, duy nhất trong một sản phẩm
ngay_san_xuat|date||Ngày sản xuất
han_su_dung|date||Hạn sử dụng
ngay_canh_bao|date||Ngày cảnh báo
nha_cung_cap_id|id|FK|Nhà cung cấp của lô NVL
trang_thai|enum||dùng được, cách ly, đã thu hồi
""")
E('kho', 'LOAI_PHIEU_KHO', 'Loại phiếu kho', 'stock.picking.type', 'Nhập mua, xuất bán, chuyển kho, nhập thành phẩm từ nhà máy.', """
id|id|PK|Mã nội bộ
kho_id|id|FK|Kho
ma|text|UK|Mã
ten|text||Tên
chuoi_so_id|id|FK|Chuỗi đánh số
vi_tri_nguon_mac_dinh_id|id|FK|Nguồn mặc định
vi_tri_dich_mac_dinh_id|id|FK|Đích mặc định
""")
E('kho', 'PHIEU_KHO', 'Phiếu kho', 'stock.picking', 'Một lần nhập, xuất hoặc chuyển.', """
id|id|PK|Mã nội bộ
so|text|UK|Số phiếu
loai_phieu_id|id|FK|Loại phiếu
doi_tac_id|id|FK|Nhà cung cấp hoặc khách
vi_tri_nguon_id|id|FK|Từ vị trí
vi_tri_dich_id|id|FK|Tới vị trí
chung_tu_nguon|text||Đơn mua, đơn bán hoặc phiếu nhập thành phẩm
ngay_du_kien|datetime||Dự kiến
ngay_hoan_thanh|datetime||Thực tế
trang_thai|enum||nháp, chờ hàng, sẵn sàng, hoàn thành, hủy
""")
E('kho', 'DICH_CHUYEN_KHO', 'Dịch chuyển kho', 'stock.move', 'Một mặt hàng di chuyển giữa hai vị trí.', """
id|id|PK|Mã nội bộ
phieu_kho_id|id|FK|Phiếu kho
san_pham_id|id|FK|Sản phẩm
so_luong|qty||Số lượng
dvt_id|id|FK|Đơn vị tính
vi_tri_nguon_id|id|FK|Từ
vi_tri_dich_id|id|FK|Tới
dong_don_mua_id|id|FK|Theo dòng đơn mua
dong_don_ban_id|id|FK|Theo dòng đơn bán
trang_thai|enum||nháp, đã giữ chỗ, hoàn thành, hủy
""")
E('kho', 'DONG_DICH_CHUYEN_LO', 'Chi tiết theo lô', 'stock.move.line', 'Số lượng thực tế theo lô và vị trí, ghi lúc quét mã vạch.', """
id|id|PK|Mã nội bộ
dich_chuyen_id|id|FK|Dịch chuyển
lo_id|id|FK|Lô
vi_tri_nguon_id|id|FK|Từ
vi_tri_dich_id|id|FK|Tới
so_luong|qty||Số lượng thực tế
nguoi_quet_id|id|FK|Người quét
thoi_diem_quet|datetime||Thời điểm quét
""")
E('kho', 'TON_KHO', 'Tồn kho', 'stock.quant', 'Số tồn theo sản phẩm, vị trí, lô.', """
id|id|PK|Mã nội bộ
san_pham_id|id|FK|Sản phẩm
vi_tri_id|id|FK|Vị trí
lo_id|id|FK|Lô
so_luong|qty||Tồn
so_luong_giu_cho|qty||Đã giữ cho đơn
""")
E('kho', 'LOP_GIA_TRI_TON', 'Lớp giá trị tồn', 'stock.valuation.layer', 'Giá trị từng lần nhập xuất, căn cứ ghi sổ kho.', """
id|id|PK|Mã nội bộ
dich_chuyen_id|id|FK|Dịch chuyển
san_pham_id|id|FK|Sản phẩm
so_luong|qty||Số lượng, âm là xuất
don_gia|money||Đơn giá
gia_tri|money||Giá trị
sl_con_lai|qty||Còn lại để tính FIFO
but_toan_id|id|FK|Bút toán kho
""")
E('kho', 'KIEM_KE', 'Đợt kiểm kê', 'stock.quant (inventory mode)', 'Kiểm kê định kỳ hoặc đột xuất.', """
id|id|PK|Mã nội bộ
so|text|UK|Số đợt
kho_id|id|FK|Kho
ngay|date||Ngày kiểm
trang_thai|enum||đang đếm, chờ duyệt, đã điều chỉnh
nguoi_kiem_id|id|FK|Trưởng tổ kiểm kê
""")
E('kho', 'DONG_KIEM_KE', 'Dòng kiểm kê', 'stock.quant (inventory line)', 'Sổ sách so với thực tế.', """
id|id|PK|Mã nội bộ
kiem_ke_id|id|FK|Đợt kiểm kê
san_pham_id|id|FK|Sản phẩm
lo_id|id|FK|Lô
vi_tri_id|id|FK|Vị trí
sl_so_sach|qty||Số trên sổ
sl_thuc_te|qty||Số đếm được
chenh_lech|qty||Thực tế trừ sổ sách
""")
E('kho', 'QUY_TAC_TON_TOI_THIEU', 'Quy tắc tồn tối thiểu', 'stock.warehouse.orderpoint', 'Dưới mức thì tự đề xuất mua hoặc báo nhà máy.', """
id|id|PK|Mã nội bộ
san_pham_id|id|FK|Sản phẩm
kho_id|id|FK|Kho
sl_toi_thieu|qty||Mức tối thiểu
sl_toi_da|qty||Mức tối đa
hanh_dong|enum||mua, báo nhà máy
""")

R('kho', 'NHOM_SAN_PHAM', '|o--o{', 'NHOM_SAN_PHAM', 'nhóm cha của')
R('kho', 'NHOM_SAN_PHAM', '||--o{', 'SAN_PHAM', 'gồm')
R('kho', 'THUONG_HIEU', '|o--o{', 'SAN_PHAM', 'nhãn của')
R('kho', 'DON_VI_TINH', '||--o{', 'SAN_PHAM', 'ĐVT')
R('kho', 'CONG_TY', '||--o{', 'KHO', 'sở hữu')
R('kho', 'KHO', '||--|{', 'VI_TRI_KHO', 'gồm')
R('kho', 'VI_TRI_KHO', '|o--o{', 'VI_TRI_KHO', 'vị trí cha của')
R('kho', 'SAN_PHAM', '||--o{', 'LO_HANG', 'theo lô')
R('kho', 'KHO', '||--o{', 'LOAI_PHIEU_KHO', 'có')
R('kho', 'LOAI_PHIEU_KHO', '||--o{', 'PHIEU_KHO', 'phân loại')
R('kho', 'PHIEU_KHO', '||--|{', 'DICH_CHUYEN_KHO', 'gồm')
R('kho', 'SAN_PHAM', '||--o{', 'DICH_CHUYEN_KHO', 'di chuyển')
R('kho', 'DICH_CHUYEN_KHO', '||--|{', 'DONG_DICH_CHUYEN_LO', 'chi tiết lô')
R('kho', 'LO_HANG', '|o--o{', 'DONG_DICH_CHUYEN_LO', 'lô')
R('kho', 'VI_TRI_KHO', '||--o{', 'DONG_DICH_CHUYEN_LO', 'từ, tới')
R('kho', 'DONG_DON_MUA', '|o--o{', 'DICH_CHUYEN_KHO', 'nhận theo')
R('kho', 'DONG_DON_BAN', '|o--o{', 'DICH_CHUYEN_KHO', 'giao theo')
R('kho', 'SAN_PHAM', '||--o{', 'TON_KHO', 'tồn')
R('kho', 'VI_TRI_KHO', '||--o{', 'TON_KHO', 'tại')
R('kho', 'LO_HANG', '|o--o{', 'TON_KHO', 'của lô')
R('kho', 'DICH_CHUYEN_KHO', '||--o|', 'LOP_GIA_TRI_TON', 'định giá')
R('kho', 'LOP_GIA_TRI_TON', '|o--o|', 'BUT_TOAN', 'ghi sổ')
R('kho', 'KHO', '||--o{', 'KIEM_KE', 'kiểm kê')
R('kho', 'KIEM_KE', '||--|{', 'DONG_KIEM_KE', 'gồm')
R('kho', 'SAN_PHAM', '||--o{', 'DONG_KIEM_KE', 'được đếm')
R('kho', 'SAN_PHAM', '||--o{', 'QUY_TAC_TON_TOI_THIEU', 'đặt mức')
R('kho', 'KHO', '||--o{', 'QUY_TAC_TON_TOI_THIEU', 'tại')

# ------------------------------------------------------------------ R&D (tách riêng)
M('rd', 'Nghiên cứu & phát triển (R&D)', 'Viết riêng, dữ liệu tách biệt', 'GĐ3',
  'Bộ phận R&D làm việc tách riêng: dự án sản phẩm mới, công thức có phiên bản, mẫu thử và đánh giá. Chỉ nhóm R&D và Giám đốc xem được; kế toán không truy cập. ERP không quản lý khâu sản xuất (lệnh sản xuất, định mức, giá thành lệnh).')

E('rd', 'DU_AN_RD', 'Dự án R&D', 'lfood.rd.project', 'Một sản phẩm mới hoặc cải tiến.', """
id|id|PK|Mã nội bộ
ma|text|UK|Mã dự án
ten|text||Tên sản phẩm dự kiến
phu_trach_id|id|FK|Người phụ trách (người dùng nhóm R&D)
ngay_bat_dau|date||Ngày bắt đầu
trang_thai|enum||ý tưởng, thử mẫu, đánh giá, chuyển giao, dừng
""")
E('rd', 'CONG_THUC', 'Công thức', 'lfood.rd.formula', 'Công thức theo phiên bản; bảo mật, chỉ R&D xem.', """
id|id|PK|Mã nội bộ
du_an_id|id|FK|Dự án
phien_ban|int||Số phiên bản
thanh_phan|text||Nguyên liệu và tỷ lệ
quy_trinh|text||Các bước chế biến
trang_thai|enum||nháp, đã chốt
""")
E('rd', 'MAU_THU', 'Mẫu thử', 'lfood.rd.sample', 'Một lần làm mẫu theo công thức.', """
id|id|PK|Mã nội bộ
cong_thuc_id|id|FK|Công thức
ngay|date||Ngày làm mẫu
ket_qua|text||Cảm quan, chỉ tiêu kiểm nghiệm
danh_gia|enum||đạt, cần sửa, loại
""")

R('rd', 'NGUOI_DUNG', '||--o{', 'DU_AN_RD', 'phụ trách')
R('rd', 'DU_AN_RD', '||--o{', 'CONG_THUC', 'có phiên bản')
R('rd', 'CONG_THUC', '||--o{', 'MAU_THU', 'làm mẫu')

# ------------------------------------------------------------------ CHẤT LƯỢNG
M('cl', 'Chất lượng ISO 22000 / HACCP', 'Quality', 'GĐ2',
  'Điểm kiểm tra khi nhập mua, xuất bán, điểm kiểm soát tới hạn CCP có giới hạn đo, phiếu kiểm tra, cảnh báo và hành động khắc phục, truy xuất lô xuôi ngược, lệnh thu hồi.')

E('cl', 'DIEM_KIEM_TRA', 'Điểm kiểm tra', 'quality.point', 'Nơi và cách kiểm tra; điểm CCP có giới hạn trên dưới.', """
id|id|PK|Mã nội bộ
ten|text||Tên, ví dụ Nhiệt độ tiệt trùng
san_pham_id|id|FK|Áp cho sản phẩm
loai_phieu_kho_id|id|FK|Kiểm khi nhập hoặc xuất
kieu|enum||đạt hoặc không, đo giá trị, chụp ảnh
gioi_han_duoi|rate||Giới hạn dưới
gioi_han_tren|rate||Giới hạn trên
la_ccp|bool||Điểm kiểm soát tới hạn HACCP
""")
E('cl', 'PHIEU_KIEM_TRA', 'Phiếu kiểm tra', 'quality.check', 'Kết quả một lần kiểm tra.', """
id|id|PK|Mã nội bộ
diem_id|id|FK|Điểm kiểm tra
phieu_kho_id|id|FK|Phiếu kho
lo_id|id|FK|Lô
gia_tri_do|rate||Giá trị đo
ket_qua|enum||chờ, đạt, không đạt
nguoi_kiem_id|id|FK|Người kiểm
thoi_diem|datetime||Thời điểm
""")
E('cl', 'CANH_BAO_CHAT_LUONG', 'Cảnh báo chất lượng', 'quality.alert', 'Mở khi không đạt; theo dõi khắc phục.', """
id|id|PK|Mã nội bộ
phieu_kiem_tra_id|id|FK|Phiếu không đạt
mo_ta|text||Mô tả
nguyen_nhan|text||Nguyên nhân
hanh_dong|text||Hành động khắc phục
han_xu_ly|date||Hạn
trang_thai|enum||mới, đang xử lý, đã đóng
""")
E('cl', 'THU_HOI_SAN_PHAM', 'Lệnh thu hồi', 'mới (tùy biến)', 'Thu hồi lô lỗi từ khách hàng.', """
id|id|PK|Mã nội bộ
lo_id|id|FK|Lô bị thu hồi
ly_do|text||Lý do
sl_da_giao|qty||Số đã giao cho khách
sl_da_thu|qty||Số đã thu về
trang_thai|enum||mở, đang thu, đã hủy hàng, đóng
""")

R('cl', 'DIEM_KIEM_TRA', '||--o{', 'PHIEU_KIEM_TRA', 'sinh phiếu')
R('cl', 'SAN_PHAM', '|o--o{', 'DIEM_KIEM_TRA', 'áp cho')
R('cl', 'LOAI_PHIEU_KHO', '|o--o{', 'DIEM_KIEM_TRA', 'kiểm khi nhập xuất')
R('cl', 'PHIEU_KHO', '|o--o{', 'PHIEU_KIEM_TRA', 'được kiểm')
R('cl', 'LO_HANG', '|o--o{', 'PHIEU_KIEM_TRA', 'của lô')
R('cl', 'PHIEU_KIEM_TRA', '||--o|', 'CANH_BAO_CHAT_LUONG', 'không đạt thì mở')
R('cl', 'LO_HANG', '||--o{', 'THU_HOI_SAN_PHAM', 'bị thu hồi')
