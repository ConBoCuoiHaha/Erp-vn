"""Dữ liệu mẫu để chạy thử: người dùng theo vai trò, nhà cung cấp, chứng từ.
Số liệu chứng từ MDV00433 lấy theo ảnh chụp MISA công ty đã gửi."""
from datetime import date


def post_init_demo(env):
    env = env(context=dict(env.context, lfood_audit_skip=True, tracking_disable=True))
    ref = env.ref
    companies = ref('base.main_company') | ref('lfood_base.company_factory')

    users = {}
    for login, name, groups in [
        ('giamdoc', 'Nguyễn Văn Giám Đốc', ['lfood_base.group_director']),
        ('ketoantruong', 'Trần Thị Kế Toán Trưởng', ['lfood_base.group_chief_accountant']),
        ('ketoanvien', 'Lê Văn Kế Toán Viên', ['lfood_base.group_accountant']),
        ('nhanvien', 'Phạm Thị Nhân Viên', ['lfood_base.group_employee']),
    ]:
        user = env['res.users'].search([('login', '=', login)], limit=1)
        if not user:
            user = env['res.users'].create({
                'name': name, 'login': login, 'password': 'lfood2026',
                'company_id': ref('lfood_base.company_factory').id, 'company_ids': [(6, 0, companies.ids)], 'lang': 'vi_VN',
                'group_ids': [(6, 0, [ref(g).id for g in groups])],
            })
        users[login] = user
    env.ref('base.user_admin').write({'company_ids': [(6, 0, companies.ids)]})

    Partner = env['res.partner']
    def vendor(name, vat, street):
        p = Partner.search([('vat', '=', vat)], limit=1)
        return p or Partner.create({'name': name, 'vat': vat, 'street': street, 'is_company': True})
    ba_anh_em = vendor('CÔNG TY TNHH ẨM THỰC BA ANH EM', '1102086248', 'Số 6 đường E1, ấp 5, Xã Mỹ Hạnh, Tỉnh Tây Ninh')
    dien_luc = vendor('CÔNG TY ĐIỆN LỰC TÂY NINH', '3900254388', 'KCN Nam Thuận, Xã Mỹ Hạnh, Tây Ninh')
    van_tai = vendor('CÔNG TY TNHH VẬN TẢI TRƯỜNG PHÁT', '0312556677', 'Phường Tây Thạnh, TP. Hồ Chí Minh')

    if env['lfood.service.voucher'].search_count([]):
        return
    vat8 = ref('lfood_voucher.vat_8')
    Voucher = env['lfood.service.voucher'].with_user(users['ketoanvien']).with_company(ref('lfood_base.company_factory'))

    def make(partner, d, memo, ref_no, lines, post=True):
        v = Voucher.create({
            'company_id': ref('lfood_base.company_factory').id, 'partner_id': partner.id, 'accounting_date': d,
            'document_date': d, 'memo': memo, 'invoice_ref': ref_no, 'payment_method': 'bank',
            'buyer_id': users['ketoanvien'].id,
            'line_ids': [(0, 0, dict(l, vat_rate_id=vat8.id)) for l in lines],
        })
        if post:
            v.action_post()
            if v.state == 'waiting':
                v.with_user(users['ketoantruong']).action_approve()
        return v

    make(ba_anh_em, date(2026, 7, 31), 'Mua dịch vụ của CÔNG TY TNHH ẨM THỰC BA ANH EM theo hóa đơn số 222', '222', [
        {'service_code': 'CPSX', 'name': 'Tiền cơm tháng 7 năm 2026', 'acc_expense': '6277', 'acc_payable': '3311',
         'uom': 'suất', 'quantity': 2841, 'price_unit': 25000, 'cost_item_id': ref('lfood_voucher.ci_I_1_1').id},
        {'service_code': 'CPSX', 'name': 'Tiền cơm tháng 7 năm 2026', 'acc_expense': '6277', 'acc_payable': '3311',
         'uom': 'suất', 'quantity': 1324, 'price_unit': 20000, 'cost_item_id': ref('lfood_voucher.ci_I_1_1').id},
    ])
    make(ba_anh_em, date(2026, 8, 31), 'Tiền cơm tháng 8 năm 2026 theo hóa đơn số 251', '251', [
        {'service_code': 'CPSX', 'name': 'Tiền cơm tháng 8 năm 2026', 'acc_expense': '6277', 'uom': 'suất',
         'quantity': 2910, 'price_unit': 25000, 'cost_item_id': ref('lfood_voucher.ci_I_1_1').id},
    ])
    make(dien_luc, date(2026, 7, 31), 'Tiền điện, nước tháng 7/2026', 'HD-0007123', [
        {'service_code': 'DIEN', 'name': 'Tiền điện tháng 7/2026', 'acc_expense': '6427', 'uom': 'kWh',
         'quantity': 1, 'price_unit': 11828738, 'cost_item_id': ref('lfood_voucher.ci_II_1_1').id},
        {'service_code': 'NUOC', 'name': 'Tiền nước tháng 7/2026', 'acc_expense': '6427', 'uom': 'm3',
         'quantity': 1, 'price_unit': 10190460, 'cost_item_id': ref('lfood_voucher.ci_II_1_2').id},
    ])
    make(dien_luc, date(2026, 8, 31), 'Tiền điện tháng 8/2026', 'HD-0007455', [
        {'service_code': 'DIEN', 'name': 'Tiền điện tháng 8/2026', 'acc_expense': '6427', 'uom': 'kWh',
         'quantity': 1, 'price_unit': 20602987, 'cost_item_id': ref('lfood_voucher.ci_II_1_1').id},
    ])
    make(van_tai, date(2026, 8, 31), 'Cước chành xe miền Nam tháng 8/2026', 'HD-1240', [
        {'service_code': 'VANTAI', 'name': 'Chành xe MN tháng 8/2026', 'acc_expense': '6417', 'uom': 'chuyến',
         'quantity': 1, 'price_unit': 187376045, 'cost_item_id': ref('lfood_voucher.ci_II_6_1').id},
    ])
    make(van_tai, date(2026, 9, 12), 'Cước chành xe tuần 2 tháng 9/2026 (nháp)', 'HD-1302', [
        {'service_code': 'VANTAI', 'name': 'Chành xe MN tuần 2 tháng 9', 'acc_expense': '6417', 'uom': 'chuyến',
         'quantity': 3, 'price_unit': 4200000, 'cost_item_id': ref('lfood_voucher.ci_II_6_1').id},
    ], post=False)
