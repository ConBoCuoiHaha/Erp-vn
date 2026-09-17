# Phần 2: Mua hàng (+ chứng từ mua dịch vụ có phiên bản), Bán hàng & CRM
from core import E, R, M

M('mh', 'Mua hàng & chứng từ mua dịch vụ', 'Purchase, Purchase Agreements, Accounting (Vendor Bills)', 'GĐ1',
  'Yêu cầu mua, đề nghị báo giá, đơn mua, hợp đồng khung, bảng giá nhà cung cấp, nhận hàng, đối chiếu 3 bên. ★ Chứng từ mua dịch vụ có phiên bản: sau khi Cất vẫn Sửa được, tự động tính lại số liệu, báo cáo giữ nguyên.')

E('mh', 'YEU_CAU_MUA', 'Yêu cầu mua', 'purchase.requisition', 'Phòng ban đề nghị mua hàng hoặc dịch vụ.', """
id|id|PK|Mã nội bộ
so|text|UK|Số yêu cầu
phong_ban_id|id|FK|Phòng ban đề nghị
nguoi_yeu_cau_id|id|FK|Người đề nghị
ngay_can|date||Ngày cần hàng
ly_do|text||Lý do
trang_thai|enum||nháp, chờ duyệt, đã duyệt, đã đặt hàng, hủy
""")
E('mh', 'DONG_YEU_CAU_MUA', 'Dòng yêu cầu mua', 'purchase.requisition.line', 'Hàng cần mua.', """
id|id|PK|Mã nội bộ
yeu_cau_id|id|FK|Yêu cầu mua
san_pham_id|id|FK|Hàng hoặc dịch vụ
so_luong|qty||Số lượng
dvt_id|id|FK|Đơn vị tính
don_gia_du_kien|money||Đơn giá dự kiến
khoan_muc_id|id|FK|Khoản mục chi phí
""")
E('mh', 'HOP_DONG_MUA', 'Hợp đồng mua', 'purchase.requisition (blanket order)', 'Hợp đồng khung với nhà cung cấp, ví dụ suất ăn, vận tải.', """
id|id|PK|Mã nội bộ
so|text|UK|Số hợp đồng
doi_tac_id|id|FK|Nhà cung cấp
ngay_hieu_luc|date||Từ ngày
ngay_het_han|date||Đến ngày
tong_gia_tri|money||Giá trị hợp đồng
da_thuc_hien|money||Đã lập chứng từ
trang_thai|enum||nháp, hiệu lực, hết hạn, hủy
""")
E('mh', 'DON_MUA', 'Đơn mua', 'purchase.order', 'Đề nghị báo giá rồi thành đơn mua đã xác nhận.', """
id|id|PK|Mã nội bộ
so|text|UK|Số đơn, ví dụ PO00012
cong_ty_id|id|FK|Công ty
doi_tac_id|id|FK|Nhà cung cấp
yeu_cau_id|id|FK|Từ yêu cầu mua
hop_dong_id|id|FK|Theo hợp đồng
ngay_dat|date||Ngày đặt
ngay_giao_du_kien|date||Ngày giao dự kiến
kho_nhan_id|id|FK|Kho nhận
dieu_khoan_tt_id|id|FK|Điều khoản thanh toán
tong_truoc_thue|money||Tổng tiền hàng
tong_thue|money||Tổng thuế
tong_cong|money||Tổng thanh toán
trang_thai|enum||báo giá, đã gửi, đã xác nhận, đã nhận, đã lập hóa đơn, hủy
""")
E('mh', 'DONG_DON_MUA', 'Dòng đơn mua', 'purchase.order.line', 'Hàng trong đơn mua và số đã nhận, đã lập hóa đơn.', """
id|id|PK|Mã nội bộ
don_mua_id|id|FK|Đơn mua
san_pham_id|id|FK|Sản phẩm
mo_ta|text||Mô tả
so_luong|qty||Số lượng đặt
dvt_id|id|FK|Đơn vị tính
don_gia|money||Đơn giá
thue_id|id|FK|Thuế
thanh_tien|money||Thành tiền
sl_da_nhan|qty||Đã nhận
sl_da_lap_hd|qty||Đã lập hóa đơn
khoan_muc_id|id|FK|Khoản mục chi phí
""")
E('mh', 'BANG_GIA_NCC', 'Bảng giá nhà cung cấp', 'product.supplierinfo', 'Giá, số lượng tối thiểu, thời gian giao của từng nhà cung cấp.', """
id|id|PK|Mã nội bộ
doi_tac_id|id|FK|Nhà cung cấp
san_pham_id|id|FK|Sản phẩm
don_gia|money||Đơn giá
sl_toi_thieu|qty||Mua tối thiểu
so_ngay_giao|int||Thời gian giao
hieu_luc_tu|date||Từ ngày
hieu_luc_den|date||Đến ngày
""")
E('mh', 'CHUNG_TU_MUA_DV', '★ Chứng từ mua dịch vụ', 'account.move in_invoice (tùy biến có phiên bản)', 'Phần đầu cố định của chứng từ. Số liệu nằm ở các phiên bản; báo cáo chỉ đọc phiên bản báo cáo.', """
id|id|PK|Mã nội bộ
so_ct|text|UK|Số chứng từ, ví dụ MDV00433
cong_ty_id|id|FK|Công ty
doi_tac_id|id|FK|Nhà cung cấp
don_mua_id|id|FK|Lập từ đơn mua
hop_dong_id|id|FK|Lập từ hợp đồng mua
nhan_vien_mua_id|id|FK|Nhân viên mua hàng
ngay_hach_toan|date||Ngày hạch toán, quyết định kỳ
ngay_chung_tu|date||Ngày chứng từ
dien_giai|text||Diễn giải
so_hoa_don|text||Tham chiếu, số hóa đơn NCC
dieu_khoan_tt_id|id|FK|Điều khoản thanh toán
so_ngay_no|int||Số ngày được nợ
han_thanh_toan|date||Hạn thanh toán
thanh_toan|enum||chưa thanh toán, thanh toán ngay
phuong_thuc_tt|enum||tiền mặt, chuyển khoản
nhan_hoa_don|enum||nhận kèm hóa đơn, nhận sau, không có
la_cp_mua_hang|bool||Là chi phí mua hàng
chiet_khau|enum||không, theo phần trăm, theo số tiền
san_tmdt|text||Sàn thương mại điện tử
ten_shop|text||Tên shop
trang_thai|enum||nháp, chờ duyệt, đã cất, đang sửa, đã hủy
phien_ban_hien_hanh_id|id|FK|Phiên bản đang dùng để xem và sửa tiếp
phien_ban_bao_cao_id|id|FK|Phiên bản mà bút toán và báo cáo đọc
but_toan_id|id|FK|Bút toán ghi sổ
""")
E('mh', 'PHIEN_BAN_CHUNG_TU', '★ Phiên bản chứng từ', 'mới (tùy biến)', 'Phiên bản 1 là số gốc lúc mua vào. Mỗi lần Sửa rồi Lưu tạo thêm một phiên bản; phiên bản đã lưu không sửa được.', """
id|id|PK|Mã nội bộ
chung_tu_id|id|FK|Chứng từ mua dịch vụ
so_phien_ban|int|UK|1, 2, 3... trong một chứng từ
loai|enum||gốc lúc mua vào, sửa đổi, khôi phục gốc
phien_ban_nguon_id|id|FK|Sửa từ phiên bản nào
trang_thai|enum||nháp đang sửa, đã lưu
tong_tien_dv|money||Tổng tiền dịch vụ
tong_thue|money||Thuế GTGT
tong_thanh_toan|money||Tổng tiền thanh toán
ly_do_sua|text||Bắt buộc khi lưu phiên bản sửa đổi
quy_tac_id|id|FK|Quy tắc tự động đã dùng
nguoi_tao_id|id|FK|Người tạo
thoi_diem_luu|datetime||Thời điểm lưu
but_toan_dieu_chinh_id|id|FK|Bút toán điều chỉnh nếu được duyệt đưa vào báo cáo
""")
E('mh', 'DONG_PHIEN_BAN', '★ Dòng của phiên bản', 'account.move.line (bản sao theo phiên bản)', 'Lưới Hạch toán của một phiên bản. Mỗi dòng trỏ về dòng gốc lúc mua vào.', """
id|id|PK|Mã nội bộ
phien_ban_id|id|FK|Phiên bản
dong_goc_id|id|FK|Dòng tương ứng ở phiên bản 1
thu_tu|int||Số thứ tự dòng
dich_vu_id|id|FK|Mã dịch vụ
ten_dich_vu|text||Tên dịch vụ
tk_chi_phi_id|id|FK|TK chi phí hoặc TK kho
tk_cong_no_id|id|FK|TK công nợ, 3311
doi_tuong_id|id|FK|Đối tượng
dvt_id|id|FK|Đơn vị tính
so_luong|qty||Số lượng
don_gia|money||Đơn giá
thanh_tien|money||Thành tiền
thue_id|id|FK|Thuế suất
tien_thue|money||Tiền thuế
khoan_muc_id|id|FK|Khoản mục CP
khoa_phan_bo|bool||Giữ nguyên khi tự động phân bổ
""")
E('mh', 'CHENH_LECH_PHIEN_BAN', '★ Chênh lệch phiên bản', 'mới (tùy biến)', 'Từng trường thay đổi so với phiên bản nguồn và so với gốc lúc mua vào.', """
id|id|PK|Mã nội bộ
phien_ban_id|id|FK|Phiên bản mới
dong_id|id|FK|Dòng bị đổi, trống nếu là phần đầu
truong|text||Tên trường
gia_tri_nguon|text||Giá trị ở phiên bản nguồn
gia_tri_goc|text||Giá trị lúc mua vào
gia_tri_moi|text||Giá trị mới
do_nguoi_sua|bool||Người sửa trực tiếp, sai là do hệ thống tự tính
""")

