# Phần 4: Tài sản, bảo trì, đội xe; Nhân sự & lương
from core import E, R, M

M('ts', 'Tài sản, bảo trì & đội xe', 'Accounting: Assets, Maintenance, Fleet', 'GĐ1 (TSCĐ) · GĐ3 (bảo trì, xe)',
  'Ghi tăng tài sản từ chứng từ mua, lịch khấu hao tự động theo tháng hoặc năm, chạy khấu hao cuối kỳ, thanh lý; thiết bị và lịch bảo trì; đội xe, nhiên liệu, bảo dưỡng, chành xe theo vùng MN / MB.')

E('ts', 'LOAI_TAI_SAN', 'Loại tài sản', 'account.asset (model)', 'Máy móc, Xe...; mang tài khoản và thời gian mặc định.', """
id|id|PK|Mã nội bộ
ten|text|UK|Máy móc, Xe
tk_nguyen_gia_id|id|FK|211x
tk_hao_mon_id|id|FK|214x
tk_chi_phi_id|id|FK|627, 641, 642
thoi_gian_mac_dinh|int||Số tháng mặc định
khoan_muc_id|id|FK|Khoản mục nhận chi phí khấu hao
""")
E('ts', 'TAI_SAN_CO_DINH', 'Tài sản cố định', 'account.asset', 'Phần đã làm trong bản chạy thử 4 sheet.', """
id|id|PK|Mã nội bộ
ma|text|UK|Mã tài sản, ví dụ 11222
ten|text||Tên tài sản
loai_id|id|FK|Loại tài sản
cong_ty_id|id|FK|Công ty
kho_id|id|FK|Kho 1, 2, 3
phong_ban_su_dung_id|id|FK|Đơn vị sử dụng
so_ct_ghi_tang|text|UK|GT00001
chung_tu_mua_dv_id|id|FK|Ghi tăng từ chứng từ mua
dong_don_mua_id|id|FK|Ghi tăng từ đơn mua
nguyen_gia|money||Thành tiền lúc mua
ngay_ghi_tang|date||Ngày ghi tăng
ngay_bat_dau_kh|date||Bằng ngày ghi tăng
thoi_gian|int||Thời gian sử dụng
don_vi_thoi_gian|enum||tháng, năm
khong_tinh_kh|bool||Không tính khấu hao
gia_tri_thanh_ly|money||Giá trị thu hồi dự kiến
trang_thai|enum||nháp, đang khấu hao, đã khấu hao hết, đã thanh lý
""")
E('ts', 'LICH_KHAU_HAO', 'Lịch khấu hao', 'account.move (depreciation)', 'Mỗi tháng một dòng; tháng cuối nhận phần làm tròn.', """
id|id|PK|Mã nội bộ
tai_san_id|id|FK|Tài sản
ky_thu|int||1 tới n
ky|month||Tháng
so_tien|money||Khấu hao trong kỳ
luy_ke|money||Hao mòn lũy kế
con_lai|money||Giá trị còn lại
but_toan_id|id|FK|Bút toán khi đã chạy
trang_thai|enum||dự kiến, đã ghi sổ
""")
E('ts', 'THIET_BI', 'Thiết bị', 'maintenance.equipment', 'Máy móc cần bảo trì.', """
id|id|PK|Mã nội bộ
ten|text||Tên thiết bị
tai_san_id|id|FK|Tài sản cố định tương ứng
so_serial|text|UK|Số serial
nguoi_phu_trach_id|id|FK|Người phụ trách
chu_ky_bao_tri|int||Số ngày giữa 2 lần bảo trì
""")
E('ts', 'YEU_CAU_BAO_TRI', 'Yêu cầu bảo trì', 'maintenance.request', 'Bảo trì phòng ngừa hoặc sửa chữa.', """
id|id|PK|Mã nội bộ
thiet_bi_id|id|FK|Thiết bị
loai|enum||phòng ngừa, sửa chữa
ngay_du_kien|date||Ngày dự kiến
phut_dung_may|int||Thời gian dừng máy
chi_phi|money||Chi phí
chung_tu_mua_dv_id|id|FK|Chứng từ thuê ngoài
trang_thai|enum||mới, đang làm, xong
""")
E('ts', 'PHUONG_TIEN', 'Phương tiện', 'fleet.vehicle', 'Xe tải giao hàng.', """
id|id|PK|Mã nội bộ
bien_so|text|UK|Biển số
loai_xe|text||Loại xe
tai_san_id|id|FK|Tài sản cố định
tai_xe_id|id|FK|Tài xế
vung_id|id|FK|Vùng chạy MN, MB
""")
E('ts', 'CHI_PHI_XE', 'Chi phí xe', 'fleet.vehicle.log.services', 'Nhiên liệu, bảo dưỡng, chành xe.', """
id|id|PK|Mã nội bộ
phuong_tien_id|id|FK|Xe
loai|enum||nhiên liệu, bảo dưỡng, chành xe, thuê xe ngoài
ngay|date||Ngày
so_km|int||Số km đồng hồ
so_tien|money||Số tiền
chung_tu_mua_dv_id|id|FK|Chứng từ gốc
khoan_muc_id|id|FK|Ví dụ II.5.1 Nhiên liệu MN
""")

