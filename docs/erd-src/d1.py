# Phần 1: Nền tảng, Kế toán, Khoản mục & ngân sách
from core import E, R, M

M('nen', 'Nền tảng & phân quyền', 'Settings, Discuss, Approvals, Documents, Sign', 'GĐ1',
  'Đa công ty (Văn phòng + Nhà máy), người dùng, nhóm quyền theo đối tượng, luồng duyệt nhiều cấp theo hạn mức tiền, nhật ký thay đổi từng trường, tệp đính kèm, tìm kiếm nhanh toàn hệ thống, chuỗi đánh số chứng từ.')

E('nen', 'CONG_TY', 'Công ty', 'res.company', 'Hai pháp nhân: Văn phòng (MST 1102160036) và Nhà máy (MST 1102021113).', """
id|id|PK|Mã nội bộ
ma|text|UK|Mã công ty: VP, NM
ten|text||Tên pháp nhân
mst|text|UK|Mã số thuế
dia_chi|text||Địa chỉ đăng ký
tien_te_id|id|FK|Tiền tệ hạch toán, VND
cong_ty_me_id|id|FK|Công ty mẹ khi hợp nhất
che_do_ke_toan|enum||TT99 hoặc TT200
""")
E('nen', 'PHONG_BAN', 'Phòng ban', 'hr.department', 'Cây phòng ban, dùng cho phân quyền, ngân sách và chi phí lương.', """
id|id|PK|Mã nội bộ
cong_ty_id|id|FK|Thuộc công ty
ten|text||Tên phòng ban
phong_ban_cha_id|id|FK|Phòng ban cha
truong_phong_id|id|FK|Nhân viên trưởng phòng
khoan_muc_mac_dinh_id|id|FK|Khoản mục chi phí mặc định
""")
E('nen', 'NGUOI_DUNG', 'Người dùng', 'res.users', 'Tài khoản đăng nhập.', """
id|id|PK|Mã nội bộ
ten_dang_nhap|text|UK|Email hoặc tên đăng nhập
mat_khau_bam|text||Mật khẩu đã băm
nhan_vien_id|id|FK|Hồ sơ nhân viên
cong_ty_mac_dinh_id|id|FK|Công ty mở mặc định
cac_cong_ty_duoc_phep|json||Danh sách công ty được truy cập
trang_thai|enum||hoạt động, khóa
lan_dang_nhap_cuoi|datetime||Thời điểm đăng nhập gần nhất
""")
E('nen', 'NHOM_QUYEN', 'Nhóm quyền', 'res.groups', 'Vai trò: Thủ kho, Kế toán viên, Kế toán trưởng, Giám đốc, QA...', """
id|id|PK|Mã nội bộ
ma|text|UK|Mã nhóm
ten|text||Tên hiển thị
phan_he|text||Phân hệ áp dụng
""")
E('nen', 'NGUOI_DUNG_NHOM', 'Người dùng thuộc nhóm', 'res.groups.users_rel', 'Bảng nối nhiều-nhiều.', """
nguoi_dung_id|id|PK, FK|Người dùng
nhom_id|id|PK, FK|Nhóm quyền
""")
E('nen', 'QUYEN_TRUY_CAP', 'Quyền truy cập', 'ir.model.access, ir.rule', 'Quyền đọc, tạo, sửa, xóa theo đối tượng và điều kiện dòng.', """
id|id|PK|Mã nội bộ
nhom_id|id|FK|Nhóm quyền
doi_tuong|text||Tên bảng áp dụng
doc|bool||Được đọc
tao|bool||Được tạo
sua|bool||Được sửa
xoa|bool||Được xóa
sua_sau_khi_cat|bool||Được Sửa chứng từ đã cất
dieu_kien_dong|text||Chỉ thấy dòng thỏa điều kiện, ví dụ theo công ty
""")
E('nen', 'DOI_TAC', 'Đối tác', 'res.partner', 'Khách hàng, nhà phân phối, nhà cung cấp, sàn TMĐT, ngân hàng.', """
id|id|PK|Mã nội bộ
ma|text|UK|Mã đối tác
ten|text||Tên
mst|text||Mã số thuế
loai|enum||công ty, cá nhân
la_khach_hang|bool||Là khách hàng
la_nha_cung_cap|bool||Là nhà cung cấp
doi_tac_cha_id|id|FK|Công ty mẹ của liên hệ hoặc địa chỉ giao
dia_chi|text||Địa chỉ
tinh_thanh|text||Tỉnh thành
dien_thoai|text||Điện thoại
email|text||Email
tk_phai_thu_id|id|FK|TK 131
tk_phai_tra_id|id|FK|TK 331
dieu_khoan_tt_id|id|FK|Điều khoản thanh toán mặc định
han_muc_cong_no|money||Hạn mức tín dụng
bang_gia_id|id|FK|Bảng giá bán mặc định
""")
E('nen', 'TIEN_TE', 'Tiền tệ', 'res.currency', 'VND, USD...', """
id|id|PK|Mã nội bộ
ma|text|UK|VND, USD
ky_hieu|text||đ, $
lam_tron|rate||Đơn vị làm tròn
""")
E('nen', 'TY_GIA', 'Tỷ giá', 'res.currency.rate', 'Tỷ giá theo ngày.', """
id|id|PK|Mã nội bộ
tien_te_id|id|FK|Tiền tệ
ngay|date||Ngày áp dụng
ty_gia|rate||Tỷ giá so với VND
""")
E('nen', 'CHUOI_SO', 'Chuỗi đánh số', 'ir.sequence', 'Cấp số chứng từ tự động: MDV, KH, GT, PO, SO...', """
id|id|PK|Mã nội bộ
ma|text|UK|Mã chuỗi
cong_ty_id|id|FK|Công ty
tien_to|text||MDV, KH, GT, DSMH, PO, SO
so_ke_tiep|int||Số sẽ cấp tiếp
do_dai|int||Số chữ số, ví dụ 5
dat_lai_theo|enum||không, năm, tháng
""")
E('nen', 'NHAT_KY_THAY_DOI', 'Nhật ký thay đổi', 'mail.tracking.value', 'Ai sửa trường nào, giá trị cũ và mới, lúc nào.', """
id|id|PK|Mã nội bộ
doi_tuong|text||Tên bảng
ban_ghi_id|id||Bản ghi bị sửa
truong|text||Tên trường
gia_tri_cu|text||Giá trị cũ
gia_tri_moi|text||Giá trị mới
ly_do|text||Lý do nhập khi sửa
nguoi_dung_id|id|FK|Người sửa
thoi_diem|datetime||Thời điểm
""")
E('nen', 'TEP_DINH_KEM', 'Tệp đính kèm', 'ir.attachment', 'Hóa đơn, hợp đồng, ảnh, XML hóa đơn điện tử.', """
id|id|PK|Mã nội bộ
doi_tuong|text||Tên bảng gắn tệp
ban_ghi_id|id||Bản ghi gắn tệp
ten|text||Tên tệp
duong_dan|text||Nơi lưu tệp
dung_luong|int||Byte
nguoi_tai_id|id|FK|Người tải lên
""")
E('nen', 'QUY_TRINH_DUYET', 'Quy trình duyệt', 'approval.category', 'Quy định chứng từ nào, mức tiền nào phải qua những bước duyệt nào.', """
id|id|PK|Mã nội bộ
ma|text|UK|Mã quy trình
doi_tuong|text||Loại chứng từ áp dụng
cong_ty_id|id|FK|Công ty
so_tien_tu|money||Áp dụng từ mức tiền
so_tien_den|money||Đến mức tiền
dang_dung|bool||Đang áp dụng
""")
E('nen', 'BUOC_DUYET', 'Bước duyệt', 'approval.approver (cấu hình)', 'Thứ tự và người hoặc nhóm duyệt.', """
id|id|PK|Mã nội bộ
quy_trinh_id|id|FK|Quy trình
thu_tu|int||Thứ tự bước
nhom_quyen_id|id|FK|Nhóm được duyệt
nguoi_duyet_id|id|FK|Hoặc người duyệt cụ thể
bat_buoc|bool||Bắt buộc phải duyệt
""")
E('nen', 'YEU_CAU_DUYET', 'Yêu cầu duyệt', 'approval.request', 'Một lần trình duyệt của một chứng từ.', """
id|id|PK|Mã nội bộ
quy_trinh_id|id|FK|Quy trình áp dụng
doi_tuong|text||Loại chứng từ
ban_ghi_id|id||Chứng từ được trình
nguoi_gui_id|id|FK|Người gửi
buoc_hien_tai|int||Bước đang chờ
trang_thai|enum||chờ duyệt, đã duyệt, từ chối, hủy
""")
E('nen', 'LUOT_DUYET', 'Lượt duyệt', 'approval.approver', 'Kết quả của từng người duyệt.', """
id|id|PK|Mã nội bộ
yeu_cau_id|id|FK|Yêu cầu duyệt
buoc_id|id|FK|Bước
nguoi_duyet_id|id|FK|Người duyệt
ket_qua|enum||duyệt, từ chối
y_kien|text||Ý kiến
thoi_diem|datetime||Thời điểm
""")

