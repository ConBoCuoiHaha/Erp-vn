{
    'name': 'LiFeOOD - Nghĩa vụ thuế và tiền chậm nộp',
    'summary': 'Lịch nghĩa vụ nộp thuế tự sinh từ tờ khai GTGT, tạm nộp và quyết toán TNDN; phiếu nộp thuế gắn nghĩa vụ; '
               'tiền chậm nộp 0,03%/ngày theo Luật Quản lý thuế 108/2025/QH15, ghi sổ Nợ 811 / Có 3339',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger', 'lfood_vat', 'lfood_cit'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/legal_params.xml',
        'views/obligation_views.xml',
    ],
    'installable': True,
}
