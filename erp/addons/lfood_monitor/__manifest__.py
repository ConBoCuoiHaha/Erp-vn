{
    'name': 'LiFeOOD - Giám sát và nhật ký kỹ thuật',
    'summary': 'Thu lỗi trên trình duyệt của người dùng, đọc nhật ký máy chủ, màn hình tình trạng hệ thống '
               'và kiểm tra sức khỏe hằng ngày (sao lưu, dung lượng đĩa, toàn vẹn nhật ký)',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_admin'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/monitor_views.xml',
    ],
    'assets': {
        'web.assets_backend': ['lfood_monitor/static/src/js/error_report.js'],
    },
    'installable': True,
}
