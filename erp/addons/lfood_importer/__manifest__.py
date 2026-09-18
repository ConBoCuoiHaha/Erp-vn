{
    'name': 'LiFeOOD - Nhập dữ liệu ban đầu',
    'summary': 'Nhập đối tác, mặt hàng, số dư đầu kỳ tài khoản, công nợ đầu kỳ, tồn kho đầu kỳ, tài sản cố định từ tệp '
               'Excel hoặc CSV bất kỳ: app đọc tiêu đề, tự đoán cột, cho sửa ánh xạ, kiểm tra rồi mới nhập',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger', 'lfood_stock', 'lfood_asset'],
    'data': [
        'security/ir.model.access.csv',
        'views/importer_views.xml',
    ],
    'installable': True,
}
