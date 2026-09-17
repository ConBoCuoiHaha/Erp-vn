{
    'name': 'LiFeOOD - Thuế thu nhập doanh nghiệp',
    'summary': 'Tạm nộp thuế TNDN theo quý và quyết toán năm: thuế suất 15%, 17%, 20% theo tổng doanh thu năm liền kề '
               'trước (Luật 67/2025/QH15), chuyển lỗ liên tục không quá 5 năm, kiểm tra tỷ lệ tạm nộp tối thiểu 80%, '
               'ghi sổ 8211 và 3334',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger', 'lfood_purchase'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'data/legal_params.xml',
        'views/cit_views.xml',
    ],
    'installable': True,
}