R('mh', 'PHONG_BAN', '||--o{', 'YEU_CAU_MUA', 'đề nghị')
R('mh', 'YEU_CAU_MUA', '||--|{', 'DONG_YEU_CAU_MUA', 'gồm')
R('mh', 'SAN_PHAM', '||--o{', 'DONG_YEU_CAU_MUA', 'cần mua')
R('mh', 'YEU_CAU_MUA', '|o--o{', 'DON_MUA', 'chuyển thành')
R('mh', 'DOI_TAC', '||--o{', 'HOP_DONG_MUA', 'ký')
R('mh', 'HOP_DONG_MUA', '|o--o{', 'DON_MUA', 'gọi hàng')
R('mh', 'DOI_TAC', '||--o{', 'DON_MUA', 'nhận đơn')
R('mh', 'DON_MUA', '||--|{', 'DONG_DON_MUA', 'gồm')
R('mh', 'SAN_PHAM', '||--o{', 'DONG_DON_MUA', 'được mua')
R('mh', 'THUE', '|o--o{', 'DONG_DON_MUA', 'áp')
R('mh', 'DOI_TAC', '||--o{', 'BANG_GIA_NCC', 'báo giá')
R('mh', 'SAN_PHAM', '||--o{', 'BANG_GIA_NCC', 'có giá')
R('mh', 'DON_MUA', '||--o{', 'PHIEU_KHO', 'nhận hàng qua')
R('mh', 'DON_MUA', '|o--o{', 'BUT_TOAN', 'lập hóa đơn NCC')
R('mh', 'DOI_TAC', '||--o{', 'CHUNG_TU_MUA_DV', 'xuất hóa đơn')
R('mh', 'DON_MUA', '|o--o{', 'CHUNG_TU_MUA_DV', 'lập từ đơn')
R('mh', 'HOP_DONG_MUA', '|o--o{', 'CHUNG_TU_MUA_DV', 'lập từ hợp đồng')
R('mh', 'NHAN_VIEN', '|o--o{', 'CHUNG_TU_MUA_DV', 'mua hàng')
R('mh', 'CHUNG_TU_MUA_DV', '||--|{', 'PHIEN_BAN_CHUNG_TU', 'có các phiên bản')
R('mh', 'PHIEN_BAN_CHUNG_TU', '|o--o{', 'PHIEN_BAN_CHUNG_TU', 'nguồn sửa của')
R('mh', 'PHIEN_BAN_CHUNG_TU', '||--|{', 'DONG_PHIEN_BAN', 'gồm')
R('mh', 'DONG_PHIEN_BAN', '|o--o{', 'DONG_PHIEN_BAN', 'dòng gốc của')
R('mh', 'SAN_PHAM', '||--o{', 'DONG_PHIEN_BAN', 'dịch vụ')
R('mh', 'KHOAN_MUC_CHI_PHI', '|o--o{', 'DONG_PHIEN_BAN', 'phân loại')
R('mh', 'HE_THONG_TAI_KHOAN', '||--o{', 'DONG_PHIEN_BAN', 'TK chi phí, công nợ')
R('mh', 'THUE', '|o--o{', 'DONG_PHIEN_BAN', 'áp')
R('mh', 'PHIEN_BAN_CHUNG_TU', '||--o{', 'CHENH_LECH_PHIEN_BAN', 'ghi chênh lệch')
R('mh', 'QUY_TAC_TU_DONG', '|o--o{', 'PHIEN_BAN_CHUNG_TU', 'tính lại theo')
R('mh', 'CHUNG_TU_MUA_DV', '||--o|', 'BUT_TOAN', 'ghi sổ từ phiên bản báo cáo')
R('mh', 'PHIEN_BAN_CHUNG_TU', '|o--o|', 'BUT_TOAN', 'điều chỉnh khi được duyệt')

