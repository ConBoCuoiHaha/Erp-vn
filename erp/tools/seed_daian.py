# Nạp bộ dữ liệu công ty mẫu "Công ty CP Nhựa Đại An" kỳ 01/2026 theo docs/ketoan-excel-dai-an.md.
# Chạy:  Get-Content tools\seed_daian.py -Raw | docker compose run --rm -T -e LFOOD_SEED_COMMIT=1 odoo odoo shell -c /etc/odoo/odoo.conf -d lfood_daian --no-http
# Không có LFOOD_SEED_COMMIT=1 thì chỉ chạy thử rồi hoàn tác.
import os
import traceback
from datetime import date

from odoo.exceptions import UserError, AccessError, ValidationError

D = lambda d: date(2026, 1, d)
DEC = date(2025, 12, 31)
ref = env.ref
stat, fails = {}, []


def do(what, fn):
    env.flush_all()
    env.cr.execute('SAVEPOINT s')
    try:
        res = fn()
        env.flush_all()
        env.cr.execute('RELEASE SAVEPOINT s')
        stat[what] = stat.get(what, 0) + 1
        return res
    except Exception as e:
        env.cr.execute('ROLLBACK TO SAVEPOINT s')
        env.clear()
        fr = [f for f in traceback.extract_tb(e.__traceback__) if 'lfood_' in f.filename]
        where = ' @ %s:%s' % (fr[-1].filename.split('addons/')[-1], fr[-1].lineno) if fr else ''
        fails.append((what, '%s: %s%s' % (type(e).__name__, str(e).splitlines()[0][:200] if str(e) else '', where)))
        return None


# ------------------------------------------------------------------ công ty
CO = ref('base.main_company')
CO.sudo().with_context(lfood_audit_skip=True).write({
    'name': 'Công ty CP Nhựa Đại An',
    'vat': '0300399096',
    'street': '249 Minh Phụng, Thủ Đức',
    'city': 'TP. Hồ Chí Minh',
    'lfood_manufacturer': True,
})
# mọi người dùng chuyển về công ty này rồi mới lưu trữ pháp nhân cũ
for u in env['res.users'].sudo().search([]):
    u.write({'company_ids': [(4, CO.id)], 'company_id': CO.id})
OTHER = ref('lfood_base.company_factory', False)
if OTHER and OTHER != CO and OTHER.active:
    OTHER.sudo().with_context(lfood_audit_skip=True).write({'active': False})
U = {u.login: u for u in env['res.users'].search([('login', 'in', ['ketoanvien', 'ketoantruong'])])}
kv = lambda m: env[m].with_user(U['ketoanvien']).with_company(CO)
kt = lambda m: env[m].with_user(U['ketoantruong']).with_company(CO)
vat10, vat8, vat5, vat0, kct = (ref('lfood_voucher.vat_10'), ref('lfood_voucher.vat_8'), ref('lfood_voucher.vat_5'),
                                ref('lfood_voucher.vat_0'), ref('lfood_voucher.vat_kct'))

# ------------------------------------------------------------------ kho, mặt hàng
WH = env['lfood.warehouse'].sudo()
w_vt = WH.create({'code': 'KVT', 'name': 'Kho vật tư', 'company_id': CO.id})
w_tp = WH.create({'code': 'KTP', 'name': 'Kho thành phẩm', 'company_id': CO.id})
P = kv('lfood.product')
MAT = {}
for code, name, uom, price in [('NL01', 'Hạt nhựa HDPE', 'kg', 30000), ('NL02', 'Bột nhựa PVC', 'kg', 24000),
                               ('NL03', 'Bột màu USP', 'kg', 200000), ('NL04', 'Chất phụ gia DTA', 'lít', 150000),
                               ('NL05', 'Xăng A92', 'lít', 20000), ('NL06', 'Dầu DO', 'lít', 16000)]:
    MAT[code] = P.create({'code': code, 'name': name, 'uom': uom, 'kind': 'material', 'vat_rate_id': vat10.id,
                          'track_lot': False, 'company_id': CO.id})
TOOL = {}
for code, name, price in [('CC01', 'Quạt đánh bóng Pana', 2500000), ('CC02', 'Máy đánh bóng Asia', 500000)]:
    TOOL[code] = P.create({'code': code, 'name': name, 'uom': 'cái', 'kind': 'tool', 'vat_rate_id': vat10.id,
                           'track_lot': False, 'company_id': CO.id})
FIN = {}
for code, name in [('TN01', 'Tủ nhựa TN01'), ('TN02', 'Tủ nhựa TN02')]:
    FIN[code] = P.create({'code': code, 'name': name, 'uom': 'cái', 'kind': 'finished', 'vat_rate_id': vat10.id,
                          'track_lot': False, 'company_id': CO.id})
stat['mặt hàng'] = len(MAT) + len(TOOL) + len(FIN)

