# Dữ liệu mẫu để dùng thử: 01/01/2026 đến 17/09/2026, đi qua đúng nghiệp vụ của app (không ghi thẳng vào bảng).
# Tên đối tác, nhân viên là tên bịa, có chữ "(mẫu)". Chạy thử (không lưu):
#   Get-Content tools\seed_demo.py -Raw | docker compose run --rm -T odoo odoo shell -c /etc/odoo/odoo.conf -d lfood --no-http
# Lưu thật: thêm -e LFOOD_SEED_COMMIT=1 sau "run --rm -T". Chạy một lần; lần sau tự dừng nếu đã có dữ liệu mẫu.
import os
import random
import traceback
import calendar
from datetime import date, timedelta
from odoo.exceptions import UserError, AccessError, ValidationError

rnd = random.Random(2026)
END = date(2026, 9, 17)
ref = env.ref
NM = ref('lfood_base.company_factory')
VP = ref('base.main_company')
U = {u.login: u for u in env['res.users'].search([('login', 'in', ['ketoanvien', 'ketoantruong', 'giamdoc'])])}
kv = lambda m, c=NM: env[m].with_user(U['ketoanvien']).with_company(c)
kt = lambda m, c=NM: env[m].with_user(U['ketoantruong']).with_company(c)
vat8, vat10, vat5, kct = ref('lfood_voucher.vat_8'), ref('lfood_voucher.vat_10'), ref('lfood_voucher.vat_5'), ref('lfood_voucher.vat_kct')
stat, fails = {}, []


def do(what, fn):
    """Mỗi nghiệp vụ trong savepoint riêng: lỗi thì ghi lại, không làm hỏng phần còn lại."""
    env.flush_all()
    env.cr.execute('SAVEPOINT seed')
    try:
        res = fn()
        env.flush_all()
        env.cr.execute('RELEASE SAVEPOINT seed')
        stat[what] = stat.get(what, 0) + 1
        return res
    except Exception as e:
        env.cr.execute('ROLLBACK TO SAVEPOINT seed')
        env.clear()
        fr = [f for f in traceback.extract_tb(e.__traceback__) if 'lfood_' in f.filename]
        where = ' @ %s:%s' % (fr[-1].filename.split('addons/')[-1], fr[-1].lineno) if fr else ''
        fails.append((what, '%s: %s%s' % (type(e).__name__, str(e).splitlines()[0][:220] if str(e) else '', where)))
        return None


if env['res.partner'].search_count([('name', 'ilike', '(mẫu)')]):
    raise SystemExit('Đã có dữ liệu mẫu, dừng để không tạo trùng.')

# ------------------------------------------------------------------ danh mục
WH = env['lfood.warehouse'].sudo()
w_nl = WH.create({'code': 'KNL', 'name': 'Kho nguyên liệu', 'company_id': NM.id})
w_tp = WH.create({'code': 'KTP', 'name': 'Kho thành phẩm', 'company_id': NM.id})
w_hh = WH.create({'code': 'KHH', 'name': 'Kho hàng hóa', 'company_id': NM.id})


def ean(n):
    base = '893%09d' % n  # 893 = mã quốc gia Việt Nam
    s = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(base))
    return base + str((10 - s % 10) % 10)


P = kv('lfood.product')
materials = [P.create({'code': c, 'name': n, 'uom': u, 'kind': 'material', 'vat_rate_id': v.id, 'track_lot': True,
                       'shelf_life_days': sl, 'company_id': NM.id, 'min_qty': mn})
             for c, n, u, v, sl, mn in [
                 ('NL01', 'Gạo tẻ (mẫu)', 'kg', kct, 365, 500), ('NL02', 'Thịt heo xay (mẫu)', 'kg', kct, 30, 100),
                 ('NL03', 'Thịt gà phi lê (mẫu)', 'kg', kct, 30, 100), ('NL04', 'Cà rốt (mẫu)', 'kg', kct, 20, 50),
                 ('NL05', 'Hành tím (mẫu)', 'kg', kct, 60, 20), ('NL06', 'Nước mắm (mẫu)', 'lít', vat8, 540, 30),
                 ('NL07', 'Hũ nhựa PP 300ml (mẫu)', 'cái', vat8, 1800, 5000), ('NL08', 'Thùng carton 24 hũ (mẫu)', 'cái', vat8, 1800, 300)]]
