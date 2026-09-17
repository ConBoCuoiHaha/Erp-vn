{
    'name': 'LiFeOOD - Chế độ ốm đau, thai sản',
    'summary': 'Hồ sơ hưởng ốm đau, chăm con ốm, dưỡng sức, khám thai, sảy thai, sinh con, lao động nam nghỉ khi vợ sinh theo '
               'Luật Bảo hiểm xã hội 41/2024/QH15: kiểm tra số ngày tối đa, tính mức hưởng, ghi Nợ 3383 / Có 334',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger', 'lfood_payroll', 'lfood_hr', 'lfood_hr_records'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/data.xml',
        'views/benefit_views.xml',
        'views/insurance_change_views.xml',
    ],
    'installable': True,
}
