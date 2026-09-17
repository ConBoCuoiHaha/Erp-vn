"""Dữ liệu mẫu: tài sản theo file Thử AI.xlsx (máy 1 tỷ, 5 năm, phân xưởng sản xuất) và chứng từ khấu hao tháng 8/2026."""
from datetime import date


def post_init_demo(env):
    ref = env.ref
    factory = ref('lfood_base.company_factory')
    user = env['res.users'].search([('login', '=', 'ketoanvien')], limit=1)
    if not user or env['lfood.asset'].search_count([]):
        return
    Asset = env['lfood.asset'].with_user(user).with_company(factory).with_context(lfood_audit_skip=True)
    assets = Asset.create([
        {'name': 'Máy chiết rót tự động', 'category_id': ref('lfood_asset.cat_machine').id, 'usage': 'production',
         'original_value': 1_000_000_000, 'life_months': 60, 'date_start': date(2026, 8, 1),
         'purchase_date': date(2026, 7, 28), 'location': 'Phân xưởng sản xuất', 'company_id': factory.id},
        {'name': 'Xe tải 1,5 tấn giao hàng', 'category_id': ref('lfood_asset.cat_vehicle').id, 'usage': 'sales',
         'original_value': 540_000_000, 'life_months': 72, 'date_start': date(2026, 8, 16),
         'serial': '70C-123.45', 'purchase_date': date(2026, 8, 16), 'company_id': factory.id},
    ])
    assets.action_confirm()
    Depr = env['lfood.asset.depreciation'].with_user(user).with_company(factory).with_context(lfood_audit_skip=True)
    run = Depr.create({'date': date(2026, 8, 31), 'company_id': factory.id})
    run.action_compute()
    run.action_post()