cost_nl = {'NL01': 16000, 'NL02': 95000, 'NL03': 88000, 'NL04': 14000, 'NL05': 38000, 'NL06': 42000, 'NL07': 1800, 'NL08': 6500}
finished = [P.create({'code': c, 'name': n, 'uom': 'hũ', 'kind': 'finished', 'vat_rate_id': vat8.id, 'track_lot': True,
                      'shelf_life_days': 270, 'company_id': NM.id, 'barcode': ean(i + 1), 'brand': 'LiFeOOD', 'min_qty': 500})
            for i, (c, n) in enumerate([('TP01', 'Cháo hũ thịt bằm (mẫu)'), ('TP02', 'Cháo hũ gà nấm (mẫu)'),
                                        ('TP03', 'Súp hũ cua (mẫu)'), ('TP04', 'Cháo hũ cá hồi (mẫu)'),
                                        ('TP05', 'Cháo hũ bò rau củ (mẫu)'), ('TP06', 'Súp hũ bí đỏ (mẫu)')])]
cost_tp = {'TP01': 11500, 'TP02': 12000, 'TP03': 14500, 'TP04': 16800, 'TP05': 15200, 'TP06': 10500}
goods = [P.create({'code': c, 'name': n, 'uom': u, 'kind': 'goods', 'vat_rate_id': vat8.id, 'track_lot': True,
                   'shelf_life_days': 365, 'company_id': NM.id, 'barcode': ean(100 + i), 'brand': b})
         for i, (c, n, u, b) in enumerate([('HH01', 'Nước yến sào lon (mẫu)', 'lon', 'Đối tác A'),
                                           ('HH02', 'Bánh gạo lứt (mẫu)', 'gói', 'Đối tác B'),
                                           ('HH03', 'Sữa hạt óc chó (mẫu)', 'hộp', 'Đối tác C'),
                                           ('HH04', 'Muối tôm Tây Ninh (mẫu)', 'hũ', 'Đối tác A')])]
cost_hh = {'HH01': 9500, 'HH02': 18000, 'HH03': 7200, 'HH04': 21000}
price = {**{k: round(v * 1.9, -2) for k, v in cost_tp.items()}, **{k: round(v * 1.35, -2) for k, v in cost_hh.items()}}
stat['mặt hàng'] = len(materials) + len(finished) + len(goods)

Partner = env['res.partner']
first = ['Minh', 'Phát', 'Thịnh', 'Hưng', 'An', 'Phúc', 'Tân', 'Đại', 'Bảo', 'Hòa', 'Nam', 'Việt', 'Kim', 'Long', 'Thành']
suppliers = [Partner.create({'name': 'Công ty TNHH %s %s (mẫu)' % (k, first[i]), 'is_company': True,
                             'street': '%d đường số %d, KCN Trảng Bàng, Tây Ninh' % (rnd.randint(1, 200), rnd.randint(1, 30))})
             for i, k in enumerate(['Nông sản', 'Thực phẩm', 'Bao bì', 'Nông sản', 'Thực phẩm', 'Bao bì', 'Thương mại', 'Gia vị'])]
sup_of = {'NL01': suppliers[0], 'NL02': suppliers[1], 'NL03': suppliers[4], 'NL04': suppliers[3], 'NL05': suppliers[3],
          'NL06': suppliers[7], 'NL07': suppliers[2], 'NL08': suppliers[5]}
Chan = env['lfood.sale.channel'].with_user(U['ketoanvien'])
channels = {c: Chan.create({'code': c, 'name': n}) for c, n in [('MT', 'Siêu thị (mẫu)'), ('GT', 'Đại lý, tạp hóa (mẫu)'),
                                                                 ('ONL', 'Bán trực tuyến (mẫu)')]}
