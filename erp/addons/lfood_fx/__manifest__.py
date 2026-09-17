{
    'name': 'LiFeOOD - Ngoại tệ và đánh giá lại tỷ giá',
    'summary': 'Ghi loại ngoại tệ và số nguyên tệ trên bút toán; đánh giá lại khoản mục tiền tệ có gốc ngoại tệ cuối kỳ '
               'theo tỷ giá mua bán chuyển khoản trung bình, ghi chênh lệch thuần vào 515 hoặc 635 (Thông tư 99/2025/TT-BTC)',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'views/fx_views.xml',
    ],
    'installable': True,
}