R('nen', 'CONG_TY', '|o--o{', 'CONG_TY', 'công ty mẹ của')
R('nen', 'CONG_TY', '||--o{', 'PHONG_BAN', 'gồm')
R('nen', 'PHONG_BAN', '|o--o{', 'PHONG_BAN', 'phòng cha của')
R('nen', 'CONG_TY', '||--o{', 'NGUOI_DUNG', 'mặc định của')
R('nen', 'NHAN_VIEN', '|o--o|', 'NGUOI_DUNG', 'đăng nhập bằng')
R('nen', 'NGUOI_DUNG', '||--o{', 'NGUOI_DUNG_NHOM', 'thuộc')
R('nen', 'NHOM_QUYEN', '||--o{', 'NGUOI_DUNG_NHOM', 'gồm')
R('nen', 'NHOM_QUYEN', '||--o{', 'QUYEN_TRUY_CAP', 'được cấp')
R('nen', 'DOI_TAC', '|o--o{', 'DOI_TAC', 'liên hệ, địa chỉ con')
R('nen', 'TIEN_TE', '||--o{', 'TY_GIA', 'có')
R('nen', 'CONG_TY', '||--o{', 'CHUOI_SO', 'sở hữu')
R('nen', 'NGUOI_DUNG', '||--o{', 'NHAT_KY_THAY_DOI', 'thực hiện')
R('nen', 'NGUOI_DUNG', '||--o{', 'TEP_DINH_KEM', 'tải lên')
R('nen', 'QUY_TRINH_DUYET', '||--|{', 'BUOC_DUYET', 'gồm')
R('nen', 'QUY_TRINH_DUYET', '||--o{', 'YEU_CAU_DUYET', 'áp cho')
R('nen', 'YEU_CAU_DUYET', '||--o{', 'LUOT_DUYET', 'có')
R('nen', 'BUOC_DUYET', '||--o{', 'LUOT_DUYET', 'ở bước')
R('nen', 'NHOM_QUYEN', '|o--o{', 'BUOC_DUYET', 'duyệt bởi')
R('nen', 'NGUOI_DUNG', '||--o{', 'LUOT_DUYET', 'duyệt')
R('nen', 'NGUOI_DUNG', '||--o{', 'YEU_CAU_DUYET', 'gửi')

