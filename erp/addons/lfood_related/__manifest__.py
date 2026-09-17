{
    'name': 'LiFeOOD - Giao dịch liên kết',
    'summary': 'Đánh dấu bên liên kết, tổng hợp giao dịch liên kết trong năm, khống chế chi phí lãi vay 30% và chuyển phần vượt '
               '5 năm theo Nghị định 255/2026/NĐ-CP, đưa lãi vay không được trừ vào quyết toán thuế TNDN',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_admin', 'lfood_ledger', 'lfood_cit', 'lfood_loan', 'lfood_sale'],
    'data': [
        'data/legal_params.xml',
        'views/related_views.xml',
    ],
    'installable': True,
}
