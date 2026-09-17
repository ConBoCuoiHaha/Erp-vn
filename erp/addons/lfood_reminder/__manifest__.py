{
    'name': 'LiFeOOD - Nhắc hạn',
    'summary': 'Danh sách việc sắp đến hạn quét hằng ngày: tờ khai thuế GTGT, tạm nộp thuế TNDN, hợp đồng lao động, '
               'lô sắp hết hạn dùng, hóa đơn quá hạn thu, tham số pháp lý hết áp dụng',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_voucher', 'lfood_vat', 'lfood_cit', 'lfood_hr', 'lfood_stock', 'lfood_sale', 'lfood_loan'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'views/reminder_views.xml',
    ],
    'installable': True,
}
