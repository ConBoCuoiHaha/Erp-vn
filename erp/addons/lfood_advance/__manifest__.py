{
    'name': 'LiFeOOD - Tạm ứng',
    'summary': 'Giấy đề nghị tạm ứng có duyệt, phiếu chi tạm ứng, bảng thanh toán tạm ứng theo chứng từ gốc, '
               'nộp lại hoặc trừ lương phần chi không hết, chi bổ sung, hóa đơn đưa lên bảng kê mua vào',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_ledger', 'lfood_vat', 'lfood_payroll'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'views/advance_views.xml',
    ],
    'installable': True,
}
