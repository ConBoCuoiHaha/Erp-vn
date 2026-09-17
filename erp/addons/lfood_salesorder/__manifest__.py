{
    'name': 'LiFeOOD - Đơn bán hàng',
    'summary': 'Kênh phân phối, bảng giá theo kênh, hạn mức công nợ khách hàng, báo giá và đơn bán, '
               'lập hóa đơn từ đơn, giao hàng theo hạn dùng tối thiểu khách yêu cầu',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_ledger', 'lfood_sale', 'lfood_stock'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'views/sale_order_views.xml',
        'views/margin_views.xml',
    ],
    'installable': True,
}
