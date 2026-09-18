{
    'name': 'LiFeOOD - Bán hàng',
    'summary': 'Ghi nhận hóa đơn bán ra đã phát hành (Nghị định 254/2026), hàng bán trả lại, giảm giá, thu tiền theo hóa đơn, '
               'tuổi nợ phải thu, phải trả; bảng kê thuế GTGT bán ra lấy từ hóa đơn',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger', 'lfood_vat', 'lfood_admin'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'views/sale_views.xml',
        'views/payment_term_views.xml',
    ],
    'installable': True,
}