# ------------------------------------------------------------------ KẾ TOÁN
M('kt', 'Kế toán & báo cáo', 'Accounting, Invoicing, Consolidation, Spreadsheet', 'GĐ1',
  'Hệ thống tài khoản TT99, sổ nhật ký, bút toán tự động từ mọi phân hệ, thuế GTGT, hóa đơn điện tử, công nợ, thanh toán, đối soát ngân hàng, khóa sổ kỳ, kết chuyển, báo cáo tài chính B01–B03, sổ chi tiết có drill-down, chốt báo cáo, hợp nhất 2 pháp nhân.')

E('kt', 'HE_THONG_TAI_KHOAN', 'Hệ thống tài khoản', 'account.account', 'Danh mục tài khoản theo TT99, có cấp cha con.', """
id|id|PK|Mã nội bộ
cong_ty_id|id|FK|Công ty
so_tk|text|UK|Số tài khoản, ví dụ 6277
ten|text||Tên tài khoản
loai|enum||tài sản, nợ phải trả, vốn, doanh thu, chi phí
tk_cha_id|id|FK|Tài khoản cấp trên
cho_phep_hach_toan|bool||Tài khoản chi tiết được hạch toán
theo_doi_doi_tuong|bool||Bắt buộc có đối tác
""")
E('kt', 'SO_NHAT_KY', 'Sổ nhật ký', 'account.journal', 'Mua hàng, bán hàng, tiền mặt, ngân hàng, tổng hợp, khấu hao.', """
id|id|PK|Mã nội bộ
cong_ty_id|id|FK|Công ty
ma|text|UK|Mã sổ
ten|text||Tên sổ
loai|enum||mua, bán, tiền mặt, ngân hàng, tổng hợp
chuoi_so_id|id|FK|Chuỗi đánh số
tk_mac_dinh_id|id|FK|Tài khoản mặc định
""")
E('kt', 'KY_KE_TOAN', 'Kỳ kế toán', 'account.lock_date', 'Tháng kế toán và trạng thái khóa.', """
id|id|PK|Mã nội bộ
cong_ty_id|id|FK|Công ty
nam|int||Năm
thang|int||Tháng
trang_thai|enum||mở, đang khóa sổ, đã khóa
ngay_khoa|datetime||Thời điểm khóa
nguoi_khoa_id|id|FK|Người khóa
""")
E('kt', 'BUT_TOAN', 'Bút toán', 'account.move', 'Chứng từ ghi sổ. Mọi nghiệp vụ tài chính đều sinh bút toán.', """
id|id|PK|Mã nội bộ
so_ct|text|UK|Số bút toán
cong_ty_id|id|FK|Công ty
so_nhat_ky_id|id|FK|Sổ nhật ký
ky_id|id|FK|Kỳ kế toán
ngay_hach_toan|date||Ngày hạch toán
ngay_chung_tu|date||Ngày chứng từ
doi_tac_id|id|FK|Đối tác
loai|enum||hóa đơn mua, hóa đơn bán, chi phí, khấu hao, lương, điều chỉnh, tổng hợp
nguon_doi_tuong|text||Chứng từ gốc sinh ra bút toán
nguon_id|id||Mã chứng từ gốc
trang_thai|enum||nháp, đã ghi sổ, đã hủy
but_toan_dao_id|id|FK|Bút toán đảo khi hủy
dien_giai|text||Diễn giải
""")
E('kt', 'DONG_BUT_TOAN', 'Dòng bút toán', 'account.move.line', 'Một vế nợ hoặc có. Nguồn dữ liệu của mọi báo cáo.', """
id|id|PK|Mã nội bộ
but_toan_id|id|FK|Bút toán
tai_khoan_id|id|FK|Tài khoản
doi_tac_id|id|FK|Đối tác
no|money||Phát sinh nợ
co|money||Phát sinh có
tien_te_id|id|FK|Tiền tệ gốc
so_tien_nguyen_te|money||Số tiền nguyên tệ
khoan_muc_id|id|FK|Khoản mục chi phí
thue_id|id|FK|Thuế sinh ra dòng này
han_thanh_toan|date||Hạn thanh toán
da_doi_tru|bool||Đã đối trừ hết
""")
E('kt', 'THUE', 'Thuế', 'account.tax', 'Thuế GTGT đầu vào, đầu ra.', """
id|id|PK|Mã nội bộ
ma|text|UK|Mã thuế
ten|text||GTGT 8% đầu vào...
loai|enum||mua, bán
ty_le|rate||0, 5, 8, 10
tk_thue_id|id|FK|1331 hoặc 33311
""")
E('kt', 'DIEU_KHOAN_TT', 'Điều khoản thanh toán', 'account.payment.term', 'Số ngày được nợ, chiết khấu thanh toán sớm.', """
id|id|PK|Mã nội bộ
ten|text||Ví dụ Nợ 30 ngày
so_ngay|int||Số ngày được nợ
chiet_khau_som|rate||Phần trăm chiết khấu nếu trả sớm
""")
E('kt', 'THANH_TOAN', 'Thanh toán', 'account.payment', 'Phiếu thu, phiếu chi, ủy nhiệm chi.', """
id|id|PK|Mã nội bộ
so_ct|text|UK|Số phiếu
loai|enum||thu, chi
doi_tac_id|id|FK|Đối tác
so_nhat_ky_id|id|FK|Sổ tiền mặt hoặc ngân hàng
so_tien|money||Số tiền
ngay|date||Ngày
phuong_thuc|enum||tiền mặt, chuyển khoản, séc
but_toan_id|id|FK|Bút toán sinh ra
trang_thai|enum||nháp, đã ghi sổ, đã đối soát
""")
E('kt', 'DOI_TRU_CONG_NO', 'Đối trừ công nợ', 'account.partial.reconcile', 'Nối dòng hóa đơn với dòng thanh toán.', """
id|id|PK|Mã nội bộ
dong_no_id|id|FK|Dòng bên nợ
dong_co_id|id|FK|Dòng bên có
so_tien|money||Số tiền đối trừ
ngay|date||Ngày đối trừ
""")
E('kt', 'SAO_KE_NGAN_HANG', 'Sao kê ngân hàng', 'account.bank.statement', 'Sao kê nhập tệp hoặc đồng bộ.', """
id|id|PK|Mã nội bộ
so_nhat_ky_id|id|FK|Tài khoản ngân hàng
ngay|date||Ngày sao kê
so_du_dau|money||Số dư đầu
so_du_cuoi|money||Số dư cuối
""")
E('kt', 'DONG_SAO_KE', 'Dòng sao kê', 'account.bank.statement.line', 'Một giao dịch ngân hàng.', """
id|id|PK|Mã nội bộ
sao_ke_id|id|FK|Sao kê
ngay|date||Ngày giao dịch
noi_dung|text||Nội dung chuyển khoản
so_tien|money||Số tiền, âm là chi
doi_tac_id|id|FK|Đối tác nhận diện được
dong_but_toan_id|id|FK|Dòng bút toán đã đối soát
""")
E('kt', 'HOA_DON_DIEN_TU', 'Hóa đơn điện tử', 'l10n_vn_edi', 'Thông tin phát hành và cấp mã cơ quan thuế.', """
id|id|PK|Mã nội bộ
but_toan_id|id|FK|Hóa đơn bán gốc
ky_hieu|text||Ký hiệu hóa đơn
so_hd|text|UK|Số hóa đơn
ma_cqt|text||Mã cơ quan thuế
ma_tra_cuu|text||Mã tra cứu
trang_thai|enum||chờ gửi, đã cấp mã, bị từ chối, đã thay thế
tep_xml_id|id|FK|Tệp XML
""")
E('kt', 'MAU_BAO_CAO', 'Mẫu báo cáo', 'account.report', 'B01-DN, B02-DN, B03-DN, Phân tích chi phí nhiều kỳ, Lãi gộp theo nhãn hàng...', """
id|id|PK|Mã nội bộ
ma|text|UK|Mã báo cáo
ten|text||Tên báo cáo
cong_ty_id|id|FK|Công ty, trống là dùng chung
""")
E('kt', 'CHI_TIEU_BAO_CAO', 'Chỉ tiêu báo cáo', 'account.report.line', 'Dòng báo cáo có công thức, dạng cây Mã số II, II.1, II.1.1.', """
id|id|PK|Mã nội bộ
mau_id|id|FK|Mẫu báo cáo
ma_so|text||Mã số, ví dụ II.1.1
ten|text||Chỉ tiêu
cong_thuc|text||Tài khoản, khoản mục hoặc tổng các chỉ tiêu
chi_tieu_cha_id|id|FK|Chỉ tiêu cha
thu_tu|int||Thứ tự
""")
E('kt', 'BAO_CAO_CHOT', 'Báo cáo đã chốt', 'account.report (bản lưu)', 'Ảnh chụp số liệu báo cáo tại thời điểm chốt; không đổi dù dữ liệu gốc sửa sau.', """
id|id|PK|Mã nội bộ
mau_id|id|FK|Mẫu báo cáo
cong_ty_id|id|FK|Công ty
ky_tu|month||Từ kỳ
ky_den|month||Đến kỳ
ngay_chot|datetime||Thời điểm chốt
nguoi_chot_id|id|FK|Người chốt
trang_thai|enum||đã chốt, đã hủy chốt
""")
E('kt', 'GIA_TRI_BAO_CAO_CHOT', 'Giá trị báo cáo đã chốt', 'account.report.external.value', 'Giá trị từng chỉ tiêu từng kỳ của bản chốt.', """
bao_cao_chot_id|id|PK, FK|Báo cáo đã chốt
chi_tieu_id|id|PK, FK|Chỉ tiêu
ky|month|PK|Kỳ
gia_tri|money||Giá trị
""")
E('kt', 'GIAO_DICH_NOI_BO', 'Giao dịch nội bộ', 'inter-company rules', 'Mua bán giữa Nhà máy và Văn phòng, dùng để loại trừ khi hợp nhất.', """
id|id|PK|Mã nội bộ
cong_ty_ban_id|id|FK|Công ty bán
cong_ty_mua_id|id|FK|Công ty mua
but_toan_ban_id|id|FK|Hóa đơn bán
but_toan_mua_id|id|FK|Hóa đơn mua tương ứng
so_tien|money||Giá trị
da_loai_tru|bool||Đã loại trừ ở kỳ hợp nhất
""")

