{
    'name': 'LiFeOOD - Nhập khẩu, xuất khẩu, thuế nhà thầu',
    'summary': 'Tờ khai nhập khẩu: thuế nhập khẩu, thuế GTGT hàng nhập khẩu, chi phí nhập khẩu vào giá vốn, nhập kho có kiểm '
               'tra chất lượng; hồ sơ xuất khẩu thuế suất 0% theo Luật Thuế GTGT Điều 14; thuế nhà thầu nước ngoài theo '
               'Nghị định 320/2025 và Luật Thuế GTGT Điều 12',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger', 'lfood_fx', 'lfood_vat', 'lfood_sale',
                'lfood_stock', 'lfood_quality'],
    'data': [
        'security/ir.model.access.csv',
        'data/fct_params.xml',
        'views/trade_views.xml',
    ],
    'installable': True,
}