# ------------------------------------------------------------------ đối tác
Partner = env['res.partner']
PT = {}
for key, name, vat, street in [
        ('CUULONG', 'Công ty TNHH Xây Dựng Cửu Long', '0300918834', '77 Bùi Thị Xuân, Q.1, TP.HCM'),
        ('KHANGTHINH', 'Công ty Cổ phần TM Khang Thịnh', '0313760390', '519 Nguyễn Tri Phương, Q.10, TP.HCM'),
        ('VINHTAN', 'Công ty TNHH TM Vĩnh Tân', '', '77 Trần Đình Xu, Q.1, TP.HCM'),
        ('MISUNA', 'Công ty MiSuNa - Thái Lan', '', '543 Silom, Bangkok'),
        ('PHATTIEN', 'Công ty TNHH TM Phát Tiến', '0301049150', '16 Lữ Gia, Q.11, TP.HCM'),
        ('HAIVIET', 'Công ty TNHH TM Hải Việt', '', '12 Mạc Đĩnh Chi, Q.1, TP.HCM'),
        ('NHUAVN', 'Công ty CP Nhựa Việt Nam', '0300381966', '30 Nguyễn Tất Thành, Q.1, TP.HCM'),
        ('HUNGTHAI', 'Công ty TNHH Điện cơ Hưng Thái', '0313751491', '156 An Dương Vương, Q.8, TP.HCM'),
        ('MINHHOA', 'Công ty TNHH TM Minh Hòa', '0301426747', '356 Nguyễn Văn Linh, Q.8, TP.HCM'),
        ('TMT', 'Công ty TNHH Quảng cáo TMT', '0313757493', '05 Phạm Hữu Chí, Q.5, TP.HCM'),
        ('DIENTHOAI', 'Công ty Điện thoại Tây thành phố', '0300954529', '270 Lý Thường Kiệt, Q.11, TP.HCM'),
        ('DIENLUC', 'Công ty Điện lực Phú Thọ', '0300951119', '215 Lý Thường Kiệt, Q.11, TP.HCM'),
        ('LONGHAI', 'Công ty Du lịch Long Hải', '', '234 Thùy Vân, Vũng Tàu'),
        ('XD584', 'Công ty Xây dựng 584', '', '462 Lê Lai, Q.1, TP.HCM'),
        ('QUANGMINH', 'Công ty TNHH TM Quang Minh', '', 'TP.HCM'),
        ('PHUONGNAM', 'DNTN Khách sạn Phương Nam', '1100480626', '59 QL 1, Tân An, Long An'),
        ('TIENTHANH', 'Công ty TNHH Tiến Thành', '0313752047', '135 Trần Tuấn Khải, Q.5, TP.HCM'),
        ('COD', 'Cổ đông công ty', '', 'TP.HCM'),
        ('NGANHANG', 'Ngân hàng TMCP Công Thương - CN 11', '', '292 Lãnh Binh Thăng, Q.11, TP.HCM')]:
    PT[key] = Partner.create({'name': name, 'is_company': True, 'vat': vat or False, 'street': street})
stat['đối tác'] = len(PT)

# ------------------------------------------------------------------ khoản mục chi phí của công ty
ITEM = {}
CI = env['lfood.cost.item'].sudo()
root_sx = CI.search([('name', '=', 'CHI PHÍ SẢN XUẤT')], limit=1)
root_bh = CI.search([('name', '=', 'CHI PHÍ BÁN HÀNG VÀ QUẢN LÝ DOANH NGHIỆP')], limit=1)
for code, name, parent in [('DA-DIEN-PX', 'Điện phân xưởng', root_sx), ('DA-CCDC', 'Công cụ, thuê TSCĐ phân xưởng', root_sx),
                           ('DA-TSCD', 'Mua sắm tài sản cố định', root_bh), ('DA-QC', 'Quảng cáo, tiếp thị', root_bh),
                           ('DA-DTHOAI', 'Điện thoại, bưu chính', root_bh), ('DA-NHANG', 'Phí ngân hàng', root_bh),
                           ('DA-DIEN-VP', 'Điện văn phòng', root_bh)]:
    ITEM[code] = CI.create({'code': code, 'name': name, 'parent_id': parent.id if parent else False})

# ------------------------------------------------------------------ nhân sự
basic = ref('lfood_payroll.comp_basic')
MIN_SALARY = 5_500_000
STAFF = [
    # (mã, họ tên, bộ phận, hệ số lương, TK chi phí, sản phẩm trực tiếp)
    # tổng hệ số từng bộ phận đặt đúng bằng bảng phân bổ tiền lương của sách:
    # 642 = 13,2; 641 = 2,5; 627 = 3,0; 622 TN01 = 13,7; 622 TN02 = 11,0 (mức lương tối thiểu 5.500.000)
    ('NV01', 'Nguyễn Văn Sơn', 'Ban Giám đốc', 2.2, '6421', None),
    ('NV02', 'Lê Thu Thủy', 'Ban Giám đốc', 2.1, '6421', None),
    ('NV03', 'Huỳnh Đắc Long', 'Hành chính - Tổ chức', 1.5, '6421', None),
    ('NV04', 'Nguyễn Văn Tâm', 'Hành chính - Tổ chức', 1.2, '6421', None),
    ('NV05', 'Trần Quang Hải', 'Hành chính - Tổ chức', 1.0, '6421', None),
    ('NV06', 'Nguyễn Thị Loan', 'Kế toán', 1.8, '6421', None),
    ('NV07', 'Lê Văn Hùng', 'Kế toán', 1.2, '6421', None),
    ('NV08', 'Nguyễn Thị Châu', 'Kế toán', 1.0, '6421', None),
    ('NV09', 'Lê Thị Diệu', 'Kế toán', 1.2, '6421', None),
    ('NV10', 'Lê Thị Ái Loan', 'Tiếp thị', 1.5, '6411', None),
    ('NV11', 'Trần Thị Lệ Nga', 'Tiếp thị', 1.0, '6411', None),
    ('NV12', 'Lê Duy Thông', 'Quản lý phân xưởng', 1.8, '6271', None),
    ('NV13', 'Lê Văn Nam', 'Quản lý phân xưởng', 1.2, '6271', None),
    ('CN01', 'Nguyễn Thế Nam', 'Phân xưởng - Tổ 1', 1.8, '622', 'TN01'),
    ('CN02', 'Lưu Công Hoàng', 'Phân xưởng - Tổ 1', 1.5, '622', 'TN01'),
    ('CN03', 'Trần Văn Tùng', 'Phân xưởng - Tổ 1', 1.5, '622', 'TN01'),
    ('CN04', 'Phan Văn Phước', 'Phân xưởng - Tổ 1', 1.5, '622', 'TN01'),
    ('CN05', 'Lê Yến Nhung', 'Phân xưởng - Tổ 1', 1.5, '622', 'TN01'),
    ('CN06', 'Trần Thùy Trang', 'Phân xưởng - Tổ 1', 1.2, '622', 'TN01'),
    ('CN07', 'Lê Thị Lan', 'Phân xưởng - Tổ 1', 1.2, '622', 'TN01'),
    ('CN08', 'Nguyễn Văn Huy', 'Phân xưởng - Tổ 1', 1.2, '622', 'TN01'),
    ('CN09', 'Lưu Bích Ngọc', 'Phân xưởng - Tổ 1', 1.2, '622', 'TN01'),
    ('CN10', 'Nguyễn Thế Hà', 'Phân xưởng - Tổ 1', 1.1, '622', 'TN01'),
    ('CN11', 'Phạm Tấn Duy', 'Phân xưởng - Tổ 2', 2.1, '622', 'TN02'),
    ('CN12', 'Trần Thế Nam', 'Phân xưởng - Tổ 2', 1.8, '622', 'TN02'),
    ('CN13', 'Trần Mạnh Khôi', 'Phân xưởng - Tổ 2', 1.5, '622', 'TN02'),
    ('CN14', 'Nguyễn Đắc Tuấn', 'Phân xưởng - Tổ 2', 1.2, '622', 'TN02'),
    ('CN15', 'Lê Thị Thủy Tiên', 'Phân xưởng - Tổ 2', 1.2, '622', 'TN02'),
    ('CN16', 'Trần Thành Lợi', 'Phân xưởng - Tổ 2', 1.2, '622', 'TN02'),
    ('CN17', 'Nguyễn Ngọc My', 'Phân xưởng - Tổ 2', 1.0, '622', 'TN02'),
    ('CN18', 'Trần Minh Toàn', 'Phân xưởng - Tổ 2', 1.0, '622', 'TN02'),
]
EMP = {}
for code, name, dept, coef, acc, prod in STAFF:
    salary = round(coef * MIN_SALARY)
    vals = {'code': code, 'name': name, 'department': dept, 'company_id': CO.id, 'region': 'I',
            'cost_account': acc, 'date_start': date(2020, 1, 1), 'insurance_salary': salary,
            'component_line_ids': [(0, 0, {'component_id': basic.id, 'amount': salary})]}
    if prod:
        vals['cost_product_id'] = FIN[prod].id
    EMP[name] = kv('lfood.employee').create(vals)