R('kt', 'CONG_TY', '||--o{', 'HE_THONG_TAI_KHOAN', 'dùng')
R('kt', 'HE_THONG_TAI_KHOAN', '|o--o{', 'HE_THONG_TAI_KHOAN', 'tài khoản cha của')
R('kt', 'CONG_TY', '||--o{', 'SO_NHAT_KY', 'có')
R('kt', 'CHUOI_SO', '||--o{', 'SO_NHAT_KY', 'đánh số')
R('kt', 'CONG_TY', '||--o{', 'KY_KE_TOAN', 'có')
R('kt', 'SO_NHAT_KY', '||--o{', 'BUT_TOAN', 'ghi')
R('kt', 'KY_KE_TOAN', '||--o{', 'BUT_TOAN', 'thuộc kỳ')
R('kt', 'DOI_TAC', '|o--o{', 'BUT_TOAN', 'đối tượng')
R('kt', 'BUT_TOAN', '|o--o|', 'BUT_TOAN', 'đảo của')
R('kt', 'BUT_TOAN', '||--|{', 'DONG_BUT_TOAN', 'gồm')
R('kt', 'HE_THONG_TAI_KHOAN', '||--o{', 'DONG_BUT_TOAN', 'hạch toán vào')
R('kt', 'KHOAN_MUC_CHI_PHI', '|o--o{', 'DONG_BUT_TOAN', 'phân tích theo')
R('kt', 'THUE', '|o--o{', 'DONG_BUT_TOAN', 'sinh ra')
R('kt', 'HE_THONG_TAI_KHOAN', '||--o{', 'THUE', 'TK thuế')
R('kt', 'DIEU_KHOAN_TT', '|o--o{', 'DOI_TAC', 'mặc định')
R('kt', 'DOI_TAC', '|o--o{', 'THANH_TOAN', 'nhận hoặc trả')
R('kt', 'THANH_TOAN', '||--||', 'BUT_TOAN', 'sinh')
R('kt', 'DONG_BUT_TOAN', '||--o{', 'DOI_TRU_CONG_NO', 'được đối trừ')
R('kt', 'SO_NHAT_KY', '||--o{', 'SAO_KE_NGAN_HANG', 'của')
R('kt', 'SAO_KE_NGAN_HANG', '||--|{', 'DONG_SAO_KE', 'gồm')
R('kt', 'DONG_SAO_KE', '|o--o|', 'DONG_BUT_TOAN', 'đối soát với')
R('kt', 'BUT_TOAN', '||--o|', 'HOA_DON_DIEN_TU', 'phát hành')
R('kt', 'MAU_BAO_CAO', '||--|{', 'CHI_TIEU_BAO_CAO', 'gồm')
R('kt', 'CHI_TIEU_BAO_CAO', '|o--o{', 'CHI_TIEU_BAO_CAO', 'chỉ tiêu cha của')
R('kt', 'MAU_BAO_CAO', '||--o{', 'BAO_CAO_CHOT', 'chốt thành')
R('kt', 'BAO_CAO_CHOT', '||--|{', 'GIA_TRI_BAO_CAO_CHOT', 'lưu')
R('kt', 'CHI_TIEU_BAO_CAO', '||--o{', 'GIA_TRI_BAO_CAO_CHOT', 'giá trị của')
R('kt', 'KY_KE_TOAN', '||--o{', 'BAO_CAO_CHOT', 'chốt ở kỳ')
R('kt', 'CONG_TY', '||--o{', 'GIAO_DICH_NOI_BO', 'bán nội bộ')
R('kt', 'BUT_TOAN', '||--o{', 'GIAO_DICH_NOI_BO', 'ghi nhận')

