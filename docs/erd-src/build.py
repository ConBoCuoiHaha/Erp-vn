import html
import os
import core, d1, d2, d3, d4
import s1, s2, s3
from core import MODULES, ENTITIES, RELS
from s1 import KEY, STATE, FOCUS, FOCUS_EXTRA
from s2 import FLOWS
from tpl import HEAD, MECH_SVG, RULES, FLOWCHART, GAPS

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'erd-lifeood.html')
esc = lambda s: html.escape(s, quote=False)
MOD = {m['code']: m for m in MODULES}


def short(s, n=36):
    s = s.replace('"', "'")
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(' ', 1)[0]
    return cut + '…'


def er_block(names, rels, attrs=True):
    out = ['erDiagram']
    for n in names:
        e = ENTITIES[n]
        if not attrs:
            continue
        out.append(f'  {n} {{')
        for f in e['fields']:
            key = f' {f["k"]}' if f['k'] else ''
            out.append(f'    {f["t"]} {f["f"]}{key} "{short(f["m"])}"')
        out.append('  }')
    for a, card, b, lab in rels:
        out.append(f'  {a} {card} {b} : "{lab}"')
    if not attrs:
        present = {x for r in rels for x in (r[0], r[2])}
        for n in names:
            if n not in present:
                out.append(f'  {n} {{\n    id id PK\n  }}')
    return '\n'.join(out)


def mermaid(src, cap, label=''):
    return f'''<figure class="diagram"><pre class="mermaid">
{esc(src)}
</pre></figure>{f'<figcaption>{cap}</figcaption>' if cap else ''}'''


def seq_fig(code, title, why, src):
    return f'''<div id="qt-{code.lower()}">
  <h3><span class="stepno">{code}</span>{esc(title)}</h3>
  <p class="why">{esc(why)}</p>
  <figure class="diagram"><pre class="mermaid">
{esc(src)}
</pre></figure>
</div>'''


# ---------------------------------------------------------------- tổng quan
CORE = ['CONG_TY', 'NGUOI_DUNG', 'NHAN_VIEN', 'PHONG_BAN', 'DOI_TAC', 'YEU_CAU_DUYET',
        'HE_THONG_TAI_KHOAN', 'BUT_TOAN', 'DONG_BUT_TOAN', 'BAO_CAO_CHOT', 'THANH_TOAN',
        'KHOAN_MUC_CHI_PHI', 'NGAN_SACH', 'DON_MUA', 'CHUNG_TU_MUA_DV', 'PHIEN_BAN_CHUNG_TU',
        'DON_BAN', 'SAN_PHAM', 'LO_HANG', 'PHIEU_KHO', 'TON_KHO', 'DU_AN_RD',
        'CONG_THUC', 'PHIEU_KIEM_TRA', 'TAI_SAN_CO_DINH', 'PHIEU_LUONG']
CORE_EXTRA = [
    ('DONG_BUT_TOAN', '}o--o{', 'BAO_CAO_CHOT', 'tổng hợp khi chốt'),
    ('PHIEU_LUONG', '}o--o|', 'BUT_TOAN', 'ghi sổ lương'),
    ('NGAN_SACH', '}o--o{', 'KHOAN_MUC_CHI_PHI', 'kế hoạch theo'),
    ('PHIEU_KHO', '||--o{', 'TON_KHO', 'cập nhật'),
    ('TAI_SAN_CO_DINH', '|o--o{', 'BUT_TOAN', 'khấu hao'),
    ('DU_AN_RD', '||--o{', 'CONG_THUC', 'có phiên bản'),
    ('CHUNG_TU_MUA_DV', '|o--o{', 'YEU_CAU_DUYET', 'trình duyệt'),
    ('DON_MUA', '|o--o{', 'YEU_CAU_DUYET', 'trình duyệt'),
    ('PHIEN_BAN_CHUNG_TU', '}o--o{', 'KHOAN_MUC_CHI_PHI', 'dòng gắn khoản mục'),
    ('PHIEU_KHO', '}o--o{', 'LO_HANG', 'theo lô'),
]
core_rels = [(r['a'], r['card'], r['b'], r['label']) for r in RELS if r['a'] in CORE and r['b'] in CORE]
seen, uniq = set(), []
for r in core_rels + CORE_EXTRA:
    k = (r[0], r[2], r[3])
    if k not in seen:
        seen.add(k); uniq.append(r)
