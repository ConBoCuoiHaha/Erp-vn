{
    'name': 'LiFeOOD - Thuế GTGT',
    'summary': 'Tờ khai 01/GTGT theo Thông tư 89/2026, bảng kê hóa đơn mua vào có kiểm tra điều kiện khấu trừ, '
               'bảng kê bán ra, phụ lục giảm thuế theo Nghị định 174/2025, bù trừ thuế và chuyển kỳ',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'views/vat_views.xml',
        'views/einvoice_views.xml',
    ],
    'installable': True,
}
