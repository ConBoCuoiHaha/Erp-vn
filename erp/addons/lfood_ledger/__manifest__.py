{
    'name': 'LiFeOOD - Sổ kế toán',
    'summary': 'Hệ thống tài khoản Thông tư 99/2025, bút toán tự sinh từ chứng từ, phiếu thu chi, phiếu kế toán, '
               'số dư đầu kỳ, kết chuyển, khóa sổ, sổ cái, bảng cân đối số phát sinh, công nợ, B02-DN',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_asset'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'data/accounts.xml',
        'views/account_views.xml',
        'views/move_views.xml',
        'views/payment_views.xml',
        'views/wizard_views.xml',
        'views/source_views.xml',
        'views/menus.xml',
    ],
    'post_init_hook': 'post_init_ledger',
    'installable': True,
}