# ------------------------------------------------------------ KHOẢN MỤC & NGÂN SÁCH
M('ns', 'Khoản mục chi phí & ngân sách', 'Accounting: Analytic, Budget', 'GĐ1',
  'Cây khoản mục cụ – ông – cha – con, gắn tài khoản, ngân sách theo tháng, phân bổ 2 chiều tự động (sửa cha chia xuống, sửa con cộng lên), khóa khoản, cảnh báo vượt ngân sách, so sánh kế hoạch với thực tế.')

E('ns', 'KHOAN_MUC_CHI_PHI', 'Khoản mục chi phí', 'account.analytic.account', 'Cây cụ – ông – cha – con, trục của báo cáo chi phí và ngân sách.', """
id|id|PK|Mã nội bộ
cong_ty_id|id|FK|Công ty
ma_so|text|UK|Mã số, ví dụ II.1.1
ten|text||Chỉ tiêu, ví dụ Chi phí điện
cap|int||1 cụ, 2 ông, 3 cha, 4 con
khoan_muc_cha_id|id|FK|Khoản cha
dang_dung|bool||Còn sử dụng
""")
E('ns', 'KHOAN_MUC_TAI_KHOAN', 'Tài khoản của khoản mục', 'analytic distribution model', 'Khoản mục được phép đi với tài khoản nào, ví dụ II.5 với 6417, 64188, 6427.', """
khoan_muc_id|id|PK, FK|Khoản mục
tai_khoan_id|id|PK, FK|Tài khoản
""")
E('ns', 'NGAN_SACH', 'Ngân sách', 'budget.analytic', 'Một bộ ngân sách năm, có phiên bản và duyệt.', """
id|id|PK|Mã nội bộ
cong_ty_id|id|FK|Công ty
ma|text|UK|Mã ngân sách
ten|text||Ví dụ Ngân sách 2027
nam|int||Năm
phien_ban|int||Lần lập lại
trang_thai|enum||nháp, chờ duyệt, đã duyệt, đã khóa
nguoi_lap_id|id|FK|Người lập
""")
E('ns', 'DONG_NGAN_SACH', 'Dòng ngân sách', 'budget.line', 'Số kế hoạch của một khoản mục trong một tháng.', """
id|id|PK|Mã nội bộ
ngan_sach_id|id|FK|Ngân sách
khoan_muc_id|id|FK|Khoản mục
ky|month||Tháng
so_ke_hoach|money||Số kế hoạch
khoa_phan_bo|bool||Giữ nguyên khi khoản cha phân bổ lại
phuong_thuc|enum||theo tỷ trọng, chia đều, cố định
""")
E('ns', 'LICH_SU_PHAN_BO', 'Lịch sử phân bổ', 'mail.tracking (mở rộng)', 'Mỗi lần sửa một ô và các ô bị tự động thay đổi theo.', """
id|id|PK|Mã nội bộ
dong_ngan_sach_id|id|FK|Ô được sửa
quy_tac_id|id|FK|Quy tắc tự động đã áp
gia_tri_cu|money||Giá trị cũ
gia_tri_moi|money||Giá trị mới
chieu|enum||chia xuống, cộng lên
cac_o_anh_huong|json||Danh sách ô bị đổi và giá trị mới
nguoi_dung_id|id|FK|Người sửa
thoi_diem|datetime||Thời điểm
""")
E('ns', 'QUY_TAC_TU_DONG', 'Quy tắc tự động', 'base.automation (tùy biến)', 'Cấu hình cách hệ thống tự tính lại khi người dùng sửa một con số.', """
id|id|PK|Mã nội bộ
pham_vi|enum||chứng từ mua dịch vụ, ngân sách
ten|text||Tên quy tắc
kich_hoat|enum||sửa tổng, sửa thành tiền, sửa SL hoặc đơn giá, đổi khoản mục
phuong_thuc|enum||theo tỷ trọng, chia đều, theo định mức
lam_tron|int||Làm tròn tới đồng
nhan_so_du|enum||dòng có phần lẻ lớn nhất, dòng cuối
ton_trong_khoa|bool||Bỏ qua dòng hoặc khoản đang khóa
dang_dung|bool||Đang bật
""")