core_rels = uniq

focus_rels = [(r['a'], r['card'], r['b'], r['label']) for r in RELS if r['a'] in FOCUS and r['b'] in FOCUS] + FOCUS_EXTRA

n_ent, n_rel = len(ENTITIES), len(RELS)
n_fld = sum(len(e['fields']) for e in ENTITIES.values())
all_flows = [f for m in MODULES for f in FLOWS.get(m['code'], [])]
n_seq = len(KEY) + len(all_flows)

# ---------------------------------------------------------------- HTML
P = [HEAD, '<div class="page">']

toc = ['<nav class="toc" aria-label="Mục lục"><b>Mục lục</b><ol>',
       '<li><a href="#pham-vi">1. Phạm vi chức năng</a></li>',
       '<li><a href="#phan-he">2. Sơ đồ phân hệ</a></li>',
       '<li><a href="#trong-tam">3. ★ Sửa chứng từ sau khi Cất</a></li>',
       '<li><a href="#erd-tong">4. ERD tổng quát</a></li>',
       '<li><a href="#erd-chi-tiet">5. ERD chi tiết</a></li>']
toc += [f'<li class="sub"><a href="#erd-{m["code"]}">{esc(m["name"])}</a></li>' for m in MODULES]
toc += ['<li><a href="#tu-dien">6. Từ điển dữ liệu</a></li>',
        '<li><a href="#quy-trinh">7. Quy trình thao tác</a></li>']
toc += [f'<li class="sub"><a href="#qt-{m["code"]}">{esc(m["name"])}</a></li>' for m in MODULES if FLOWS.get(m['code'])]
toc += ['<li><a href="#quyet-dinh">8. Việc cần quyết định</a></li>', '</ol></nav>']
P += toc

P.append(f'''<main>
<header class="doc">
  <div class="eyebrow">Tài liệu thiết kế · Công ty LiFeOOD · 13/09/2026</div>
  <h1>Bản thiết kế ERP LiFeOOD</h1>
  <p class="lede">Thiết kế toàn bộ hệ thống ERP nội bộ cho công ty thương mại và sản xuất thực phẩm: bán hàng, mua hàng, kho theo lô, chất lượng HACCP, R&D tách riêng, tài sản, nhân sự và kế toán, tham chiếu chức năng Odoo Enterprise. Trọng tâm là chứng từ mua dịch vụ sửa được sau khi Cất, tự động tính lại số liệu mà báo cáo không đổi.</p>
  <div class="facts">
    <div class="fact"><strong>{len(MODULES)}</strong><span>phân hệ</span></div>
    <div class="fact"><strong>{n_ent}</strong><span>thực thể</span></div>
    <div class="fact"><strong>{n_rel}</strong><span>quan hệ</span></div>
    <div class="fact"><strong>{n_fld}</strong><span>trường dữ liệu</span></div>
    <div class="fact"><strong>{n_seq}</strong><span>sơ đồ tuần tự</span></div>
  </div>
</header>''')

# 1. phạm vi
rows = ''.join(f'''<tr><td class="mn">{esc(m["name"])}</td><td>{esc(m["features"])}</td>
<td class="od">{esc(m["odoo"])}</td><td class="num">{sum(1 for e in ENTITIES.values() if e["mod"] == m["code"])}</td><td class="ph">{esc(m["phase"])}</td></tr>'''
               for m in MODULES)
