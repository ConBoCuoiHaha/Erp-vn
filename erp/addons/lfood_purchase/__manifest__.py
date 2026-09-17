{
    'name': 'LiFeOOD - Mua hàng',
    'summary': 'Yêu cầu mua có kiểm soát ngân sách và duyệt, báo giá và so sánh báo giá, đơn mua hàng, nhận hàng vào kho theo đơn, '
               'đối chiếu 3 bên giữa đơn mua, phiếu nhận và hóa đơn; trả lại hàng mua; phân bổ chi phí mua hàng và giảm giá hàng mua vào giá nhập',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger', 'lfood_stock', 'lfood_budget'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'data/legal_params.xml',
        'views/purchase_views.xml',
        'views/adjust_views.xml',
        'views/tally_views.xml',
    ],
    'installable': True,
}