stat['nhân viên'] = len(EMP)


# ------------------------------------------------------------------ tiện ích
Acc = env['lfood.account'].sudo()


def leaf(code):
    """Trả mã tài khoản hạch toán được: mã không có thì lùi về tài khoản cha, tài khoản có con thì xuống con."""
    a = Acc.search([('code', '=', code)], limit=1)
    while not a and len(code) > 3:
        code = code[:-1]
        a = Acc.search([('code', '=', code)], limit=1)
    while a and not a.allow_posting:
        a = Acc.search([('parent_id', '=', a.id)], order='code', limit=1)
    return a.code if a else code


def manual(day, memo, rows, journal='general'):
    """rows: [(mã TK, nợ, có, đối tác)] — lập và ghi sổ phiếu kế toán."""
    lines = [(0, 0, {'account_id': Acc.by_code(leaf(c)).id, 'debit': round(d), 'credit': round(cr),
                     'partner_id': p.id if p else False}) for c, d, cr, p in rows if round(d) or round(cr)]
    m = kv('lfood.move').create({'journal': journal, 'date': day if not isinstance(day, int) else D(day),
                                 'memo': memo, 'company_id': CO.id, 'line_ids': lines})
    m.action_post()
    return m


def pay(day, kind, method, purpose, partner, amount, memo, **kw):
    v = dict({'kind': kind, 'method': method, 'purpose': purpose, 'date': D(day), 'amount': round(amount),
              'memo': memo, 'company_id': CO.id}, **kw)
    if partner:
        v['partner_id'] = partner.id
    p = kv('lfood.payment').create(v)
    p.action_post()
    return p


def service(day, partner, ref, lines, pay_now=None):
    """Chứng từ mua dịch vụ: lines = [(diễn giải, TK chi phí, số tiền, thuế suất)]"""
    v = kv('lfood.service.voucher').create({
        'partner_id': partner.id, 'accounting_date': D(day), 'document_date': D(day), 'invoice_ref': ref,
        'company_id': CO.id, 'memo': lines[0][0],
        'payment_state': 'paid_now' if pay_now else 'unpaid', 'payment_method': pay_now or 'bank',
        'line_ids': [(0, 0, {'name': n, 'acc_expense': acc, 'acc_payable': '3311', 'quantity': 1,
                             'price_unit': amount, 'vat_rate_id': vr.id if vr else False,
                             'cost_item_id': ITEM[item].id})
                     for n, acc, amount, vr, item in lines]})
    v.action_post()
    if v.state != 'posted':
        kt('lfood.service.voucher').browse(v.id).action_approve()
    return v


def issue(day, memo, wh, lines, purpose='internal', counter=None, product=None):
    v = {'kind': 'out', 'purpose': purpose, 'date': D(day), 'warehouse_id': wh.id, 'memo': memo,
         'company_id': CO.id, 'line_ids': [(0, 0, {'product_id': p.id, 'quantity': q}) for p, q in lines]}
    if product:
        v['cost_product_id'] = product.id
    pk = kv('lfood.stock.picking').create(v)
    if counter:
        pk.counterpart_account = counter
    pk.action_done()
    return pk


def receive(day, partner, symbol, number, wh, lines, purpose='purchase'):
    """lines: [(mặt hàng, số lượng, đơn giá, thuế)]"""
    pk = kv('lfood.stock.picking').create({
        'kind': 'in', 'purpose': purpose, 'date': D(day), 'warehouse_id': wh.id, 'company_id': CO.id,
        'partner_id': partner.id if partner else False, 'invoice_symbol': symbol, 'invoice_number': number,
        'invoice_date': D(day),
        'line_ids': [(0, 0, {'product_id': p.id, 'quantity': q, 'price_unit': pu,
                             'vat_rate_id': v.id if v else False}) for p, q, pu, v in lines]})
    pk.action_done()
    return pk


