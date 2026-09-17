{
    'name': 'LiFeOOD - Chất lượng, truy xuất, thu hồi',
    'summary': 'Truy xuất nguồn gốc theo lô một bước trước, một bước sau (Luật An toàn thực phẩm Điều 54, Nghị định '
               '46/2026/NĐ-CP), đợt thu hồi sản phẩm: cách ly lô, danh sách khách hàng, thông báo, nhập hàng thu hồi, '
               'tỷ lệ thu hồi, báo cáo kết quả',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_stock', 'lfood_stock_control', 'lfood_promotion', 'lfood_reminder', 'lfood_payroll'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'data/compliance_params.xml',
        'views/quality_views.xml',
        'views/qc_views.xml',
        'views/compliance_views.xml',
    ],
    'installable': True,
}