disc = {'MT': 0.95, 'GT': 0.9, 'ONL': 1.0}
plists = {c: kv('lfood.pricelist').create({
    'name': 'Bảng giá %s 2026 (mẫu)' % c, 'channel_id': ch.id, 'date_from': date(2026, 1, 1), 'company_id': NM.id,
    'line_ids': [(0, 0, {'product_id': p.id, 'min_qty': 1, 'price': round(price[p.code] * disc[c], -2)})
                 for p in finished + goods]}) for c, ch in channels.items()}
customers = []
for i in range(24):
    c = ['MT', 'GT', 'GT', 'ONL'][i % 4]
    name = {'MT': 'Siêu thị %s %s (mẫu)', 'GT': 'Đại lý %s %s (mẫu)', 'ONL': 'Cửa hàng trực tuyến %s %s (mẫu)'}[c] % (
        rnd.choice(['Bách hóa', 'Tiện lợi', 'Thực phẩm', 'Gia đình']), first[i % len(first)] + ' ' + str(i + 1))
    customers.append(Partner.create({'name': name, 'is_company': True, 'lfood_channel_id': channels[c].id,
                                     'lfood_pricelist_id': plists[c].id, 'lfood_credit_limit': rnd.choice([80, 150, 300]) * 1_000_000,
                                     'lfood_payment_days': {'MT': 45, 'GT': 15, 'ONL': 7}[c], 'lfood_min_shelf_days': 60 if c == 'MT' else 0}))
stat['đối tác'] = len(suppliers) + len(customers)

# ------------------------------------------------------------------ nhân sự
basic = ref('lfood_payroll.comp_basic')
last = ['Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Võ', 'Đặng', 'Bùi', 'Đỗ', 'Huỳnh']
mid = ['Văn', 'Thị', 'Minh', 'Ngọc', 'Hữu', 'Thanh', 'Quốc', 'Thu']
given = ['An', 'Bình', 'Châu', 'Dũng', 'Giang', 'Hạnh', 'Khoa', 'Lan', 'Mai', 'Nhân', 'Oanh', 'Phong', 'Quyên', 'Sơn', 'Tâm', 'Uyên', 'Vinh', 'Xuân', 'Yến']
employees = {NM: [], VP: []}
for comp, n, prefix in ((NM, 26, 'NM'), (VP, 8, 'VP')):
    for i in range(n):
        acc = '6421' if comp == VP else rnd.choice(['622', '622', '622', '6271', '6411'])
        sal = {'622': rnd.randrange(7_000_000, 11_000_000, 100_000), '6271': rnd.randrange(10_000_000, 16_000_000, 100_000),
               '6411': rnd.randrange(9_000_000, 18_000_000, 100_000), '6421': rnd.randrange(12_000_000, 35_000_000, 100_000)}[acc]

        def mk(comp=comp, i=i, prefix=prefix, acc=acc, sal=sal):
            e = kv('lfood.employee', comp).create({
                'code': '%s%03d' % (prefix, i + 1), 'name': '%s %s %s (mẫu)' % (rnd.choice(last), rnd.choice(mid), rnd.choice(given)),
                'company_id': comp.id, 'region': 'III' if comp == NM else 'I', 'cost_account': acc,
                'department': {'622': 'Sản xuất', '6271': 'Phân xưởng', '6411': 'Kinh doanh', '6421': 'Văn phòng'}[acc],
                'date_start': date(rnd.randint(2018, 2025), rnd.randint(1, 12), 1), 'dependents': rnd.choice([0, 0, 1, 2]),
                'insurance_salary': sal})
            c = kv('lfood.hr.contract', comp).create({'employee_id': e.id, 'kind': 'definite', 'date_start': date(2026, 1, 1),
                                                      'date_end': date(2027, 12, 31), 'salary': sal, 'insurance_salary': sal})
            c.action_activate()
            return e
        e = do('nhân viên + hợp đồng', mk)
        if e:
            employees[comp].append(e)