R('ns', 'CONG_TY', '||--o{', 'KHOAN_MUC_CHI_PHI', 'dùng')
R('ns', 'KHOAN_MUC_CHI_PHI', '|o--o{', 'KHOAN_MUC_CHI_PHI', 'cụ, ông, cha của')
R('ns', 'KHOAN_MUC_CHI_PHI', '||--o{', 'KHOAN_MUC_TAI_KHOAN', 'gắn')
R('ns', 'HE_THONG_TAI_KHOAN', '||--o{', 'KHOAN_MUC_TAI_KHOAN', 'thuộc')
R('ns', 'CONG_TY', '||--o{', 'NGAN_SACH', 'lập')
R('ns', 'NGAN_SACH', '||--|{', 'DONG_NGAN_SACH', 'gồm')
R('ns', 'KHOAN_MUC_CHI_PHI', '||--o{', 'DONG_NGAN_SACH', 'kế hoạch cho')
R('ns', 'DONG_NGAN_SACH', '||--o{', 'LICH_SU_PHAN_BO', 'ghi lịch sử')
R('ns', 'NGUOI_DUNG', '||--o{', 'LICH_SU_PHAN_BO', 'thực hiện')
R('ns', 'QUY_TAC_TU_DONG', '||--o{', 'LICH_SU_PHAN_BO', 'áp dụng')

