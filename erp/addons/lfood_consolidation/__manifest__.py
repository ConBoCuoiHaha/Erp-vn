{
    'name': 'LiFeOOD - Hợp nhất hai pháp nhân',
    'summary': 'Đối chiếu giao dịch mua bán nội bộ giữa Văn phòng và Nhà máy; báo cáo quản trị hợp nhất B01, B02 sau loại trừ '
               'công nợ nội bộ, doanh thu và giá vốn nội bộ, lãi chưa thực hiện trong hàng tồn kho',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_ledger', 'lfood_stock', 'lfood_sale', 'lfood_intercompany'],
    'data': [
        'security/ir.model.access.csv',
        'views/consolidation_views.xml',
    ],
    'installable': True,
}
