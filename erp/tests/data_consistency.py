# Đối chiếu chéo số liệu giữa các phân hệ trên dữ liệu đang có (không ghi gì). Chạy trên cơ sở dữ liệu làm việc:
#   Get-Content tests\data_consistency.py -Raw | docker compose run --rm -T odoo odoo shell -c /etc/odoo/odoo.conf -d lfood --no-http
from datetime import date

res = []


def check(name, ok, detail=''):
    res.append((name, bool(ok), detail))


ML = env['lfood.move.line'].sudo()
env.flush_all()


def gl(company, prefix, upto=None, **dom):
    d = [('state', '=', 'posted'), ('company_id', '=', company.id), ('account_code', '=like', prefix + '%')]
    if upto:
        d.append(('date', '<=', upto))
    d += [(k, '=', v) for k, v in dom.items()]
    return round(sum(ML.search(d).mapped('balance')))


today = date.today()
for comp in env['res.company'].search([]):
    tag = comp.name
    check('%s: sổ cân Nợ = Có' % tag, gl(comp, '') == 0, gl(comp, ''))
    # thẻ kho = sổ cái tài khoản kho
    Val = env['lfood.stock.valuation'].sudo()
    for acc in ('152', '155', '156'):
        prods = env['lfood.product'].sudo().with_context(active_test=False).search([])
        card = round(sum(Val.search([('company_id', '=', comp.id), ('product_id', 'in',
                                     prods.filtered(lambda p: p._stock_account(comp) == acc).ids)]).mapped('value')))
        check('%s: giá trị thẻ kho = số dư TK %s' % (tag, acc), card == gl(comp, acc), (card, gl(comp, acc)))
    # công nợ phải thu từng khách = hóa đơn còn phải thu
    Inv = env['lfood.sale.invoice'].sudo().search([('company_id', '=', comp.id), ('state', '=', 'posted'), ('kind', '=', 'invoice')])
    bad = []
    for p in Inv.mapped('partner_id'):
        resid = round(sum(Inv.filtered(lambda i: i.partner_id == p).mapped('amount_residual')))
        if resid != gl(comp, '131', partner_id=p.id):
            bad.append((p.name, resid, gl(comp, '131', partner_id=p.id)))
    check('%s: công nợ 131 từng khách = tổng hóa đơn chưa thu (%s khách)' % (tag, len(Inv.mapped('partner_id'))), not bad, bad[:5])
    # tuổi nợ phải thu cộng lại = số dư 131
    ag = env['lfood.aging'].sudo().create({'kind': 'receivable', 'company_id': comp.id, 'as_of': today})
    tot = round(sum(sum(v) for v in ag._summary().values()))
    check('%s: tổng bảng tuổi nợ phải thu = số dư 131' % tag, tot == gl(comp, '131'), (tot, gl(comp, '131')))
    # lương: tháng đã chi thì 334 của nhân viên về 0; 3335 = thuế đã khấu trừ chưa nộp
    runs = env['lfood.payroll.run'].sudo().search([('company_id', '=', comp.id)])
    # so tổng thực lĩnh của các bảng lương với chính bút toán tính lương (không tính chi lương, số dư đầu kỳ, tạm ứng)
    accrual = env['lfood.move'].sudo().search([('company_id', '=', comp.id), ('state', '=', 'posted'),
                                               ('source_model', '=', 'lfood.payroll.run'), ('source_key', '=', 'payroll')])
    acc_lines = accrual.line_ids.filtered(lambda l: l.account_code.startswith('334'))
    net_posted = round(sum(acc_lines.mapped('credit')) - sum(acc_lines.mapped('debit')))
    check('%s: bút toán lương ghi Có 334 = tổng thực lĩnh các bảng lương' % tag,
          net_posted == round(sum(r.total_net for r in runs if r.state in ('posted', 'paid'))),
          (net_posted, sum(r.total_net for r in runs if r.state in ('posted', 'paid'))))
    check('%s: 3335 = tổng thuế TNCN đã khấu trừ' % tag, -gl(comp, '3335') == round(sum(r.total_pit for r in runs if r.state in ('posted', 'paid'))),
          (-gl(comp, '3335'), sum(r.total_pit for r in runs)))
    # tờ khai GTGT: bán ra trên tờ khai = hóa đơn trong kỳ
    for vr in env['lfood.vat.return'].sudo().search([('company_id', '=', comp.id), ('state', '=', 'confirmed')]):
        inv_tax = round(sum(env['lfood.sale.invoice'].sudo().search([
            ('company_id', '=', comp.id), ('state', 'in', ('posted', 'replaced')), ('date', '>=', vr.date_from),
            ('date', '<=', vr.date_to)]).mapped(lambda i: i.amount_tax * (-1 if i.kind == 'refund' else 1))))
        line_tax = round(sum(vr.sale_line_ids.filtered(lambda l: l.source_model == 'lfood.sale.invoice').mapped('tax')))
        if inv_tax != line_tax:
            check('%s: tờ khai %s/%s thuế bán ra = thuế trên hóa đơn' % (tag, vr.month, vr.year), False, (line_tax, inv_tax))
    check('%s: mọi tờ khai GTGT khớp thuế hóa đơn bán ra' % tag, True)
    # B01 cân, B02 lợi nhuận = 4212 sau kết chuyển
    Rep = env['lfood.ledger.report'].sudo()
    # kỳ kết chuyển gần nhất lấy từ bút toán kết chuyển (bảng lfood.closing là thao tác tạm, Odoo tự dọn)
    closed = env['lfood.move'].sudo().search([('company_id', '=', comp.id), ('journal', '=', 'closing'), ('state', '=', 'posted')],
                                             order='date desc', limit=1)
    if closed:
        upto = closed.date
        b01 = Rep.create({'report': 'b01', 'company_id': comp.id, 'date_from': date(upto.year, 1, 1), 'date_to': upto})
        end, pl_left = b01._b01_values(upto.replace(day=1) if False else date.fromordinal(upto.toordinal() + 1))
        check('%s: B01 tới %s cân (tài sản = nguồn vốn)' % (tag, upto), end['280'] == end['440'] and pl_left == 0, (end['280'], end['440'], pl_left))
        b02 = Rep.create({'report': 'b02', 'company_id': comp.id, 'date_from': date(upto.year, 1, 1), 'date_to': upto})
        v = b02._b02_values(date(upto.year, 1, 1), upto)
        check('%s: B02 lợi nhuận sau thuế = 4212 (năm nay) tới %s' % (tag, upto), v['60'] == -gl(comp, '4212', upto), (v['60'], -gl(comp, '4212', upto)))
        b03 = Rep.create({'report': 'b03', 'company_id': comp.id, 'date_from': date(upto.year, 1, 1), 'date_to': upto})
        cf, cash = b03._b03_values(date(upto.year, 1, 1), upto)
        check('%s: B03 tiền cuối kỳ = số dư tiền trên sổ' % tag, cf['70'] == cash, (cf['70'], cash))
    trial = Rep.create({'report': 'trial', 'company_id': comp.id, 'date_from': date(today.year, 1, 1), 'date_to': today})
    check('%s: bảng cân đối số phát sinh báo sổ cân' % tag, 'sổ cân' in trial.html)
    # đơn bán: đã lập hóa đơn không vượt số lượng đặt
    SOL = env['lfood.sale.order.line'].sudo().search([('order_id.company_id', '=', comp.id)])
    over = SOL.filtered(lambda l: l.qty_invoiced > l.quantity + 1e-6)
    check('%s: không dòng đơn bán nào lập hóa đơn vượt số đặt (%s dòng)' % (tag, len(SOL)), not over, over.mapped('order_id.name')[:5])
    # tồn kho không âm theo lô
    env.cr.execute("""SELECT count(*) FROM (SELECT product_id, warehouse_id, lot_id, sum(qty) q FROM lfood_stock_valuation
                      WHERE company_id = %s GROUP BY 1, 2, 3) t WHERE q < -0.0001""", (comp.id,))
    check('%s: không có lô nào tồn âm' % tag, env.cr.fetchone()[0] == 0)

env.cr.rollback()
print('\n==== DOI CHIEU SO LIEU ====')
for n, ok, d in res:
    print('%s  %s%s' % ('OK  ' if ok else 'LOI ', n, '' if ok else '  -> %s' % (d,)))
print('Tong: %s dat / %s' % (sum(1 for r in res if r[1]), len(res)))