# ------------------------------------------------------------ CẤU HÌNH PHÁP LÝ
M('ch', 'Cấu hình pháp lý', 'Settings + tùy biến (Odoo không có sẵn cho Việt Nam)', 'GĐ1',
  'Mọi thuế suất, mức giảm trừ, lương tối thiểu vùng, lương cơ sở, tỷ lệ bảo hiểm, giới hạn làm thêm, ngưỡng tài sản, lịch nghỉ lễ lưu thành tham số có ngày hiệu lực và văn bản căn cứ; cập nhật có duyệt, mô phỏng trước khi áp dụng, không cần sửa code.')

E('ch', 'VAN_BAN_PHAP_LY', 'Văn bản pháp lý', 'mới (tùy biến)', 'Luật, nghị quyết, nghị định, thông tư làm căn cứ cho tham số.', """
id|id|PK|Mã nội bộ
so_hieu|text|UK|Ví dụ 293/2025/NĐ-CP
loai|enum||luật, nghị quyết, nghị định, thông tư, công văn
trich_yeu|text||Trích yếu
ngay_ban_hanh|date||Ngày ban hành
ngay_hieu_luc|date||Ngày có hiệu lực
ngay_het_hieu_luc|date||Ngày hết hiệu lực nếu có
van_ban_thay_the_id|id|FK|Văn bản bị thay thế
tep_id|id|FK|Tệp văn bản đính kèm
""")
E('ch', 'THAM_SO_PHAP_LY', 'Tham số pháp lý', 'mới (tùy biến)', 'Định nghĩa một tham số: ví dụ LUONG_CO_SO, GTGT_GIAM, TNCN_GIAM_TRU_BAN_THAN.', """
id|id|PK|Mã nội bộ
ma|text|UK|Mã tham số dùng trong công thức
ten|text||Tên hiển thị
nhom|enum||thuế GTGT, thuế TNDN, thuế TNCN, lương, bảo hiểm, lao động, kế toán, hóa đơn
kieu|enum||tiền, tỷ lệ, số, bảng bậc, danh sách, ngày
don_vi|text||đồng, phần trăm, giờ, lần
pham_vi|enum||toàn quốc, theo công ty, theo địa bàn, theo nhóm hàng
mo_ta|text||Dùng ở nghiệp vụ nào
""")
E('ch', 'GIA_TRI_THAM_SO', 'Giá trị tham số theo hiệu lực', 'mới (tùy biến)', 'Mỗi lần luật đổi thêm một dòng; không sửa đè dòng cũ đã dùng để tính.', """
id|id|PK|Mã nội bộ
tham_so_id|id|FK|Tham số
cong_ty_id|id|FK|Trống là áp dụng mọi công ty
dia_ban_id|id|FK|Chỉ dùng khi tham số theo địa bàn
gia_tri_so|money||Giá trị dạng số, tiền hoặc tỷ lệ
gia_tri_json|json||Giá trị dạng danh sách
hieu_luc_tu|date||Áp dụng từ ngày
hieu_luc_den|date||Áp dụng đến ngày, trống là chưa hết
van_ban_id|id|FK|Văn bản căn cứ
trang_thai|enum||nháp, chờ duyệt, đang áp dụng, đã hết hiệu lực
nguoi_nhap_id|id|FK|Người nhập
nguoi_duyet_id|id|FK|Kế toán trưởng duyệt
ghi_chu|text||Ghi chú, điểm cần xác nhận
""")
E('ch', 'BAC_LUY_TIEN', 'Bậc lũy tiến', 'mới (tùy biến)', 'Các bậc của một giá trị dạng bảng bậc, ví dụ biểu thuế TNCN 5 bậc.', """
id|id|PK|Mã nội bộ
gia_tri_id|id|FK|Giá trị tham số
thu_tu|int||Bậc 1, 2, 3...
tu|money||Từ mức
den|money||Đến mức, trống là không giới hạn
ty_le|rate||Thuế suất hoặc tỷ lệ của bậc
""")
E('ch', 'DIA_BAN_VUNG', 'Địa bàn và vùng lương', 'mới (tùy biến)', 'Xã, phường sau sắp xếp địa giới và vùng lương tối thiểu.', """
id|id|PK|Mã nội bộ
tinh|text||Tỉnh, thành phố
xa_phuong|text||Xã, phường
vung|enum||I, II, III, IV
hieu_luc_tu|date||Áp dụng từ ngày
van_ban_id|id|FK|Văn bản căn cứ
""")
E('ch', 'NGAY_LE_NGHI', 'Lịch nghỉ lễ và ngày làm việc', 'resource.calendar.leaves', 'Ngày lễ Tết, nghỉ bù, làm bù theo từng năm.', """
id|id|PK|Mã nội bộ
nam|int||Năm
ngay|date||Ngày
loai|enum||lễ Tết, nghỉ bù, làm bù
ten|text||Ví dụ Giỗ Tổ Hùng Vương
he_so_lam_them|rate||300% với ngày lễ
van_ban_id|id|FK|Thông báo lịch nghỉ
""")
E('ch', 'MO_PHONG_THAM_SO', 'Lần mô phỏng tham số', 'mới (tùy biến)', 'Tính thử kết quả với giá trị nháp trước khi duyệt.', """
id|id|PK|Mã nội bộ
gia_tri_id|id|FK|Giá trị nháp đem thử
pham_vi|enum||bảng lương, tờ khai GTGT, quyết toán TNCN, khấu hao
ky|month||Kỳ đem tính thử
chenh_lech|json||Các dòng thay đổi và số tiền chênh lệch
nguoi_chay_id|id|FK|Người chạy
thoi_diem|datetime||Thời điểm
""")