# ------------------------------------------------------------------ nghiệp vụ theo ngày
inv_no = [0]
lot_no = [0]
open_pick = []   # phiếu nhập chờ trả tiền: (ngày đến hạn, picking)
open_inv = []    # hóa đơn bán chờ thu: (ngày thu, invoice)


def next_inv():
    inv_no[0] += 1
    return '%08d' % inv_no[0]


def buy(d, prods, wh):
    """Đơn mua -> nhận hàng -> ghi phiếu nhập có hóa đơn."""
    sup = sup_of.get(prods[0].code, suppliers[6])
    lines = []
    for p in prods:
        qty = {'kg': rnd.choice([300, 500, 800]), 'lít': 100, 'cái': rnd.choice([3000, 5000])}.get(p.uom, rnd.choice([400, 600, 1000]))
        lines.append((0, 0, {'product_id': p.id, 'name': p.name, 'quantity': qty,
                             'price_unit': cost_nl.get(p.code) or cost_hh.get(p.code), 'vat_rate_id': p.vat_rate_id.id}))
    po = kv('lfood.purchase.order').create({'partner_id': sup.id, 'date': d, 'warehouse_id': wh.id, 'line_ids': lines})
    po.action_confirm()
    if po.state == 'waiting':
        kt('lfood.purchase.order').browse(po.id).action_confirm()
    pick = kv('lfood.stock.picking').browse(po.action_receive()['res_id'])
    pick.write({'date': d, 'invoice_symbol': 'C26T%s' % sup.name[-8:-6].upper().replace(' ', 'X'),
                'invoice_number': next_inv(), 'invoice_date': d})
    for l in pick.line_ids:
        lot_no[0] += 1
        l.write({'lot_name': '%s-%s' % (l.product_id.code, d.strftime('%y%m%d')),
                 'expiry_date': d + timedelta(days=l.product_id.shelf_life_days or 365)})
    pick.action_done()
    open_pick.append((d + timedelta(days=rnd.choice([15, 30, 30, 45])), pick))
    return pick


def produce(d):
    """Nhập thành phẩm từ nhà máy (giá thành kế hoạch) và xuất nguyên liệu dùng cho sản xuất."""
    lines = [(0, 0, {'product_id': p.id, 'lot_name': '%s-%s' % (p.code, d.strftime('%y%m%d')), 'quantity': rnd.choice([1200, 1800, 2400]),
                     'expiry_date': d + timedelta(days=270), 'price_unit': cost_tp[p.code]}) for p in finished]
    kv('lfood.stock.picking').create({'kind': 'in', 'purpose': 'factory', 'date': d, 'warehouse_id': w_tp.id,
                                      'memo': 'Nhập thành phẩm tuần %s (mẫu)' % d.isocalendar()[1], 'line_ids': lines}).action_done()


def issue_materials(d):
    lines = []
    for p in materials:
        q = p._position(w_nl)[0]
        if q > 0:
            lines.append((0, 0, {'product_id': p.id, 'quantity': round(q * rnd.uniform(0.5, 0.8))}))
    if lines:
        kv('lfood.stock.picking').create({'kind': 'out', 'purpose': 'internal', 'date': d, 'warehouse_id': w_nl.id,
                                          'memo': 'Xuất nguyên liệu cho sản xuất (mẫu)', 'line_ids': lines}).action_done()


