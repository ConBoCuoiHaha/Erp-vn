{
    'name': 'LiFeOOD - Bảng nhập liệu kiểu Excel',
    'summary': 'Nhập nhiều bút toán liên tiếp trên một lưới giống sổ Nhật ký chung trong Excel, '
               'kiểm tra theo ràng buộc tự cấu hình rồi ghi sổ hàng loạt',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger', 'lfood_importer'],
    'data': [
        'security/ir.model.access.csv',
        'data/entry_data.xml',
        'views/entry_views.xml',
    ],
    'installable': True,
}
