{
    'name': 'LiFeOOD - Kiểm soát kho',
    'summary': 'Cách ly lô không đạt, biên bản hủy hàng hư hỏng, hết hạn theo Thông tư 20/2026/TT-BTC và '
               'Thông tư 99/2025/TT-BTC, tồn tối thiểu và đề xuất mua',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_ledger', 'lfood_stock', 'lfood_purchase'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'views/control_views.xml',
    ],
    'installable': True,
}
