{
    'name': 'LiFeOOD - Nền tảng',
    'summary': 'Vai trò người dùng, pháp nhân, menu và giao diện trắng xám cho ERP LiFeOOD',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [
        'security/lfood_groups.xml',
        'views/menus.xml',
        'views/res_company_views.xml',
        'data/companies.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'lfood_base/static/src/scss/lfood_theme.scss',
        ],
    },
    'post_init_hook': 'post_init_lang',
    'application': True,
    'installable': True,
}
