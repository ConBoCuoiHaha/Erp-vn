{
    'name': 'LiFeOOD - Tạm ứng lương, thưởng, thuế TNCN',
    'summary': 'Tạm ứng lương giữa kỳ trừ khi tính lương; đưa khen thưởng, lương tháng 13 vào bảng lương; khấu trừ 10% '
               'thu nhập vãng lai, 20% cá nhân không cư trú, cam kết thu nhập thấp (Nghị định 253/2026/NĐ-CP Điều 50, 64); '
               'quyết toán thuế TNCN năm thay người lao động được ủy quyền (Điều 51), dữ liệu chứng từ khấu trừ',
    'version': '19.0.1.0.0',
    'category': 'LiFeOOD',
    'author': 'LiFeOOD',
    'license': 'LGPL-3',
    'depends': ['lfood_base', 'lfood_audit', 'lfood_voucher', 'lfood_ledger', 'lfood_payroll', 'lfood_hr_records'],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/params.xml',
        'views/pit_views.xml',
    ],
    'installable': True,
}
