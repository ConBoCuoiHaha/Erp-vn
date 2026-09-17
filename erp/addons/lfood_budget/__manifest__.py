{
    'name': 'LiFeOOD - Ngân sách theo khoản mục chi phí',
    'summary': 'Ngân sách năm trên cây khoản mục: sửa khoản cha chia xuống con, sửa con cộng lên cha, khóa dòng, '
               'duyệt và lập phiên bản mới; báo cáo kế hoạch so với thực tế và cảnh báo vượt ngân sách',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'views/budget_views.xml',
    ],
    'installable': True,
}