P.append(f'''<section id="pham-vi">
<h2><span class="no">01</span>Phạm vi chức năng</h2>
<p class="intro">{len(MODULES)} phân hệ, mỗi phân hệ ghi rõ ứng dụng Odoo Enterprise tương đương để đối chiếu. Cột giai đoạn là đề xuất thứ tự làm: giai đoạn 1 gồm những gì kế toán cần ngay để thay MISA.</p>
<div class="scope"><table>
<thead><tr><th>Phân hệ</th><th>Chức năng</th><th>Tham chiếu Odoo</th><th>Thực thể</th><th>Giai đoạn</th></tr></thead>
<tbody>{rows}</tbody></table></div>
</section>''')

# 2. phân hệ
P.append(f'''<section id="phan-he">
<h2><span class="no">02</span>Sơ đồ phân hệ</h2>
<p class="intro">Các phân hệ nghiệp vụ trao đổi hàng và chứng từ với nhau, rồi cùng đổ bút toán về Kế toán. Theo đúng sơ đồ luồng ERP ban đầu của công ty, bổ sung khoản mục chi phí, ngân sách và chứng từ mua dịch vụ có phiên bản.</p>
{mermaid(FLOWCHART, 'Nét liền là chuyển dữ liệu hoặc chứng từ; nét đứt là kiểm tra hoặc kiểm soát, không sinh số liệu.')}
</section>''')

# 3. trọng tâm
P.append(f'''<section id="trong-tam">
<h2><span class="no">03</span>★ Sửa chứng từ mua dịch vụ sau khi Cất <span class="tag star">trọng tâm</span></h2>
<p class="intro">Yêu cầu: sau khi bấm Cất vẫn có nút Sửa, sửa thẳng trên số liệu lúc mua vào, hệ thống tự tính lại các con số liên quan, và báo cáo không thay đổi. Cách làm: không ghi đè chứng từ mà lưu thành các phiên bản.</p>
{MECH_SVG}
{RULES}
<h3 class="grp">Vòng đời chứng từ</h3>
{mermaid(STATE, 'Đang sửa luôn quay về Đã cất: lưu thì thêm phiên bản, hủy thì bỏ bản nháp. Chứng từ đã cất chỉ hủy được bằng bút toán đảo.')}
<h3 class="grp">ERD phần trọng tâm</h3>
{mermaid(er_block(FOCUS, focus_rels), 'CHUNG_TU_MUA_DV giữ hai con trỏ: phien_ban_hien_hanh_id để xem và sửa tiếp, phien_ban_bao_cao_id để ghi sổ. Hai con trỏ chỉ trùng nhau lúc mới Cất hoặc sau khi K6 được duyệt.')}
<h3 class="grp">Quy trình trọng tâm</h3>
<div class="stack">{''.join(seq_fig(*k) for k in KEY)}</div>
</section>''')

# 4. ERD tổng quát
P.append(f'''<section id="erd-tong">
<h2><span class="no">04</span>ERD tổng quát</h2>
<p class="intro">{len(CORE)} thực thể xương sống và quan hệ giữa các phân hệ, chưa kèm thuộc tính. Đủ {n_ent} thực thể có thuộc tính nằm ở mục 5.</p>
{mermaid(er_block(CORE, core_rels, attrs=False), 'Mọi nhánh cuối cùng đều chạy về BUT_TOAN rồi DONG_BUT_TOAN; báo cáo chỉ đọc từ đó.')}
<div class="legend">
  <div><code>||</code><span>đúng một</span></div>
  <div><code>|o</code><span>không hoặc một</span></div>
  <div><code>|{{</code><span>một hoặc nhiều</span></div>
  <div><code>o{{</code><span>không hoặc nhiều</span></div>
</div>
</section>''')

