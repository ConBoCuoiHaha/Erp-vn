{
    'name': 'LiFeOOD - Lưu trữ chứng từ điện tử',
    'summary': 'Kho hồ sơ đính kèm chứng từ (hóa đơn, hợp đồng, biên bản) gắn với chứng từ trên app, mã kiểm tra toàn vẹn, '
               'không sửa, không xóa trong thời hạn lưu trữ theo Luật Kế toán và Nghị định 174/2016/NĐ-CP',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['base', 'lfood_base', 'lfood_audit'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/policies.xml',
        'views/archive_views.xml',
    ],
    'installable': True,
}