# ------------------------------------------------------------------ BÁN HÀNG
M('bh', 'Bán hàng, CRM & TMĐT', 'CRM, Sales, Loyalty, eCommerce connectors', 'GĐ2',
  'Cơ hội bán hàng, báo giá, đơn bán, bảng giá theo kênh GT / MT / Online, chương trình khuyến mãi, hạn mức tín dụng chặn đơn, giao hàng, hóa đơn, đồng bộ đơn sàn Shopee, Lazada, Tiki, TikTok Shop.')

E('bh', 'CO_HOI', 'Cơ hội bán hàng', 'crm.lead', 'Nhà phân phối, siêu thị tiềm năng.', """
id|id|PK|Mã nội bộ
ten|text||Tên cơ hội
doi_tac_id|id|FK|Khách hàng
nhan_vien_ban_id|id|FK|Phụ trách
giai_doan_id|id|FK|Giai đoạn
gia_tri_du_kien|money||Doanh thu dự kiến
xac_suat|rate||Xác suất thành công
trang_thai|enum||đang theo, thắng, thua
""")
E('bh', 'GIAI_DOAN_CRM', 'Giai đoạn CRM', 'crm.stage', 'Mới, Đã liên hệ, Gửi mẫu, Đàm phán, Thắng.', """
id|id|PK|Mã nội bộ
ten|text||Tên giai đoạn
thu_tu|int||Thứ tự
""")
E('bh', 'KENH_PHAN_PHOI', 'Kênh phân phối', 'crm.team', 'GT, MT, Online, Xuất khẩu.', """
id|id|PK|Mã nội bộ
ma|text|UK|GT, MT, ONL, XK
ten|text||Tên kênh
khoan_muc_id|id|FK|Khoản mục chi phí bán hàng của kênh
""")
E('bh', 'VUNG_BAN_HANG', 'Vùng bán hàng', 'res.country.state group', 'Miền Nam, Miền Trung, Miền Bắc.', """
id|id|PK|Mã nội bộ
ma|text|UK|MN, MT, MB
ten|text||Tên vùng
cac_tinh|json||Tỉnh thành thuộc vùng
""")
E('bh', 'BANG_GIA', 'Bảng giá bán', 'product.pricelist', 'Giá theo kênh, theo nhóm khách.', """
id|id|PK|Mã nội bộ
ten|text||Tên bảng giá
kenh_id|id|FK|Kênh áp dụng
tien_te_id|id|FK|Tiền tệ
hieu_luc_tu|date||Từ ngày
hieu_luc_den|date||Đến ngày
""")
E('bh', 'DONG_BANG_GIA', 'Dòng bảng giá', 'product.pricelist.item', 'Giá hoặc chiết khấu theo sản phẩm và số lượng.', """
id|id|PK|Mã nội bộ
bang_gia_id|id|FK|Bảng giá
san_pham_id|id|FK|Sản phẩm
sl_toi_thieu|qty||Từ số lượng
gia|money||Giá bán
chiet_khau|rate||Chiết khấu phần trăm
""")
E('bh', 'CHUONG_TRINH_KM', 'Chương trình khuyến mãi', 'loyalty.program', 'Chiết khấu, tặng hàng, combo; trừ vào ngân sách khoản mục.', """
id|id|PK|Mã nội bộ
ten|text||Tên chương trình
loai|enum||chiết khấu, tặng hàng, combo
tu_ngay|date||Từ ngày
den_ngay|date||Đến ngày
dieu_kien|json||Điều kiện áp dụng
khoan_muc_id|id|FK|Khoản mục chi phí khuyến mãi
""")
E('bh', 'DON_BAN', 'Đơn bán', 'sale.order', 'Báo giá rồi thành đơn bán.', """
id|id|PK|Mã nội bộ
so|text|UK|Số đơn, ví dụ SO00031
cong_ty_id|id|FK|Công ty
doi_tac_id|id|FK|Khách hàng
dia_chi_giao_id|id|FK|Địa chỉ giao
nhan_vien_ban_id|id|FK|Nhân viên bán hàng
co_hoi_id|id|FK|Từ cơ hội
kenh_id|id|FK|Kênh
vung_id|id|FK|Vùng
bang_gia_id|id|FK|Bảng giá
kho_xuat_id|id|FK|Kho xuất
ngay_dat|date||Ngày đặt
tong_truoc_thue|money||Tổng tiền hàng
tong_thue|money||Tổng thuế
tong_cong|money||Tổng thanh toán
bi_chan_tin_dung|bool||Bị chặn do vượt hạn mức
trang_thai|enum||báo giá, đã gửi, đã xác nhận, đang giao, đã lập hóa đơn, hủy
""")
E('bh', 'DONG_DON_BAN', 'Dòng đơn bán', 'sale.order.line', 'Hàng bán, số đã giao và đã lập hóa đơn.', """
id|id|PK|Mã nội bộ
don_ban_id|id|FK|Đơn bán
san_pham_id|id|FK|Sản phẩm
so_luong|qty||Số lượng
dvt_id|id|FK|Đơn vị tính
don_gia|money||Đơn giá
chiet_khau|rate||Chiết khấu
thue_id|id|FK|Thuế
thanh_tien|money||Thành tiền
sl_da_giao|qty||Đã giao
sl_da_lap_hd|qty||Đã lập hóa đơn
ctkm_id|id|FK|Chương trình khuyến mãi
han_dung_toi_thieu|int||Số ngày còn hạn tối thiểu khách yêu cầu
""")
E('bh', 'KENH_TMDT', 'Sàn thương mại điện tử', 'connector (tùy biến)', 'Kết nối shop trên sàn.', """
id|id|PK|Mã nội bộ
ten_san|enum||Shopee, Lazada, Tiki, TikTok Shop
ma_shop|text|UK|Mã shop trên sàn
doi_tac_id|id|FK|Sàn là đối tác công nợ
lich_dong_bo|text||Chu kỳ lấy đơn
""")
E('bh', 'DON_TMDT', 'Đơn sàn TMĐT', 'connector order (tùy biến)', 'Đơn lấy về từ sàn, nối với đơn bán.', """
id|id|PK|Mã nội bộ
kenh_tmdt_id|id|FK|Shop
ma_don_san|text|UK|Mã đơn trên sàn
don_ban_id|id|FK|Đơn bán tạo ra
phi_san|money||Phí sàn
tien_ve|money||Tiền sàn chuyển về
trang_thai_dong_bo|enum||mới, đã tạo đơn, đã giao, đã đối soát, lỗi
""")

