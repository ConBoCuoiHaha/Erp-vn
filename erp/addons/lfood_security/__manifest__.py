{
    'name': 'LiFeOOD - Đăng nhập an toàn',
    'summary': 'Mã xác thực 2 lớp (auth_totp), độ dài mật khẩu tối thiểu, khóa tạm khi đăng nhập sai nhiều lần, '
               'tự đăng xuất khi không thao tác; quên mật khẩu (gửi thư đặt lại mật khẩu, không cho tự đăng ký); màn hình cấu hình và danh sách người chưa bật mã 2 lớp',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'auth_totp', 'auth_password_policy', 'auth_signup', 'lfood_base', 'lfood_audit', 'lfood_admin',
                # tự cài theo mail; khai phụ thuộc để module này nạp sau và vô hiệu hóa chúng
                'base_install_request', 'partner_autocomplete'],
    'data': [
        'security/ir.model.access.csv',
        'data/params.xml',
        'data/mail.xml',
        'views/security_views.xml',
    ],
    'installable': True,
}
