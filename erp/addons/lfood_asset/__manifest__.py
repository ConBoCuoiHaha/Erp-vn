{
    'name': 'LiFeOOD - Tài sản cố định',
    'summary': 'Ghi tăng TSCĐ từ chứng từ mua, lịch khấu hao theo ngày, chứng từ khấu hao hằng tháng, '
               'thanh lý; khấu hao lên báo cáo chi phí theo cây khoản mục',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'data/categories.xml',
        'views/asset_views.xml',
        'views/depreciation_views.xml',
        'views/voucher_views.xml',
        'views/menus.xml',
    ],
    'post_init_hook': 'post_init_demo',
    'installable': True,
}