# 5. ERD chi tiết
parts = []
for m in MODULES:
    names = [n for n, e in ENTITIES.items() if e['mod'] == m['code']]
    rels = [(r['a'], r['card'], r['b'], r['label']) for r in RELS if r['mod'] == m['code']]
    ext = sorted({x for r in rels for x in (r[0], r[2]) if x not in names})
    cap = ('Thực thể không có thuộc tính trong hình thuộc phân hệ khác: ' + ', '.join(ext) + '.') if ext else ''
    parts.append(f'''<div class="mod" id="erd-{m["code"]}">
<h3>{esc(m["name"])} <span class="tag c">{len(names)} thực thể</span></h3>
<p class="why">{esc(m["features"])}</p>
{mermaid(er_block(names, rels), cap)}
</div>''')
P.append(f'''<section id="erd-chi-tiet">
<h2><span class="no">05</span>ERD chi tiết theo phân hệ</h2>
<p class="intro">Tên trường viết không dấu để dùng làm tên cột; chú thích tiếng Việt rút gọn trong hình, bản đầy đủ ở mục 6. <span class="key pk">PK</span> khóa chính, <span class="key fk">FK</span> khóa ngoại, <span class="key">UK</span> không được trùng.</p>
{''.join(parts)}
</section>''')

# 6. từ điển
def keytag(k):
    return ' '.join(f'<span class="key {"pk" if x == "PK" else "fk" if x == "FK" else ""}">{x}</span>'
                    for x in [y.strip() for y in k.split(',')] if x)

dparts = []
for m in MODULES:
    items = []
    for n, e in ENTITIES.items():
        if e['mod'] != m['code']:
            continue
        rows = ''.join(f'<tr><td class="f">{f["f"]}</td><td class="t">{f["t"]}</td><td class="k">{keytag(f["k"])}</td><td>{esc(f["m"])}</td></tr>'
                       for f in e['fields'])
        items.append(f'''<details class="ent">
<summary><div><span class="nm">{n}</span> · <span class="vn">{esc(e["vn"])}</span></div><span class="od">{esc(e["odoo"])}</span><div class="ds">{esc(e["desc"])}</div></summary>
<div class="tw"><table><thead><tr><th>Trường</th><th>Kiểu</th><th>Khóa</th><th>Ý nghĩa</th></tr></thead><tbody>{rows}</tbody></table></div>
</details>''')
    dparts.append(f'<div class="dictmod"><h3>{esc(m["name"])}</h3><div class="dict">{"".join(items)}</div></div>')
P.append(f'''<section id="tu-dien">
<h2><span class="no">06</span>Từ điển dữ liệu</h2>
<p class="intro">{n_ent} thực thể, {n_fld} trường. Bấm từng thực thể để xem trường, kiểu, khóa và ý nghĩa; bên phải là đối tượng Odoo tương đương. Kiểu <code>money</code> là số nguyên đồng, <code>qty</code> có phần thập phân.</p>
{''.join(dparts)}
</section>''')

# 7. quy trình
qparts = []
for m in MODULES:
    fl = FLOWS.get(m['code'])
    if not fl:
        continue
    qparts.append(f'''<div id="qt-{m["code"]}"><h3 class="grp">{esc(m["name"])}</h3><div class="stack">{''.join(seq_fig(*f) for f in fl)}</div></div>''')
P.append(f'''<section id="quy-trinh">
<h2><span class="no">07</span>Quy trình thao tác</h2>
<p class="intro">Các quy trình còn lại, xếp theo phân hệ (6 quy trình trọng tâm K1–K6 ở mục 3). Khung <b>alt</b> là các nhánh loại trừ nhau, <b>opt</b> là bước tùy chọn, <b>loop</b> là bước lặp.</p>
{''.join(qparts)}
</section>''')

P.append(f'''<section id="quyet-dinh">
<h2><span class="no">08</span>Việc cần quyết định</h2>
<p class="intro">Những điểm thiết kế đang dựa trên giả định. Mỗi mục cần một quyết định trước khi viết mã.</p>
{GAPS}
</section>
<footer>Dựa trên sơ đồ luồng ERP và tài liệu ban đầu của công ty, ảnh chứng từ và báo cáo MISA, file Thử AI.xlsx và bản chạy thử. In ra PDF bằng Ctrl+P, chọn Lưu dưới dạng PDF.</footer>
</main></div>
<script>
window.addEventListener('beforeprint', () => document.querySelectorAll('details.ent').forEach(d => d.open = true));
</script>''')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(P))
print(OUT, os.path.getsize(OUT), 'entities', n_ent, 'rels', n_rel, 'fields', n_fld, 'seq', n_seq)