def sell(day, partner, number, lines, wh=None, kind='invoice', origin=None, symbol='1C26TDP', due_days=0):
    """lines: [(mặt hàng hoặc None, tên, số lượng, đơn giá, thuế suất)]"""
    v = {'partner_id': partner.id, 'date': D(day), 'invoice_date': D(day), 'invoice_template': '1',
         'invoice_symbol': symbol, 'invoice_number': number, 'company_id': CO.id, 'kind': kind,
         'line_ids': [(0, 0, {'product_id': p.id if p else False, 'name': n, 'quantity': q, 'price_unit': pu,
                              'vat_rate_id': vr.id}) for p, n, q, pu, vr in lines]}
    if wh:
        v['warehouse_id'] = wh.id
    if origin:
        v['origin_id'] = origin.id
    if due_days:
        v['due_date'] = D(day) + __import__('datetime').timedelta(days=due_days)
    inv = kv('lfood.sale.invoice').create(v)
    inv.action_post()
    return inv


# ------------------------------------------------------------------ số dư đầu kỳ
EMP_CNSX = [e for (code, name, dept, coef, acc, prod) in STAFF if acc == '622' for e in [EMP[name]]]
opening = [
    ('1111', 568_600_000, 0, None),
    ('1121', 1_512_000_000, 0, None),
    ('1122', 529_980_000, 0, None),
    ('121', 300_000_000, 0, None),
    ('1311', 110_000_000, 0, PT['CUULONG']), ('1311', 55_000_000, 0, PT['KHANGTHINH']),
    ('1311', 40_000_000, 0, PT['VINHTAN']), ('1311', 235_000_000, 0, PT['MISUNA']),
    ('1388', 1_670_000, 0, PT['QUANGMINH']),
    ('141', 1_200_000, 0, EMP['Trần Thế Nam'].partner_id), ('141', 1_800_000, 0, EMP['Lê Thị Lan'].partner_id),
    ('152', 720_000_000, 0, None),
    ('153', 30_000_000, 0, None),
    ('154', 100_740_000, 0, None),
    ('155', 279_200_000, 0, None),
    ('2111', 5_040_000_000, 0, None), ('2112', 475_800_000, 0, None),
    ('2113', 612_000_000, 0, None), ('2114', 33_600_000, 0, None),
    ('222', 620_000_000, 0, None),
    ('242', 32_000_000, 0, None),
    ('243', 4_000_000, 0, None),
    ('3311', 20_000_000, 0, PT['NHUAVN']),
    ('2141', 0, 1_592_650_000, None),
    ('2293', 0, 20_000_000, PT['VINHTAN']),
    ('3311', 0, 77_000_000, PT['PHATTIEN']), ('3311', 0, 66_000_000, PT['HAIVIET']),
    ('33311', 0, 18_000_000, None), ('3334', 0, 32_000_000, None),
    ('3411', 0, 570_000_000, None),
    ('3524', 0, 20_000_000, None),
    ('3531', 0, 132_000_000, None), ('3532', 0, 95_000_000, None),
    ('41111', 0, 7_000_000_000, None), ('4112', 0, 400_000_000, None), ('4118', 0, 288_000_000, None),
    ('414', 0, 528_590_000, None),
    ('4211', 0, 439_350_000, None),
]
share = 44_000_000 // len(EMP_CNSX)
rest = 44_000_000 - share * len(EMP_CNSX)
for i, e in enumerate(EMP_CNSX):
    opening.append(('334', 0, share + (rest if i == 0 else 0), e.partner_id))
tong_no = sum(r[1] for r in opening)
tong_co = sum(r[2] for r in opening)
print('KT so du dau ky: No %s / Co %s, lech %s' % (tong_no, tong_co, tong_no - tong_co))
do('số dư đầu kỳ', lambda: manual(DEC, 'Số dư đầu kỳ 31/12/2025', opening, journal='opening'))

# tồn kho đầu kỳ (không ghi sổ lại, chỉ lập thẻ kho)
do('tồn kho đầu kỳ vật tư', lambda: kv('lfood.stock.picking').create({
    'kind': 'in', 'purpose': 'opening', 'date': DEC, 'warehouse_id': w_vt.id, 'company_id': CO.id,
    'memo': 'Tồn kho đầu kỳ vật tư, công cụ',
    'line_ids': [(0, 0, {'product_id': MAT[c].id, 'quantity': q, 'price_unit': pu}) for c, q, pu in [
        ('NL01', 12000, 30000), ('NL02', 10000, 24000), ('NL03', 400, 200000),
        ('NL04', 200, 150000), ('NL05', 400, 20000), ('NL06', 125, 16000)]]
    + [(0, 0, {'product_id': TOOL[c].id, 'quantity': q, 'price_unit': pu}) for c, q, pu in [
        ('CC01', 10, 2500000), ('CC02', 10, 500000)]]}).action_done())
do('tồn kho đầu kỳ thành phẩm', lambda: kv('lfood.stock.picking').create({
    'kind': 'in', 'purpose': 'opening', 'date': DEC, 'warehouse_id': w_tp.id, 'company_id': CO.id,
    'memo': 'Tồn kho đầu kỳ thành phẩm',
    'line_ids': [(0, 0, {'product_id': FIN[c].id, 'quantity': q, 'price_unit': pu}) for c, q, pu in [
        ('TN01', 200, 798960), ('TN02', 200, 597040)]]}).action_done())

