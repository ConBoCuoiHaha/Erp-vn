{
    'name': 'LiFeOOD - Tiền lương và bảo hiểm',
    'summary': 'Nhân viên, khoản lương, bảng lương tháng; BHXH, BHYT, BHTN, KPCĐ theo Luật BHXH 2024, Luật Việc làm 2025, '
               'Luật Công đoàn 2024; thuế TNCN 5 bậc theo Luật 109/2025; ghi sổ và chi lương',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/legal_params.xml',
        'data/pit_exemptions.xml',
        'views/payroll_views.xml',
        'views/simulation_views.xml',
    ],
    'post_init_hook': 'post_init_payroll',
    'installable': True,
}
