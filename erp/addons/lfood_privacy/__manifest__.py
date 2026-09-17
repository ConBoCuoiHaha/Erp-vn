{
    'name': 'LiFeOOD - Bảo vệ dữ liệu cá nhân',
    'summary': 'Sổ căn cứ xử lý và sự đồng ý, yêu cầu của chủ thể dữ liệu có hạn xử lý theo Nghị định 356/2025/NĐ-CP, '
               'sổ sự cố vi phạm, nhật ký mở xem hồ sơ nhân sự và bảng lương, người phụ trách và miễn trừ',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_payroll', 'lfood_reminder'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'views/privacy_views.xml',
    ],
    'installable': True,
}
