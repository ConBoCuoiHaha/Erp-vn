{
    'name': 'LiFeOOD - Hồ sơ nhân sự',
    'summary': 'Phòng ban, chức danh; điều chuyển, điều chỉnh lương (Bộ luật Lao động 2019 Điều 29); khen thưởng; '
               'xử lý kỷ luật lao động có kiểm tra thời hiệu, hình thức, thủ tục (Điều 122-125)',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_payroll', 'lfood_hr', 'lfood_reminder'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/data.xml',
        'data/safety_params.xml',
        'views/records_views.xml',
        'views/labor_report_views.xml',
        'views/safety_views.xml',
        'views/recruit_views.xml',
        'views/performance_views.xml',
    ],
    'installable': True,
}
