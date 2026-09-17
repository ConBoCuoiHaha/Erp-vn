{
    'name': 'LiFeOOD - Trích lập dự phòng',
    'summary': 'Dự phòng nợ phải thu khó đòi (2293) và dự phòng giảm giá hàng tồn kho (2294) theo Thông tư '
               '48/2019/TT-BTC: tuổi nợ 30%, 50%, 70%, 100%; giá gốc so với giá trị thuần có thể thực hiện được; '
               'chỉ ghi phần chênh lệch so với số đã trích',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger', 'lfood_sale', 'lfood_stock'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'data/legal_params.xml',
        'views/provision_views.xml',
    ],
    'installable': True,
}
