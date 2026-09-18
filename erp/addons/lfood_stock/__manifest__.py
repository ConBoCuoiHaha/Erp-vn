{
    'name': 'LiFeOOD - Kho',
    'summary': 'Hàng hóa, vật tư, lô và hạn dùng, nhập mua, xuất bán, xuất dùng, chuyển kho, kiểm kê; giá xuất bình quân gia quyền '
               'theo từng lần phát sinh; chặn xuất âm; nhập xuất tồn, hàng sắp hết hạn; bảng kê mua vào hàng hóa',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger', 'lfood_vat', 'lfood_sale'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'data/companies.xml',
        'views/stock_views.xml',
        'views/count_views.xml',
        'views/barcode_views.xml',
        'views/uom_views.xml',
    ],
    'installable': True,
}