R('bh', 'DOI_TAC', '||--o{', 'CO_HOI', 'cơ hội với')
R('bh', 'GIAI_DOAN_CRM', '||--o{', 'CO_HOI', 'ở giai đoạn')
R('bh', 'NHAN_VIEN', '|o--o{', 'CO_HOI', 'phụ trách')
R('bh', 'CO_HOI', '|o--o{', 'DON_BAN', 'chốt thành')
R('bh', 'DOI_TAC', '||--o{', 'DON_BAN', 'đặt')
R('bh', 'KENH_PHAN_PHOI', '||--o{', 'DON_BAN', 'qua kênh')
R('bh', 'VUNG_BAN_HANG', '||--o{', 'DON_BAN', 'thuộc vùng')
R('bh', 'BANG_GIA', '||--o{', 'DON_BAN', 'áp giá')
R('bh', 'KENH_PHAN_PHOI', '|o--o{', 'BANG_GIA', 'giá cho kênh')
R('bh', 'BANG_GIA', '||--|{', 'DONG_BANG_GIA', 'gồm')
R('bh', 'SAN_PHAM', '||--o{', 'DONG_BANG_GIA', 'giá của')
R('bh', 'DON_BAN', '||--|{', 'DONG_DON_BAN', 'gồm')
R('bh', 'SAN_PHAM', '||--o{', 'DONG_DON_BAN', 'được bán')
R('bh', 'CHUONG_TRINH_KM', '|o--o{', 'DONG_DON_BAN', 'khuyến mãi')
R('bh', 'KHOAN_MUC_CHI_PHI', '|o--o{', 'CHUONG_TRINH_KM', 'trừ ngân sách')
R('bh', 'DON_BAN', '||--o{', 'PHIEU_KHO', 'giao hàng qua')
R('bh', 'DON_BAN', '|o--o{', 'BUT_TOAN', 'lập hóa đơn bán')
R('bh', 'KENH_TMDT', '||--o{', 'DON_TMDT', 'phát sinh')
R('bh', 'DON_TMDT', '||--o|', 'DON_BAN', 'tạo')
R('bh', 'DOI_TAC', '||--o|', 'KENH_TMDT', 'là sàn')
