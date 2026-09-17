"""Khi cài phân hệ Sổ kế toán: ghi sổ bổ sung cho các chứng từ đã có từ trước."""


def post_init_ledger(env):
    env = env(context=dict(env.context, lfood_audit_skip=True))
    Move = env['lfood.move']

    for voucher in env['lfood.service.voucher'].search([('state', 'in', ('posted', 'editing'))], order='accounting_date, id'):
        voucher._ledger_sync()

    assets = env['lfood.asset'].search([('state', '!=', 'draft')], order='date_start, id')
    vendor = False
    for asset in assets:
        if Move._active_for(asset):
            continue
        if not asset.voucher_id and not asset.partner_id:
            # tài sản mẫu nhập tay chưa có nhà cung cấp: gắn nhà cung cấp mẫu để ghi được Có 3311 theo đối tượng
            vendor = vendor or env['res.partner'].search([('name', '=', 'Nhà cung cấp thiết bị (dữ liệu mẫu)')], limit=1) \
                or env['res.partner'].create({'name': 'Nhà cung cấp thiết bị (dữ liệu mẫu)', 'is_company': True})
            asset.write({'partner_id': vendor.id})
        # gọi lại phần ghi sổ ghi tăng của phân hệ Sổ kế toán cho tài sản đã ghi tăng trước khi cài
        if asset.voucher_id:
            lines = asset._voucher_reclass_lines()
        else:
            label = 'Ghi tăng %s' % asset.code
            lines = [(asset.account_asset, asset.original_value, 0, None, label, None),
                     (asset.counterpart_account or '3311', 0, asset.original_value, asset.partner_id, label, None)]
        if lines:
            Move._create_from_source(asset, 'asset', asset.purchase_date or asset.date_start, lines,
                                     memo='Ghi tăng TSCĐ %s %s' % (asset.code, asset.name), key='increase', ref=asset.code)

    for depr in env['lfood.asset.depreciation'].search([('state', '=', 'posted')], order='date, id'):
        depr._ledger_sync()
