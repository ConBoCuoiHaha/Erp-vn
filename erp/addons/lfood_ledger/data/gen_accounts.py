"""Sinh accounts.xml từ tt99_phu_luc_ii.txt (Phụ lục II Thông tư 99/2025/TT-BTC) + tài khoản chi tiết công ty."""
import html, os

HERE = os.path.dirname(os.path.abspath(__file__))
# 334, 337, 171: B01 lấy cả dư Nợ (135, 134, 164) lẫn dư Có (315, 318, 325) nên phải là lưỡng tính
BOTH = {'131', '136', '138', '171', '331', '333', '334', '336', '337', '338', '413', '421', '911'}
DEBIT_CONTRA = {'419', '521'}
CREDIT_CONTRA = {'214', '229'}
COMPANY_DETAIL = [
    ('1311', 'Phải thu của khách hàng (chi tiết công ty)'),
    ('3311', 'Phải trả cho người bán (chi tiết công ty)'),
    ('2111', 'Nhà cửa, vật kiến trúc'),
    ('2112', 'Máy móc, thiết bị'),
    ('2113', 'Phương tiện vận tải, truyền dẫn'),
    ('2114', 'Thiết bị, dụng cụ quản lý'),
]


def nature(code):
    c3 = code[:3]
    if c3 in BOTH:
        return 'both'
    if c3 in DEBIT_CONTRA:
        return 'debit'
    if c3 in CREDIT_CONTRA:
        return 'credit'
    return 'debit' if code[0] in '1268' else 'credit' if code[0] in '3457' else 'both'


rows = []
for line in open(os.path.join(HERE, 'tt99_phu_luc_ii.txt'), encoding='utf-8'):
    parts = [p.strip() for p in line.split('|')]
    code, name = (parts[1], parts[2]) if len(parts) == 3 else (parts[0], parts[1])
    rows.append((code, name, True))
rows += [(c, n, False) for c, n in COMPANY_DETAIL]
codes = {c for c, _, _ in rows}
assert len([c for c in codes if len(c) == 3]) == 71, 'Thông tư 99 có 71 tài khoản cấp 1'

out = ['<?xml version="1.0" encoding="utf-8"?>',
       '<!-- Sinh tự động bằng gen_accounts.py từ Phụ lục II Thông tư 99/2025/TT-BTC. Không sửa tay. -->',
       '<odoo>', '<data noupdate="1">']
for code, name, official in sorted(rows, key=lambda r: r[0]):
    parent = next((code[:k] for k in range(len(code) - 1, 2, -1) if code[:k] in codes), None)
    out.append('    <record id="acc_%s" model="lfood.account">' % code)
    out.append('        <field name="code">%s</field><field name="name">%s</field>' % (code, html.escape(name)))
    out.append('        <field name="nature">%s</field><field name="is_official" eval="%s"/>' % (nature(code), official))
    if parent:
        out.append('        <field name="parent_id" ref="acc_%s"/>' % parent)
    out.append('    </record>')
out.append('</data>')
# bản ghi noupdate không được ghi lại khi nâng cấp: tính chất tài khoản đặt lại mỗi lần -u cho khớp quy tắc trên
out.append('<function model="lfood.account" name="write" eval="[[%s], {\'nature\': \'both\'}]"/>'
           % ', '.join("ref('acc_%s')" % c for c, _, _ in sorted(rows) if nature(c) == 'both'))
out.append('</odoo>')
open(os.path.join(HERE, 'accounts.xml'), 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print(len(rows), 'accounts')
