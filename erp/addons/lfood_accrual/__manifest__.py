{
    'name': 'LiFeOOD - Chi phí trả trước và trích trước',
    'summary': 'Chi phí chờ phân bổ TK 242 và chi phí phải trả TK 335 theo Thông tư 99/2025/TT-BTC: lập lịch phân bổ '
               'theo tháng, ghi sổ từng kỳ, quyết toán khoản trích trước theo số thực tế',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger', 'lfood_asset', 'lfood_reminder'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'views/accrual_views.xml',
        'views/lease_views.xml',
    ],
    'installable': True,
}
