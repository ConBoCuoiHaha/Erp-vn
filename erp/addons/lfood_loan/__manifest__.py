{
    'name': 'LiFeOOD - Vay và lãi vay',
    'summary': 'Hợp đồng vay, giải ngân Có 3411, trích lãi theo dư nợ thực tế từng ngày Nợ 635 / Có 335, phiếu trả gốc, '
               'trả lãi, tự tất toán; ghi riêng phần lãi vượt 20%/năm không được trừ khi tính thuế TNDN',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/data.xml',
        'views/loan_views.xml',
    ],
    'installable': True,
}
