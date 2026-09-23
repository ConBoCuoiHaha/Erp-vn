{
    'name': 'LiFeOOD - Nhận diện nội bộ',
    'summary': 'Gỡ nhận diện và liên kết ra dịch vụ Odoo khỏi giao diện: trang đăng nhập, menu người dùng, thư gửi đi, '
               'tiêu đề trình duyệt, biểu tượng trang. App chạy nội bộ, không dùng dịch vụ của Odoo.',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'mail'],
    'data': ['views/brand.xml'],
    'assets': {
        'web.assets_backend': ['lfood_brand/static/src/user_menu.js'],
    },
    'installable': True,
}
