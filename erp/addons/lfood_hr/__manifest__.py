{
    'name': 'LiFeOOD - Nhân sự',
    'summary': 'Hợp đồng lao động, chấm công, làm thêm giờ, nghỉ phép theo Bộ luật Lao động 2019: kiểm tra thời hạn '
               'hợp đồng, thời gian và lương thử việc, giới hạn làm thêm, phép năm theo thâm niên; đưa ngày công và '
               'tiền làm thêm vào bảng lương',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_payroll'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'data/legal_params.xml',
        'data/shift_params.xml',
        'views/hr_views.xml',
        'views/shift_views.xml',
    ],
    'installable': True,
}
