{
    'name': 'LiFeOOD - Tính giá thành sản phẩm',
    'summary': 'Giá thành giản đơn: tập hợp 621, 622, 627 theo sản phẩm, phân bổ chi phí chung theo tiêu thức, '
               'đánh giá sản phẩm dở dang theo sản lượng hoàn thành tương đương, kết chuyển 154 và nhập kho thành phẩm',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger', 'lfood_stock', 'lfood_payroll'],
    'data': [
        'security/ir.model.access.csv',
        'views/costing_views.xml',
    ],
    'installable': True,
}
