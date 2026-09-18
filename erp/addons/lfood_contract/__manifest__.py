{
    'name': 'LiFeOOD - Hợp đồng mua bán, đánh giá nhà cung cấp, trade marketing',
    'summary': 'Hợp đồng mua khung (giá, sản lượng, thời hạn), đánh giá nhà cung cấp theo giao hàng, chất lượng, điểm chấm; '
               'hợp đồng nhà phân phối thưởng doanh số theo bậc quyết toán bằng hóa đơn điều chỉnh giảm; chương trình '
               'trade marketing, trưng bày theo ngân sách và khoản mục',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_admin', 'lfood_voucher', 'lfood_ledger', 'lfood_purchase', 'lfood_sale',
                'lfood_salesorder', 'lfood_quality'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'views/contract_views.xml',
    ],
    'installable': True,
}
