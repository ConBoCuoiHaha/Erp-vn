{
    'name': 'LiFeOOD - Nhật ký hệ thống',
    'summary': 'Ghi lại mọi thao tác: đăng nhập, tạo, sửa, xóa, xuất dữ liệu, in báo cáo; '
               'nhật ký không sửa, không xóa được và có chuỗi mã băm để phát hiện can thiệp',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'lfood_base'],
    'data': [
        'security/ir.model.access.csv',
        'views/audit_log_views.xml',
    ],
    'installable': True,
}
