from markupsafe import Markup, escape

from odoo import api, fields, models

# (nhóm, quyền, nhân viên, kế toán viên, kế toán trưởng, giám đốc, R&D, quản trị)
MATRIX = [
    ('Chứng từ', 'Xem chứng từ', 0, 1, 1, 1, 0, 1),
    ('Chứng từ', 'Thêm chứng từ, sửa chứng từ nháp', 0, 1, 1, 0, 0, 1),
    ('Chứng từ', 'Cất chứng từ', 0, 1, 1, 0, 0, 1),
    ('Chứng từ', 'Duyệt, trả lại chứng từ vượt hạn mức', 0, 0, 1, 1, 0, 1),
    ('Chứng từ', 'Sửa chứng từ đã cất (tạo phiên bản)', 0, 0, 1, 0, 0, 1),
    ('Chứng từ', 'Sửa tổng, tự phân bổ các dòng', 0, 1, 1, 0, 0, 1),
    ('Chứng từ', 'Điều chỉnh hàng loạt, hoàn tác lô', 0, 0, 1, 0, 0, 1),
    ('Chứng từ', 'Khôi phục số gốc, đưa sửa đổi vào báo cáo', 0, 0, 1, 0, 0, 1),
    ('Chứng từ', 'Hủy chứng từ', 0, 0, 1, 0, 0, 1),
    ('Chứng từ', 'Xóa chứng từ nháp', 0, 1, 1, 0, 0, 1),
    ('Chứng từ', 'Xóa chứng từ đã hủy chưa từng ghi sổ', 0, 0, 0, 0, 0, 1),
    ('Tài sản', 'Xem tài sản, lịch và chứng từ khấu hao', 0, 1, 1, 1, 0, 1),
    ('Tài sản', 'Ghi tăng, hủy ghi tăng khi chưa khấu hao', 0, 1, 1, 0, 0, 1),
    ('Tài sản', 'Tính và ghi sổ khấu hao tháng', 0, 1, 1, 0, 0, 1),
    ('Tài sản', 'Hủy chứng từ khấu hao, thanh lý tài sản', 0, 0, 1, 0, 0, 1),
    ('Tài sản', 'Sửa loại tài sản, khung thời gian khấu hao', 0, 0, 1, 0, 0, 1),
    ('Sổ kế toán', 'Lập, ghi sổ phiếu thu chi, phiếu kế toán, số dư đầu kỳ', 0, 1, 1, 0, 0, 1),
    ('Sổ kế toán', 'Hủy phiếu thu chi, đảo bút toán', 0, 0, 1, 0, 0, 1),
    ('Sổ kế toán', 'Kết chuyển cuối kỳ, khóa và mở khóa sổ', 0, 0, 1, 0, 0, 1),
    ('Sổ kế toán', 'Xem sổ cái, sổ nhật ký chung, cân đối phát sinh, công nợ, B01, B02', 0, 1, 1, 1, 0, 1),
    ('Sổ kế toán', 'Mở tài khoản chi tiết', 0, 0, 1, 0, 0, 1),
    ('Thuế', 'Lập tờ khai GTGT, lấy bảng kê, sửa nhóm hàng bán ra', 0, 1, 1, 0, 0, 1),
    ('Thuế', 'Xác nhận, hủy xác nhận tờ khai; sửa điều kiện khấu trừ', 0, 0, 1, 0, 0, 1),
    ('Thuế', 'Xem tờ khai và bảng kê', 0, 1, 1, 1, 0, 1),
    ('Bán hàng', 'Ghi nhận hóa đơn bán ra, hàng bán trả lại, giảm giá', 0, 1, 1, 0, 0, 1),
    ('Bán hàng', 'Hủy hóa đơn bán ra đã ghi sổ', 0, 0, 1, 0, 0, 1),
    ('Kho', 'Lập, ghi phiếu nhập, xuất, chuyển kho, kiểm kê; khai báo hàng hóa, lô', 0, 1, 1, 0, 0, 1),
    ('Kho', 'Hủy phiếu kho đã ghi; khai báo kho', 0, 0, 1, 0, 0, 1),
    ('Báo cáo', 'Xem tuổi nợ, nhập xuất tồn, hàng sắp hết hạn, B03', 0, 1, 1, 1, 0, 1),
    ('Tiền lương', 'Hồ sơ nhân viên, lập và tính bảng lương, chi lương', 0, 1, 1, 0, 0, 1),
    ('Tiền lương', 'Ghi sổ, hủy ghi sổ bảng lương; sửa khoản lương', 0, 0, 1, 0, 0, 1),
    ('Tiền lương', 'Xem bảng lương, tổng hợp thuế TNCN, bảo hiểm', 0, 1, 1, 1, 0, 1),
    ('Báo cáo', 'Xem báo cáo phân tích chi phí', 0, 1, 1, 1, 0, 1),
    ('Báo cáo', 'Xuất Excel, CSV', 0, 1, 1, 1, 0, 1),
    ('Danh mục', 'Thêm, sửa, xóa nhà cung cấp', 0, 1, 1, 0, 0, 1),
    ('Danh mục', 'Thêm, sửa, xóa khoản mục chi phí', 0, 0, 1, 0, 0, 1),
    ('Cấu hình', 'Thêm mức tham số pháp lý', 0, 1, 1, 0, 0, 1),
    ('Cấu hình', 'Duyệt tham số pháp lý', 0, 0, 1, 0, 0, 1),
    ('Cấu hình', 'Thuế suất GTGT', 0, 0, 1, 0, 0, 1),
    ('Cấu hình', 'Hạn mức duyệt, số ngày được sửa', 0, 0, 1, 0, 0, 1),
    ('Kiểm soát', 'Xem nhật ký hệ thống, kiểm tra toàn vẹn', 0, 0, 1, 1, 0, 1),
    ('R&D', 'Dự án, công thức, mẫu thử R&D (phân hệ R&D, giai đoạn sau)', 0, 0, 0, 1, 1, 1),
    ('Quản trị', 'Thêm, sửa, ngừng hoạt động người dùng; đổi mật khẩu', 0, 0, 0, 0, 0, 1),
    ('Quản trị', 'Gán vai trò, phân quyền, cấu hình nâng cao Odoo', 0, 0, 0, 0, 0, 1),
    ('Quản trị', 'Thêm, sửa pháp nhân', 0, 0, 0, 0, 0, 1),
    ('Quản trị', 'Sao lưu ngay, kiểm tra, tải về, xóa bản sao lưu', 0, 0, 0, 0, 0, 1),
    ('Không ai được', 'Sửa hoặc xóa nhật ký hệ thống', 0, 0, 0, 0, 0, 0),
    ('Không ai được', 'Sửa, xóa bút toán đã ghi sổ; ghi sổ vào kỳ đã khóa', 0, 0, 0, 0, 0, 0),
    ('Không ai được', 'Sửa phiên bản chứng từ đã lưu, sửa mức tham số đã duyệt', 0, 0, 0, 0, 0, 0),
]


class LfoodRoleMatrix(models.TransientModel):
    _name = 'lfood.role.matrix'
    _description = 'Ma trận phân quyền'

    html = fields.Html('Ma trận', compute='_compute_html', sanitize=False)

    @api.depends_context('uid')
    def _compute_html(self):
        head = Markup('<tr><th>Nhóm</th><th>Quyền</th><th>Nhân viên</th><th>Kế toán viên</th>'
                      '<th>Kế toán trưởng</th><th>Giám đốc</th><th>R&amp;D</th><th>Quản trị</th></tr>')
        rows = Markup('').join(
            Markup('<tr><td>%s</td><td>%s</td>%s</tr>') % (
                escape(g), escape(p),
                Markup('').join(Markup('<td style="text-align:center">%s</td>') % ('Có' if v else '—') for v in vals))
            for g, p, *vals in MATRIX)
        for rec in self:
            rec.html = Markup('<div class="o_lfood_changes"><table>%s%s</table></div>') % (head, rows)