R('ts', 'LOAI_TAI_SAN', '||--o{', 'TAI_SAN_CO_DINH', 'phân loại')
R('ts', 'KHOAN_MUC_CHI_PHI', '|o--o{', 'LOAI_TAI_SAN', 'nhận khấu hao')
R('ts', 'CHUNG_TU_MUA_DV', '|o--o{', 'TAI_SAN_CO_DINH', 'ghi tăng từ')
R('ts', 'DONG_DON_MUA', '|o--o{', 'TAI_SAN_CO_DINH', 'ghi tăng từ')
R('ts', 'PHONG_BAN', '|o--o{', 'TAI_SAN_CO_DINH', 'sử dụng')
R('ts', 'TAI_SAN_CO_DINH', '||--o{', 'LICH_KHAU_HAO', 'khấu hao theo')
R('ts', 'LICH_KHAU_HAO', '|o--o|', 'BUT_TOAN', 'ghi sổ')
R('ts', 'TAI_SAN_CO_DINH', '|o--o{', 'THIET_BI', 'là')
R('ts', 'THIET_BI', '||--o{', 'YEU_CAU_BAO_TRI', 'bảo trì')
R('ts', 'CHUNG_TU_MUA_DV', '|o--o{', 'YEU_CAU_BAO_TRI', 'chi phí thuê ngoài')
R('ts', 'TAI_SAN_CO_DINH', '|o--o|', 'PHUONG_TIEN', 'là')
R('ts', 'NHAN_VIEN', '|o--o{', 'PHUONG_TIEN', 'lái')
R('ts', 'VUNG_BAN_HANG', '|o--o{', 'PHUONG_TIEN', 'chạy vùng')
R('ts', 'PHUONG_TIEN', '||--o{', 'CHI_PHI_XE', 'phát sinh')
R('ts', 'CHUNG_TU_MUA_DV', '|o--o{', 'CHI_PHI_XE', 'chứng từ gốc')
R('ts', 'KHOAN_MUC_CHI_PHI', '|o--o{', 'CHI_PHI_XE', 'phân loại')

# ------------------------------------------------------------------ NHÂN SỰ
M('hr', 'Nhân sự & lương', 'Employees, Attendances, Time Off, Payroll, Expenses', 'GĐ3',
  'Hồ sơ nhân viên, hợp đồng lao động, chấm công theo ca, nghỉ phép, bảng lương có BHXH và thuế TNCN, phân bổ chi phí lương theo khoản mục (Lương trực tiếp nhà máy, Lương khối Back Office), đề nghị thanh toán.')

