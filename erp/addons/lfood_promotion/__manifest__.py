{
    'name': 'LiFeOOD - Khuyến mại',
    'summary': 'Chương trình khuyến mại theo Nghị định 81/2018/NĐ-CP (sửa bởi 128/2024 và 239/2026): tặng hàng kèm mua, '
               'giảm giá, tặng không kèm mua, hàng mẫu; kiểm hạn mức 50%, thông báo Sở Công Thương; '
               'hàng tặng trên hóa đơn thành tiền 0, xuất khuyến mại không kèm mua ghi chi phí bán hàng',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_salesorder'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'data/legal_params.xml',
        'views/promotion_views.xml',
    ],
    'installable': True,
}
