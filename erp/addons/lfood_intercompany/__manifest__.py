{
    'name': 'LiFeOOD - Bán hàng giữa hai pháp nhân',
    'summary': 'Nhà máy và Văn phòng có mã số thuế riêng: một chứng từ lập hóa đơn bán bên xuất, phiếu nhập mua bên nhận, '
               'giữ nguyên lô, hạn dùng; ghi căn cứ giá giao dịch liên kết',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_sale', 'lfood_stock'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'views/transfer_views.xml',
    ],
    'installable': True,
}