# tài sản cố định đang dùng dở: khai hao mòn lũy kế đầu kỳ
cat_building = ref('lfood_asset.cat_building', False) or ref('lfood_asset.cat_machine')
cat_machine = ref('lfood_asset.cat_machine')
cat_vehicle = ref('lfood_asset.cat_vehicle', False) or cat_machine
cat_office = ref('lfood_asset.cat_office', False) or cat_machine
ASSETS = [
    ('Nhà văn phòng', cat_building, 1_920_000_000, 240, date(2021, 2, 1), 'admin', 8_000_000 * 59),
    ('Nhà xưởng', cat_building, 1_680_000_000, 240, date(2021, 2, 1), 'production', 7_000_000 * 59),
    ('Nhà kho', cat_building, 1_440_000_000, 240, date(2021, 2, 1), 'admin', 6_000_000 * 59),
    ('Máy ép nhựa FJX8', cat_machine, 240_000_000, 120, date(2021, 2, 1), 'production', 2_000_000 * 59),
    ('Máy ép nhựa PA02', cat_machine, 180_000_000, 120, date(2021, 2, 1), 'production', 1_500_000 * 59),
    ('Máy phát điện HD-V12', cat_machine, 55_800_000, 72, date(2021, 2, 1), 'production', 775_000 * 59),
    ('Xe Honda 4 chỗ', cat_vehicle, 360_000_000, 120, date(2025, 4, 11), 'admin', 3_000_000 * 9),
    ('Xe tải Suzuki', cat_vehicle, 252_000_000, 120, date(2025, 4, 11), 'sales', 2_100_000 * 9),
    ('Hệ thống lạnh LG', cat_office, 33_600_000, 48, date(2025, 1, 1), 'admin', 700_000 * 12),
]
ASSET = {}
for name, cat, value, life, start, usage, accumulated in ASSETS:
    def mk(name=name, cat=cat, value=value, life=life, start=start, usage=usage, accumulated=accumulated):
        a = kv('lfood.asset').create({'name': name, 'category_id': cat.id, 'original_value': value,
                                      'life_months': life, 'date_start': start, 'usage': usage,
                                      'company_id': CO.id, 'opening_date': date(2026, 1, 1),
                                      'opening_accumulated': accumulated})
        a.action_confirm()
        return a
    ASSET[name] = do('tài sản đầu kỳ', mk)


# ------------------------------------------------------------------ nghiệp vụ tháng 01/2026
INV = {}
COST = {'TN01': 814_000, 'TN02': 625_000}   # giá thành kế hoạch, kỳ tính giá thành cuối tháng kiểm lại


def split334(amount, accs):
    """Chia số tiền trả lương cho từng người theo lương, khớp tới đồng: [(TK, người, số tiền)]"""
    emps = [EMP[n] for (c, n, d, co, a, pr) in STAFF if a in accs]
    total = sum(e.insurance_salary for e in emps)
    rows, done = [], 0
    for i, e in enumerate(emps):
        v = round(amount * e.insurance_salary / total) if i < len(emps) - 1 else amount - done
        done += v
        rows.append(('334', v, 0, e.partner_id))
    return rows


do('01 xuất NVL sản xuất TN01', lambda: issue(2, 'PXK 01/XV xuất vật liệu sản xuất TN01', w_vt, [
    (MAT['NL01'], 5000), (MAT['NL02'], 5000), (MAT['NL03'], 100), (MAT['NL04'], 80)],
    purpose='production', product=FIN['TN01']))
do('02 xuất NVL sản xuất TN02', lambda: issue(2, 'PXK 02/XV xuất vật liệu sản xuất TN02', w_vt, [
    (MAT['NL01'], 4000), (MAT['NL02'], 4000), (MAT['NL03'], 80), (MAT['NL04'], 60)],
    purpose='production', product=FIN['TN02']))
do('03 nhập mua vật tư Phát Tiến', lambda: receive(3, PT['PHATTIEN'], '1C26TPT', '0001076', w_vt, [
    (MAT['NL01'], 7000, 32000, vat10), (MAT['NL02'], 7000, 26000, vat10)]))
do('04 thu nợ Cửu Long', lambda: pay(4, 'in', 'bank', 'customer', PT['CUULONG'], 110_000_000,
                                     'GBC 9572 thu nợ HĐ 0000705'))
do('05 trả nợ Hải Việt', lambda: pay(6, 'out', 'bank', 'supplier', PT['HAIVIET'], 66_000_000,
                                     'GBN 8627 trả nợ HĐ 0000238'))
do('06 chiết khấu thanh toán', lambda: manual(6, 'PC 01/PC chiết khấu thanh toán cho Cửu Long', [
    ('635', 1_100_000, 0, None), ('111', 0, 1_100_000, None)], journal='cash'))


def asset_buy():
    v = service(7, PT['HUNGTHAI'], 'HĐ 0000786', [('Máy ép nhựa HT-V17', '2112', 64_728_000, vat10, 'DA-TSCD')])
    a = kv('lfood.asset').create({
        'name': 'Máy ép nhựa HT-V17', 'category_id': cat_machine.id, 'original_value': 64_728_000,
        'life_months': 72, 'date_start': D(7), 'purchase_date': D(7), 'usage': 'production',
        'company_id': CO.id, 'partner_id': PT['HUNGTHAI'].id, 'voucher_id': v.id})
    a.action_confirm()
    manual(7, 'TSCĐ mua bằng quỹ đầu tư phát triển', [('414', 64_728_000, 0, None), ('4118', 0, 64_728_000, None)])
    return a


ASSET['HT-V17'] = do('07 mua TSCĐ máy ép nhựa', asset_buy)
do('08 nhập mua vật liệu phụ Nhựa Việt Nam', lambda: receive(7, PT['NHUAVN'], '1C26TNV', '0000286', w_vt, [
    (MAT['NL03'], 80, 215000, vat10), (MAT['NL04'], 40, 160000, vat10)]))
do('09 chi lương kỳ 2 tháng 12/2025', lambda: manual(8, 'PC 02/PC chi lương kỳ 2 tháng 12/2025 cho công nhân sản xuất',
    split334(44_000_000, ('622',)) + [('111', 0, 44_000_000, None)], journal='cash'))
