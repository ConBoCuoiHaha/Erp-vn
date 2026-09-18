{
    'name': 'LiFeOOD - Nghiên cứu phát triển sản phẩm',
    'summary': 'Dự án sản phẩm mới, công thức theo phiên bản (chốt thì khóa), mẫu thử và đánh giá cảm quan, kiểm nghiệm, '
               'Giám đốc duyệt công thức; chỉ nhóm R&D và Giám đốc truy cập',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/rnd_views.xml',
    ],
    'installable': True,
}
