{
    'name': 'LiFeOOD - Quản trị',
    'summary': 'Người dùng và vai trò, ma trận phân quyền, sao lưu dữ liệu, danh mục nhà cung cấp',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'lfood_base', 'lfood_audit', 'lfood_voucher'],
    'data': [
        'security/ir.model.access.csv',
        'views/menus.xml',
        'views/users_views.xml',
        'views/quick_search_views.xml',
        'views/role_matrix_views.xml',
        'views/backup_views.xml',
        'views/partner_views.xml',
    ],
    'installable': True,
}