do('10 trả nợ Phát Tiến', lambda: pay(8, 'out', 'bank', 'supplier', PT['PHATTIEN'], 77_000_000,
                                      'GBN 9205 trả nợ HĐ 0000801'))
do('11 xuất xăng cho quản lý phân xưởng', lambda: issue(9, 'PXK 03/XV xăng A92 cho quản lý phân xưởng', w_vt,
                                                        [(MAT['NL05'], 100)], counter='6277'))
do('12 thu nợ Khang Thịnh', lambda: pay(9, 'in', 'bank', 'customer', PT['KHANGTHINH'], 55_000_000,
                                        'GBC 9686 thu nợ HĐ 0000242'))
do('13 thanh toán công tác phí', lambda: manual(10, 'Giấy thanh toán tạm ứng 01/TU công tác phí Lê Văn Hùng', [
    ('6427', 1_200_000, 0, None), ('111', 0, 1_200_000, None)], journal='cash'))
do('14 thu nợ MiSuNa bằng ngoại tệ', lambda: manual(11, 'GBC 9841 MiSuNa trả nợ 10.000 USD, tỷ giá 23.650', [
    ('112', 236_500_000, 0, None), ('131', 0, 235_000_000, PT['MISUNA']), ('515', 0, 1_500_000, None)], journal='bank'))
do('15 bán cổ phiếu PLC', lambda: manual(12, 'PT 01/PT bán 4.000 cổ phiếu PLC giá 25.000', [
    ('111', 100_000_000, 0, None), ('121', 0, 80_000_000, None), ('515', 0, 20_000_000, None)], journal='cash'))


def asset_sell():
    a = ASSET['Máy phát điện HD-V12']
    a.with_context(lfood_asset_system=True).write({'dispose_counterpart': '1311',
                                                   'dispose_partner_id': PT['MINHHOA'].id,
                                                   'dispose_vat_rate_id': vat10.id})
    kt('lfood.asset').browse(a.id)._dispose(D(12), 'Bán cho Công ty TNHH TM Minh Hòa', 46_000_000)
    return a


do('16 bán máy phát điện HD-V12', asset_sell)
INV['0000260'] = do('17 xuất khẩu TN01 cho MiSuNa', lambda: sell(14, PT['MISUNA'], '0000260', [
    (FIN['TN01'], 'Tủ nhựa TN01 xuất khẩu', 200, 1_422_000, vat0)], wh=w_tp))
do('18 xuất NVL sản xuất TN01', lambda: issue(15, 'PXK 04/XV xuất vật liệu sản xuất TN01', w_vt, [
    (MAT['NL01'], 4000), (MAT['NL02'], 4000), (MAT['NL03'], 80), (MAT['NL04'], 50)],
    purpose='production', product=FIN['TN01']))
do('19 xuất NVL sản xuất TN02', lambda: issue(16, 'PXK 05/XV xuất vật liệu sản xuất TN02', w_vt, [
    (MAT['NL01'], 3000), (MAT['NL02'], 3000), (MAT['NL03'], 60), (MAT['NL04'], 40)],
    purpose='production', product=FIN['TN02']))
do('20 xuất công cụ cho phân xưởng', lambda: issue(16, 'PXK 01/XC máy đánh bóng dùng ở phân xưởng, phân bổ nhiều kỳ',
                                                   w_vt, [(TOOL['CC02'], 4)], counter='242'))
do('21 xuất xăng cho hành chính', lambda: issue(17, 'PXK 06/XV xăng A92 cho phòng hành chính', w_vt,
                                                [(MAT['NL05'], 100)], counter='6427'))
do('22 trả nợ Phát Tiến hóa đơn 0001076', lambda: pay(17, 'out', 'bank', 'supplier', PT['PHATTIEN'], 446_600_000,
                                                      'GBN 14755 trả nợ HĐ 0001076'))
do('22b phí chuyển tiền', lambda: service(17, PT['NGANHANG'], 'Phí chuyển tiền',
    [('Phí chuyển tiền ngân hàng', '6427', 223_000, vat10, 'DA-NHANG')], pay_now='bank'))
do('23 trả lãi tiền vay', lambda: manual(18, 'PC 03/PC trả lãi tiền vay ngân hàng', [
    ('635', 2_800_000, 0, None), ('111', 0, 2_800_000, None)], journal='cash'))
do('24 nộp thuế tháng 12/2025', lambda: manual(18, 'GBN 15628 nộp thuế GTGT và thuế TNDN tháng 12/2025', [
    ('33311', 18_000_000, 0, None), ('3334', 32_000_000, 0, None), ('112', 0, 50_000_000, None)], journal='bank'))
do('25 chi quảng cáo sản phẩm', lambda: service(18, PT['TMT'], 'HĐ 0000845',
    [('Quảng cáo sản phẩm', '6417', 16_000_000, vat8, 'DA-QC')], pay_now='cash'))
do('26 nhập kho thành phẩm đợt 1', lambda: kv('lfood.stock.picking').create({
    'kind': 'in', 'purpose': 'factory', 'date': D(18), 'warehouse_id': w_tp.id, 'company_id': CO.id,
    'memo': 'PNK 01/NT nhập kho thành phẩm',
    'line_ids': [(0, 0, {'product_id': FIN[c].id, 'quantity': 600, 'price_unit': COST[c]}) for c in ('TN01', 'TN02')]
    }).action_done())
do('27 mua trái phiếu kho bạc', lambda: manual(19, 'PC 05/PC mua trái phiếu Kho bạc kỳ hạn 12 tháng', [
    ('128', 200_000_000, 0, None), ('111', 0, 200_000_000, None)], journal='cash'))
do('28 thu cổ tức KSL', lambda: manual(19, 'PT 02/PT thu cổ tức 10.000 cổ phiếu KSL', [
    ('111', 12_000_000, 0, None), ('515', 0, 12_000_000, None)], journal='cash'))
