{
    'name': 'LiFeOOD - Bảo trì thiết bị, đội xe',
    'summary': 'Kế hoạch bảo trì định kỳ, phiếu sửa chữa, thời gian dừng máy, chi phí; đội xe: nhiên liệu và định mức '
               'tiêu hao, bảo dưỡng, hạn đăng kiểm, bảo hiểm, chành xe theo vùng; nhắc hạn',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_asset', 'lfood_reminder'],
    'data': [
        'security/ir.model.access.csv',
        'views/equipment_views.xml',
    ],
    'installable': True,
}