E('hr', 'NHAN_VIEN', 'Nhân viên', 'hr.employee', 'Hồ sơ nhân sự.', """
id|id|PK|Mã nội bộ
ma|text|UK|Mã nhân viên
ho_ten|text||Họ tên
cong_ty_id|id|FK|Công ty
phong_ban_id|id|FK|Phòng ban
chuc_vu|text||Chức vụ
quan_ly_id|id|FK|Quản lý trực tiếp
ngay_vao_lam|date||Ngày vào làm
khoan_muc_luong_id|id|FK|Khoản mục nhận chi phí lương
trang_thai|enum||đang làm, nghỉ việc
""")
E('hr', 'HOP_DONG_LD', 'Hợp đồng lao động', 'hr.contract', 'Căn cứ tính lương.', """
id|id|PK|Mã nội bộ
nhan_vien_id|id|FK|Nhân viên
loai|enum||thử việc, xác định thời hạn, không thời hạn
luong_co_ban|money||Lương cơ bản
phu_cap|money||Phụ cấp
luong_dong_bh|money||Lương đóng bảo hiểm
tu_ngay|date||Từ ngày
den_ngay|date||Đến ngày
trang_thai|enum||hiệu lực, hết hạn
""")
E('hr', 'CHAM_CONG', 'Chấm công', 'hr.attendance', 'Giờ vào ra theo ca.', """
id|id|PK|Mã nội bộ
nhan_vien_id|id|FK|Nhân viên
ca|text||Ca làm
gio_vao|datetime||Giờ vào
gio_ra|datetime||Giờ ra
so_gio|qty||Số giờ công
""")
E('hr', 'NGHI_PHEP', 'Nghỉ phép', 'hr.leave', 'Đơn nghỉ phép và duyệt.', """
id|id|PK|Mã nội bộ
nhan_vien_id|id|FK|Nhân viên
loai|enum||phép năm, ốm, không lương
tu|datetime||Từ
den|datetime||Đến
so_ngay|qty||Số ngày
trang_thai|enum||chờ duyệt, đã duyệt, từ chối
""")
E('hr', 'BANG_LUONG_KY', 'Bảng lương kỳ', 'hr.payslip.run', 'Bảng lương của một tháng.', """
id|id|PK|Mã nội bộ
cong_ty_id|id|FK|Công ty
ky|month||Tháng
trang_thai|enum||nháp, chờ duyệt, đã duyệt, đã chi
but_toan_id|id|FK|Bút toán lương
""")
E('hr', 'PHIEU_LUONG', 'Phiếu lương', 'hr.payslip', 'Lương của một nhân viên trong kỳ.', """
id|id|PK|Mã nội bộ
bang_luong_id|id|FK|Bảng lương kỳ
nhan_vien_id|id|FK|Nhân viên
hop_dong_id|id|FK|Hợp đồng áp dụng
so_cong|qty||Số công
luong_gop|money||Tổng thu nhập
bhxh_nld|money||Bảo hiểm người lao động đóng
thue_tncn|money||Thuế thu nhập cá nhân
thuc_linh|money||Thực lĩnh
""")
E('hr', 'DONG_PHIEU_LUONG', 'Dòng phiếu lương', 'hr.payslip.line', 'Từng khoản: lương, phụ cấp, BHXH, thuế.', """
id|id|PK|Mã nội bộ
phieu_luong_id|id|FK|Phiếu lương
ma_khoan|text||BASIC, PC, BHXH, TNCN, NET
so_tien|money||Số tiền
tai_khoan_id|id|FK|Tài khoản hạch toán
khoan_muc_id|id|FK|Khoản mục chi phí
""")
E('hr', 'DE_NGHI_THANH_TOAN', 'Đề nghị thanh toán', 'hr.expense', 'Nhân viên ứng hoặc chi hộ.', """
id|id|PK|Mã nội bộ
nhan_vien_id|id|FK|Nhân viên
ngay|date||Ngày chi
mo_ta|text||Nội dung
so_tien|money||Số tiền
khoan_muc_id|id|FK|Khoản mục chi phí
trang_thai|enum||nháp, chờ duyệt, đã duyệt, đã ghi sổ, đã chi
but_toan_id|id|FK|Bút toán
""")

R('hr', 'CONG_TY', '||--o{', 'NHAN_VIEN', 'tuyển')
R('hr', 'PHONG_BAN', '||--o{', 'NHAN_VIEN', 'gồm')
R('hr', 'NHAN_VIEN', '|o--o{', 'NHAN_VIEN', 'quản lý')
R('hr', 'NHAN_VIEN', '||--o{', 'HOP_DONG_LD', 'ký')
R('hr', 'NHAN_VIEN', '||--o{', 'CHAM_CONG', 'chấm')
R('hr', 'NHAN_VIEN', '||--o{', 'NGHI_PHEP', 'xin')
R('hr', 'BANG_LUONG_KY', '||--|{', 'PHIEU_LUONG', 'gồm')
R('hr', 'NHAN_VIEN', '||--o{', 'PHIEU_LUONG', 'nhận')
R('hr', 'HOP_DONG_LD', '||--o{', 'PHIEU_LUONG', 'căn cứ')
R('hr', 'PHIEU_LUONG', '||--|{', 'DONG_PHIEU_LUONG', 'gồm')
R('hr', 'KHOAN_MUC_CHI_PHI', '|o--o{', 'DONG_PHIEU_LUONG', 'nhận chi phí lương')
R('hr', 'BANG_LUONG_KY', '|o--o|', 'BUT_TOAN', 'ghi sổ')
R('hr', 'NHAN_VIEN', '||--o{', 'DE_NGHI_THANH_TOAN', 'đề nghị')
R('hr', 'KHOAN_MUC_CHI_PHI', '|o--o{', 'DE_NGHI_THANH_TOAN', 'phân loại')
R('hr', 'DE_NGHI_THANH_TOAN', '|o--o|', 'BUT_TOAN', 'ghi sổ')