R('ch', 'THAM_SO_PHAP_LY', '||--o{', 'GIA_TRI_THAM_SO', 'có các mức theo thời gian')
R('ch', 'VAN_BAN_PHAP_LY', '||--o{', 'GIA_TRI_THAM_SO', 'là căn cứ của')
R('ch', 'VAN_BAN_PHAP_LY', '|o--o{', 'VAN_BAN_PHAP_LY', 'thay thế')
R('ch', 'GIA_TRI_THAM_SO', '||--o{', 'BAC_LUY_TIEN', 'gồm các bậc')
R('ch', 'DIA_BAN_VUNG', '|o--o{', 'GIA_TRI_THAM_SO', 'áp dụng cho')
R('ch', 'VAN_BAN_PHAP_LY', '||--o{', 'DIA_BAN_VUNG', 'quy định vùng')
R('ch', 'VAN_BAN_PHAP_LY', '|o--o{', 'NGAY_LE_NGHI', 'thông báo')
R('ch', 'GIA_TRI_THAM_SO', '||--o{', 'MO_PHONG_THAM_SO', 'được tính thử')
R('ch', 'CONG_TY', '|o--o{', 'GIA_TRI_THAM_SO', 'riêng cho')
R('ch', 'NGUOI_DUNG', '||--o{', 'GIA_TRI_THAM_SO', 'nhập, duyệt')
R('ch', 'GIA_TRI_THAM_SO', '|o--o{', 'THUE', 'quy định thuế suất')
R('ch', 'GIA_TRI_THAM_SO', '|o--o{', 'PHIEU_LUONG', 'dùng để tính')