do('29 trả nợ vay dài hạn', lambda: manual(19, 'PC 06/PC trả nợ vay dài hạn', [
    ('3411', 50_000_000, 0, None), ('111', 0, 50_000_000, None)], journal='cash'))
do('30 chi lương đợt 1/2026', lambda: manual(20, 'PC 07/PC chi lương đợt 1 tháng 01/2026',
    split334(36_000_000, ('622',)) + split334(4_000_000, ('6271',)) + split334(4_000_000, ('6411',))
    + split334(20_000_000, ('6421',)) + [('111', 0, 64_000_000, None)], journal='cash'))
INV['0000261'] = do('31 bán hàng Cửu Long', lambda: sell(20, PT['CUULONG'], '0000261', [
    (FIN['TN01'], 'Tủ nhựa TN01', 300, 980_000, vat10), (FIN['TN02'], 'Tủ nhựa TN02', 300, 806_000, vat10)],
    wh=w_tp, due_days=730))
INV['0000262'] = do('32 bán hàng Khang Thịnh', lambda: sell(22, PT['KHANGTHINH'], '0000262', [
    (FIN['TN01'], 'Tủ nhựa TN01', 250, 980_000, vat10), (FIN['TN02'], 'Tủ nhựa TN02', 300, 806_000, vat10)],
    wh=w_tp))
do('33 vay ngân hàng 18 tháng', lambda: manual(22, 'GBC 9853 vay theo hợp đồng 1273, kỳ hạn 18 tháng', [
    ('112', 200_000_000, 0, None), ('3411', 0, 200_000_000, None)], journal='bank'))
do('34 hàng bán bị trả lại', lambda: sell(23, PT['KHANGTHINH'], '0001642', [
    (FIN['TN01'], 'Tủ nhựa TN01 trả lại do kém chất lượng', 50, 980_000, vat10)],
    wh=w_tp, kind='refund', origin=INV['0000262'], symbol='1C26TKT'))
do('35 phân phối lợi nhuận 2025', lambda: manual(24, 'QĐ 04/QĐ-HĐQT phân phối lợi nhuận sau thuế năm 2025', [
    ('4211', 439_350_000, 0, None), ('414', 0, 55_000_000, None), ('3531', 0, 27_000_000, None),
    ('3532', 0, 18_000_000, None), ('3388', 0, 339_350_000, PT['COD'])]))
do('36 phát hành thêm cổ phiếu', lambda: manual(24, 'GBC 10912 thu tiền phát hành 100.000 cổ phiếu, giá 15.000', [
    ('112', 1_500_000_000, 0, None), ('41111', 0, 1_000_000_000, None), ('4112', 0, 500_000_000, None)], journal='bank'))
do('37 chi hội diễn văn nghệ từ quỹ phúc lợi', lambda: manual(25, 'PC 08/PC thuê nhạc cụ, quỹ phúc lợi đài thọ', [
    ('3532', 6_480_000, 0, None), ('111', 0, 6_480_000, None)], journal='cash'))
do('38 tạm ứng công tác phí', lambda: pay(25, 'out', 'cash', 'advance', EMP['Lê Văn Hùng'].partner_id, 2_200_000,
                                          'PC 09/PC tạm ứng công tác phí'))
do('39 thu nợ Minh Hòa', lambda: pay(25, 'in', 'bank', 'customer', PT['MINHHOA'], 50_600_000,
                                     'GBC 11356 thu nợ hóa đơn 0000259'))
do('40 tiền điện tháng 01', lambda: service(26, PT['DIENLUC'], 'HĐ 0008195', [
    ('Tiền điện phân xưởng', '6277', 27_780_000, vat10, 'DA-DIEN-PX'),
    ('Tiền điện văn phòng', '6427', 1_689_000, vat10, 'DA-DIEN-VP')], pay_now='bank'))
do('41 tiền điện thoại', lambda: service(27, PT['DIENTHOAI'], 'HĐ 0002114', [
    ('Điện thoại bộ phận bán hàng', '6417', 1_565_000, vat10, 'DA-DTHOAI'),
    ('Điện thoại bộ phận quản lý', '6427', 4_740_000, vat10, 'DA-DTHOAI')], pay_now='cash'))
do('42 thu tiền phạt vi phạm hợp đồng', lambda: manual(27, 'PT 03/PT thu tiền phạt của Vĩnh Tân', [
    ('111', 1_814_000, 0, None), ('711', 0, 1_814_000, None)], journal='cash'))
do('43 góp thêm vốn liên doanh', lambda: manual(28, 'GBN 19224 bổ sung vốn góp liên doanh Du lịch Long Hải', [
    ('222', 200_000_000, 0, None), ('112', 0, 200_000_000, None)], journal='bank'))
do('44 thu lãi liên doanh', lambda: manual(29, 'GBC 12732 thu lãi được chia từ Du lịch Long Hải', [
    ('112', 36_000_000, 0, None), ('515', 0, 36_000_000, None)], journal='bank'))
do('45 khách ứng trước tiền hàng', lambda: pay(30, 'in', 'cash', 'customer', PT['QUANGMINH'], 22_000_000,
                                               'PT 04/PT Quang Minh ứng trước tiền mua hàng'))
do('46 thu hồi khoản bồi thường', lambda: manual(30, 'PT 05/PT thu hồi khoản bắt bồi thường', [
    ('111', 800_000, 0, None), ('1388', 0, 400_000, EMP['Trần Minh Toàn'].partner_id),
    ('1388', 0, 400_000, EMP['Lê Thị Lan'].partner_id)], journal='cash'))
do('47 nộp phạt phòng cháy', lambda: manual(30, 'PC 11/PC nộp phạt vi phạm quy định phòng cháy', [
    ('811', 12_000_000, 0, None), ('111', 0, 12_000_000, None)], journal='cash'))
do('48 thu lãi tiền gửi', lambda: manual(30, 'GBC 15456 lãi tiền gửi ngân hàng', [
    ('112', 4_400_000, 0, None), ('515', 0, 4_400_000, None)], journal='bank'))


