{
    'name': 'LiFeOOD - Ngân hàng',
    'summary': 'Danh mục tài khoản ngân hàng, gán tài khoản cho phiếu thu chi chuyển khoản, sổ phụ ngân hàng nhập từ CSV, '
               'khớp tự động với sổ 112, bảng đối chiếu số dư, lập phiếu cho phí và lãi ngân hàng',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_ledger'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'views/bank_views.xml',
    ],
    'installable': True,
}
