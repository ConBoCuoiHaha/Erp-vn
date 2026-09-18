{
    'name': 'LiFeOOD - Sàn thương mại điện tử',
    'summary': 'Gian hàng trên sàn; nhập đơn từ tệp, lập hóa đơn nháp cho đơn hoàn thành, tồn khả dụng theo SKU để cập nhật '
               'lên sàn; đối soát tiền sàn chuyển về, phí sàn, đơn chưa được thanh toán',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger', 'lfood_sale', 'lfood_stock',
                'lfood_stock_control', 'lfood_salesorder', 'lfood_vat'],
    'data': [
        'security/ir.model.access.csv',
        'views/ecommerce_views.xml',
    ],
    'installable': True,
}