def payroll():
    run = kv('lfood.payroll.run').create({'company_id': CO.id, 'year': 2026, 'month': 1})
    run.action_load_employees()
    run.action_compute()
    kt('lfood.payroll.run').browse(run.id).action_post()
    return run


RUN = do('49 bảng lương tháng 01/2026', payroll)
do('50 phân bổ chi phí trả trước', lambda: manual(30, 'Bảng phân bổ chi phí trả trước 01/TT', [
    ('6277', 14_000_000, 0, None), ('242', 0, 14_000_000, None)]))
do('51 trích trước chi phí sửa chữa lớn', lambda: manual(30, 'Kế hoạch trích trước 01/DPPT sửa chữa lớn cửa hàng', [
    ('6417', 20_000_000, 0, None), ('3524', 0, 20_000_000, None)]))


def depreciation():
    d = kv('lfood.asset.depreciation').create({'company_id': CO.id, 'date': D(31)})
    d.action_compute()
    d.action_post()
    return d


DEPR = do('52 khấu hao tháng 01', depreciation)
do('53 nhập kho thành phẩm đợt 2', lambda: kv('lfood.stock.picking').create({
    'kind': 'in', 'purpose': 'factory', 'date': D(31), 'warehouse_id': w_tp.id, 'company_id': CO.id,
    'memo': 'PNK 03/NT nhập kho thành phẩm',
    'line_ids': [(0, 0, {'product_id': FIN[c].id, 'quantity': 200, 'price_unit': COST[c]}) for c in ('TN01', 'TN02')]
    }).action_done())


def costing():
    run = kv('lfood.costing.run').create({
        'company_id': CO.id, 'year': 2026, 'month': '1', 'basis': '622', 'complete_pct': 50,
        'warehouse_id': w_tp.id, 'create_picking': False,
        'line_ids': [(0, 0, {'product_id': FIN['TN01'].id, 'qty_done': 800, 'qty_wip': 100, 'pct': 50}),
                     (0, 0, {'product_id': FIN['TN02'].id, 'qty_done': 800, 'qty_wip': 100, 'pct': 50})]})
    run.action_collect()
    # dở dang đầu kỳ theo số dư chi tiết TK 154 của sách:
    # TN01 39.754.400 (NVL 31.750.000 + NC 5.160.000 + SXC 2.844.400); TN02 60.985.600 (50.180.000 + 7.340.000 + 3.465.600)
    OPEN_WIP = {'TN01': (31_750_000, 5_160_000 + 2_844_400), 'TN02': (50_180_000, 7_340_000 + 3_465_600)}
    for l in run.line_ids:
        dm, conv = OPEN_WIP[l.product_id.code]
        l.write({'open_dm': dm, 'open_conv': conv})
    kt('lfood.costing.run').browse(run.id).action_post()
    return run


COSTING = do('54 tính giá thành tháng 01', costing)


def vat_return():
    vr = kv('lfood.vat.return').create({'company_id': CO.id, 'period_type': 'month', 'year': 2026, 'month': 1})
    vr.action_fetch()
    kt('lfood.vat.return').browse(vr.id).action_confirm()
    return vr


VAT = do('55 tờ khai thuế GTGT tháng 01', vat_return)
do('57 kết chuyển cuối kỳ', lambda: kt('lfood.closing').create({'company_id': CO.id, 'date_to': D(31)}).action_apply())

print('\n==== KET QUA NAP ====')
for k in sorted(stat):
    print('  %-42s %s' % (k, stat[k]))
print('Loi: %s' % len(fails))
for w, e in fails:
    print('LOI  %-38s %s' % (w, e))
if COSTING:
    for l in COSTING.line_ids:
        print('GIA THANH %s: tong %s, don vi %s (sach: %s)' % (l.product_id.code, round(l.total_cost), round(l.unit_cost), COST[l.product_id.code]))
if COSTING:
    for l in COSTING.line_ids:
        print('  CHI TIET %s: 621 %s | 622 %s | 627 gan %s | 627 phan bo %s | DD dau %s+%s | DD cuoi %s+%s'
              % (l.product_id.code, round(l.cost_dm), round(l.cost_labor), round(l.cost_overhead_direct),
                 round(l.cost_overhead_alloc), round(l.open_dm), round(l.open_conv),
                 round(l.wip_dm_end), round(l.wip_conv_end)))
    print('  627 CHUNG CHO PHAN BO: %s' % round(COSTING.overhead_pool))
if VAT:
    sale = {}
    for l in VAT.sale_line_ids:
        sale[l.group] = round(sale.get(l.group, 0) + l.base)
    for l in VAT.sale_line_ids:
        print('   BAN RA | %s | %s | goc %s | thue %s | nhom %s | giam %s' % (l.date, (l.ref or l.name or '')[:38], round(l.base), round(l.tax), l.group, l.reduced))
    print('  BAN RA THEO NHOM THUE:', sale, '| so dong:', len(VAT.sale_line_ids))
    print('  MUA VAO:', round(sum(VAT.purchase_line_ids.mapped('tax'))), 'tren', len(VAT.purchase_line_ids), 'dong')
    f = VAT._figures()
    print('TO KHAI GTGT: [25] %s, [35] %s, [40a] %s (sach: 54.312.500 / 101.960.000 / 47.647.500)' % (f.get('25'), f.get('35'), f.get('40a')))

print('GIAI DOAN 1 xong: cong ty %s, %s mat hang, %s doi tac, %s nhan vien' % (CO.name, stat['mặt hàng'], stat['đối tác'], stat['nhân viên']))
for w, e in fails:
    print('LOI', w, e)
env.flush_all()
if os.environ.get('LFOOD_SEED_COMMIT') == '1':
    env.cr.commit()
    print('DA LUU')
else:
    env.cr.rollback()
    print('CHAY THU, KHONG LUU')
