{
    'name': 'LiFeOOD - Chữ ký số',
    'summary': 'Danh sách chứng thư số (nhà cung cấp, số sê-ri, hiệu lực, người giữ token) và nhắc hạn; ghi nhận chứng từ '
               'đã ký số: tệp ký, định dạng, người ký, thời điểm ký, mã kiểm tra tệp không đổi',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_archive', 'lfood_reminder'],
    'data': [
        'security/ir.model.access.csv',
        'views/signature_views.xml',
    ],
    'installable': True,
}