def sell(d):
    cust = rnd.choice(customers)
    wh = w_tp if rnd.random() < 0.8 else w_hh
    pool = finished if wh == w_tp else goods
    lines = []
    for p in rnd.sample(pool, rnd.randint(1, min(3, len(pool)))):
        avail = p._position(wh)[0]
        q = min(avail * 0.3, rnd.choice([48, 96, 120, 240, 480]))
        q = int(q // 24 * 24)
        if q >= 24:
            lines.append((0, 0, {'product_id': p.id, 'quantity': q, 'vat_rate_id': vat8.id}))
    if not lines:
        return None
    so = kv('lfood.sale.order').create({'partner_id': cust.id, 'date': d, 'warehouse_id': wh.id, 'company_id': NM.id, 'line_ids': lines})
    so.action_apply_prices()
    so.action_confirm()
    if so.state == 'waiting':
        kt('lfood.sale.order').browse(so.id).action_approve_credit()
    inv = kv('lfood.sale.invoice').browse(so.action_create_invoice()['res_id'])
    inv.write({'date': d, 'invoice_date': d, 'invoice_template': '1', 'invoice_symbol': 'C26TLF', 'invoice_number': next_inv(),
               'due_date': d + timedelta(days=cust.lfood_payment_days or 15)})
    inv.action_post()
    pay_day = inv.due_date + timedelta(days=rnd.choice([-5, 0, 0, 3, 10, 25]))
    open_inv.append((pay_day, inv))
    return inv


def service(d, comp, name, acc, item, amount, v=vat8, partner=None):
    partner = partner or {'6277': suppliers[6]}.get(acc) or rnd.choice(suppliers)
    vc = kv('lfood.service.voucher', comp).create({
        'partner_id': partner.id, 'accounting_date': d, 'document_date': d, 'memo': name, 'invoice_ref': 'HĐ ' + next_inv(),
        'company_id': comp.id,
        'line_ids': [(0, 0, {'name': name, 'acc_expense': acc, 'acc_payable': '3311', 'quantity': 1, 'price_unit': amount,
                             'vat_rate_id': v.id, 'cost_item_id': item.id if item else False})]})
    vc.action_post()
    if vc.state not in ('posted',):
        kt('lfood.service.voucher', comp).browse(vc.id).action_approve()
    return vc


items = {i.name: i for i in env['lfood.cost.item'].search([('child_ids', '=', False)])}
elec, water, net_i, fuel = items.get('Chi phí điện'), items.get('Chi phí nước'), items.get('Chi phí internet'), items.get('641_Nhiên liệu (Dầu DO) MN')
meal, clean = items.get('Tiền cơm ca CBCNV'), items.get('Thuê ngoài vệ sinh công nghiệp')

d = date(2026, 1, 2)
while d <= END:
    wd = d.weekday()
    if wd < 6:
        if wd == 0 and (d.day <= 7 or 15 <= d.day <= 21) or d == date(2026, 1, 2):
            do('mua nguyên liệu', lambda: buy(d, materials[:4], w_nl))
            do('mua bao bì, gia vị', lambda: buy(d, materials[4:], w_nl))
        if wd == 1:
            do('nhập thành phẩm', lambda: produce(d))
        if wd == 2 and 8 <= d.day <= 14 or d == date(2026, 1, 2):
            do('mua hàng hóa', lambda: buy(d, goods, w_hh))
        if wd == 4:
            do('xuất nguyên liệu sản xuất', lambda: issue_materials(d))
        if wd != 1 and d > date(2026, 1, 6):
            for _ in range(rnd.randint(1, 3)):
                do('đơn bán + hóa đơn', lambda: sell(d))
        if wd == 3 and 8 <= d.day <= 14:
            do('chứng từ dịch vụ', lambda: service(d, NM, 'Tiền điện sản xuất tháng %s (mẫu)' % (d.month - 1 or 12), '6277', elec,
                                                  rnd.randrange(60_000_000, 95_000_000, 1000), vat8))
            do('chứng từ dịch vụ', lambda: service(d, NM, 'Tiền nước tháng %s (mẫu)' % (d.month - 1 or 12), '6277', water,
                                                  rnd.randrange(6_000_000, 9_000_000, 1000), vat5))
            do('chứng từ dịch vụ', lambda: service(d, NM, 'Suất ăn ca tháng %s (mẫu)' % (d.month - 1 or 12), '6277', meal,
                                                  rnd.randrange(35_000_000, 48_000_000, 1000), vat8))
            do('chứng từ dịch vụ', lambda: service(d, VP, 'Internet văn phòng tháng %s (mẫu)' % (d.month - 1 or 12), '6427', net_i,
                                                  1_100_000, vat10))
        if wd == 0 and d.day <= 7:
            do('chứng từ dịch vụ', lambda: service(d, NM, 'Dầu DO xe giao hàng (mẫu)', '6417', fuel, rnd.randrange(12_000_000, 20_000_000, 1000), vat10))
            do('chứng từ dịch vụ', lambda: service(d, NM, 'Vệ sinh công nghiệp (mẫu)', '6277', clean, 18_000_000, vat8))
    # thu tiền khách, trả tiền nhà cung cấp đến hạn
    for pay_day, inv in [x for x in open_inv if x[0] <= d]:
        open_inv.remove((pay_day, inv))
        inv.invalidate_recordset()
        if inv.amount_residual > 0 and rnd.random() < 0.92:
            do('thu tiền khách hàng', lambda inv=inv: kv('lfood.payment').create({
                'kind': 'in', 'method': 'bank', 'purpose': 'customer', 'partner_id': inv.partner_id.id, 'date': d,
                'amount': inv.amount_residual if rnd.random() < 0.85 else round(inv.amount_residual / 2),
                'memo': 'Thu tiền hóa đơn %s' % inv.invoice_number, 'sale_invoice_id': inv.id}).action_post())
    for due, pick in [x for x in open_pick if x[0] <= d]:
        open_pick.remove((due, pick))
        do('trả tiền nhà cung cấp', lambda pick=pick: kv('lfood.payment').create({
            'kind': 'out', 'method': 'bank', 'purpose': 'supplier', 'partner_id': pick.partner_id.id, 'date': d,
            'amount': round(pick.amount + pick.amount_tax),
            'memo': 'Trả tiền hóa đơn %s' % pick.invoice_number, 'picking_id': pick.id}).action_post())
    # cuối tháng: nghỉ phép, lương, tờ khai thuế GTGT, kết chuyển
    if (d + timedelta(days=1)).day == 1:
        y, m = d.year, d.month
        for comp in (NM, VP):
            for e in rnd.sample(employees[comp], min(4, len(employees[comp]))):
                day1 = date(y, m, rnd.randint(3, 20))
                if day1.weekday() < 5:
                    lv = do('đơn nghỉ phép', lambda e=e, day1=day1, comp=comp: kv('lfood.hr.leave', comp).create({
                        'employee_id': e.id, 'kind': 'annual', 'date_from': day1, 'date_to': day1, 'days': 1,
                        'reason': 'Việc gia đình (mẫu)'}))
                    if lv:
                        do('duyệt đơn nghỉ', lambda lv=lv, comp=comp: kt('lfood.hr.leave', comp).browse(lv.id).action_approve())

            def payroll(comp=comp):
                run = kv('lfood.payroll.run', comp).create({'company_id': comp.id, 'year': y, 'month': m})
                run.action_load_employees()
                run.action_compute()
                kt('lfood.payroll.run', comp).browse(run.id).action_post()
                pay = date(y, m, 1) + timedelta(days=calendar.monthrange(y, m)[1] + 4)
                if pay <= END:
                    run.write({'pay_date': pay})
                    run.action_pay()
                return run
            do('bảng lương tháng', payroll)

            def vat_return(comp=comp):
                vr = kv('lfood.vat.return', comp).create({'company_id': comp.id, 'period_type': 'month', 'year': y, 'month': m})
                vr.action_fetch()
                kt('lfood.vat.return', comp).browse(vr.id).action_confirm()
            do('tờ khai GTGT tháng', vat_return)

            def closing(comp=comp):
                kt('lfood.closing', comp).create({'company_id': comp.id, 'date_to': d}).action_apply()
            do('kết chuyển cuối tháng', closing)
    d += timedelta(days=1)

print('\n==== DU LIEU MAU ====')
for k, v in sorted(stat.items()):
    print('  %-32s %s' % (k, v))
print('Loi: %s' % len(fails))
seen = {}
for w, e in fails:
    seen.setdefault((w, e), 0)
    seen[(w, e)] += 1
for (w, e), n in seen.items():
    print('LOI  %s x%s: %s' % (w, n, e))
env.flush_all()
if os.environ.get('LFOOD_SEED_COMMIT') == '1':
    env.cr.commit()
    print('DA LUU')
else:
    env.cr.rollback()
    print('CHAY THU, KHONG LUU')
