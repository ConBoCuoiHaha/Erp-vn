import html, os, sys, io
from data import GROUPS

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'nghiepvu-lifeood.html')
e = lambda s: html.escape(s, quote=True)

ALL = [it for g in GROUPS for it in g['items']]
codes = [it['code'] for it in ALL]
assert len(codes) == len(set(codes)), 'trùng mã'
N = len(ALL)
NEW = sum(it['new'] for it in ALL)
PH = {p: sum(1 for it in ALL if it['phase'] == p) for p in (1, 2, 3)}
LAW = sum(1 for it in ALL if it['law'])

CSS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'style.css'), encoding='utf-8').read()

# ---- bảng tổng theo nhóm
sum_rows = ''
for g in GROUPS:
    its = g['items']
    c = lambda p: sum(1 for it in its if it['phase'] == p)
    sum_rows += f'''<tr><td class="b"><a href="#g-{g["code"].lower()}">{e(g["name"])}</a></td>
<td class="n">{len(its)}</td><td class="n">{c(1) or "–"}</td><td class="n">{c(2) or "–"}</td><td class="n">{c(3) or "–"}</td><td class="n">{sum(it["new"] for it in its) or "–"}</td></tr>'''

# ---- danh sách
lists = ''
for g in GROUPS:
    rows = ''
    for it in g['items']:
        law = f'<div class="law">{e(it["law"])}</div>' if it['law'] else ''
        tag = '<span class="chip new">mới</span>' if it['new'] else ''
        rows += f'''<tr data-p="{it["phase"]}" data-new="{int(it["new"])}" data-q="{e((it["code"]+" "+it["name"]+" "+it["desc"]+" "+it["law"]).lower())}">
<td class="code">{it["code"]}</td>
<td><div class="nm">{e(it["name"])} {tag}</div><div class="ds">{e(it["desc"])}</div>{law}</td>
<td class="ph"><span class="chip p{it["phase"]}">GĐ{it["phase"]}</span></td></tr>'''
    lists += f'''<div class="grp" id="g-{g["code"].lower()}" data-grp>
<h3>{e(g["name"])} <span class="cnt" data-cnt>{len(g["items"])}</span></h3>
<div class="tbl"><table class="list"><thead><tr><th style="width:84px">Mã</th><th>Nghiệp vụ</th><th style="width:70px">Giai đoạn</th></tr></thead><tbody>{rows}</tbody></table></div>
</div>'''

PAGE = f'''<title>Danh mục nghiệp vụ ERP LiFeOOD</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
<div class="page">
<nav class="toc" aria-label="Mục lục"><b>Mục lục</b><ol>
<li><a href="#tong">1. Tổng số nghiệp vụ</a></li>
<li><a href="#phap-ly">2. Thay đổi pháp luật 2026</a></li>
<li><a href="#tinh">3. Cách tính lương, bảo hiểm, thuế</a></li>
<li><a href="#danh-sach">4. Danh sách {N} nghiệp vụ</a></li>
{"".join(f'<li class="sub"><a href="#g-{g["code"].lower()}">{e(g["name"])}</a></li>' for g in GROUPS)}
<li><a href="#luu-y">5. Lưu ý</a></li>
<li><a href="#nguon">Nguồn</a></li>
</ol></nav>
<main>
<header class="doc">
  <div class="eyebrow">Danh mục nghiệp vụ · Công ty LiFeOOD · 14/09/2026</div>
  <h1>Danh mục nghiệp vụ ERP LiFeOOD</h1>
  <p class="lede">Toàn bộ nghiệp vụ app ERP nội bộ sẽ đảm nhận sau khi bổ sung phần thuế, tiền lương, bảo hiểm, lao động, an toàn thực phẩm và bảo vệ dữ liệu cá nhân theo quy định có hiệu lực năm 2026. Mỗi nghiệp vụ là một quy trình có chứng từ hoặc thao tác riêng mà người dùng thực hiện trên app.</p>
  <div class="big">
    <div class="hero"><strong>{N}</strong><span>nghiệp vụ</span></div>
    <div><strong>{len(GROUPS)}</strong><span>nhóm</span></div>
    <div><strong>{NEW}</strong><span>bổ sung lần này</span></div>
    <div><strong>{LAW}</strong><span>gắn căn cứ pháp lý</span></div>
    <div><strong>{PH[1]} · {PH[2]} · {PH[3]}</strong><span>giai đoạn 1 · 2 · 3</span></div>
  </div>
</header>

<section id="tong">
<h2><span class="no">01</span>Tổng số nghiệp vụ theo nhóm</h2>
<p class="intro">Giai đoạn 1 là phần thay MISA về kế toán và thuế. So với lộ trình trước, <b>tiền lương, bảo hiểm và lao động được đưa lên giai đoạn 2</b> vì đây là nghĩa vụ phải làm hằng tháng và vừa có nhiều thay đổi luật.</p>
<div class="tbl"><table>
<thead><tr><th>Nhóm</th><th class="n">Tổng</th><th class="n">GĐ1</th><th class="n">GĐ2</th><th class="n">GĐ3</th><th class="n">Mới bổ sung</th></tr></thead>
<tbody>{sum_rows}</tbody>
<tfoot><tr><td>Cộng</td><td class="n">{N}</td><td class="n">{PH[1]}</td><td class="n">{PH[2]}</td><td class="n">{PH[3]}</td><td class="n">{NEW}</td></tr></tfoot>
</table></div>
</section>

{open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'legal.html'), encoding='utf-8').read()}

<section id="danh-sach">
<h2><span class="no">04</span>Danh sách {N} nghiệp vụ</h2>
<p class="intro">Lọc theo giai đoạn hoặc chỉ xem phần mới bổ sung. Dòng có căn cứ pháp lý ghi văn bản bên dưới.</p>
<div class="filters">
  <input id="q" type="search" placeholder="Tìm nghiệp vụ, mã, văn bản..." aria-label="Tìm nghiệp vụ">
  <div class="seg" role="group" aria-label="Giai đoạn">
    <button data-ph="0" class="on">Tất cả</button><button data-ph="1">GĐ1</button><button data-ph="2">GĐ2</button><button data-ph="3">GĐ3</button>
  </div>
  <label class="chk"><input type="checkbox" id="onlynew"> Chỉ mục mới bổ sung</label>
  <span class="shown" id="shown">{N} nghiệp vụ</span>
</div>
{lists}
</section>

<section id="luu-y">
<h2><span class="no">05</span>Lưu ý</h2>
<ul class="gaps">
  <li><b>Tham số pháp lý phải có ngày hiệu lực, không viết cứng vào code</b><span>Lương cơ sở đổi ngay giữa năm 2026 (01/7), nên bảng lương tháng 6 và tháng 7 dùng mức trần bảo hiểm khác nhau. App lưu mỗi tham số kèm ngày bắt đầu áp dụng; luật đổi thì kế toán nhập dòng mới, không phải sửa code.</span></li>
  <li><b>Tài liệu này không thay tư vấn pháp lý</b><span>Kế toán trưởng, nhân sự và QA cần xác nhận từng tham số trước khi chạy thật, đặc biệt các điểm dưới đây.</span></li>
  <li><b>Vùng lương tối thiểu của Nhà máy</b><span>Kết quả tra cứu cho thấy xã Mỹ Hạnh thuộc vùng I sau sắp xếp địa giới; nhân sự đối chiếu lại phụ lục Nghị định 293/2025/NĐ-CP.</span></li>
  <li><b>Giới hạn làm thêm 300 giờ/năm</b><span>Chỉ áp dụng cho một số ngành và phải thông báo cơ quan lao động; cần xác nhận ngành chế biến thực phẩm của công ty thuộc diện này.</span></li>
  <li><b>Văn bản hướng dẫn chưa đọc toàn văn</b><span>Thông tư 30/2025/TT-BTC (khấu hao), văn bản hướng dẫn Luật Thuế TNCN 109/2025 và Luật Quản lý thuế 108/2025, quy định an toàn thực phẩm mới. Mẫu tờ khai có thể đổi sau 01/7/2026.</span></li>
  <li><b>Lệ phí môn bài đã bãi bỏ từ 01/01/2026</b><span>Không đưa nghiệp vụ kê khai, nộp lệ phí môn bài vào app.</span></li>
</ul>
</section>

<section id="nguon">
<h2>Nguồn tham khảo</h2>
<ul class="src">
<li><a href="https://thuvienphapluat.vn/phap-luat/toan-van-thong-tu-992025ttbtc-che-do-ke-toan-doanh-nghiep-thay-the-thong-tu-200-tu-01012026-ra-sao-239165.html">Thông tư 99/2025/TT-BTC chế độ kế toán doanh nghiệp</a></li>
<li><a href="https://luatvietnam.vn/tin-van-ban-moi/chinh-thuc-giam-thue-gtgt-xuong-8-tu-ngay-01-7-2025-den-het-31-12-2026-186-102680-article.html">Giảm thuế GTGT còn 8% tới hết 31/12/2026</a></li>
<li><a href="https://ihoadon.vn/hddt/thanh-toan-khong-dung-tien-mat-tu-01-7-2025-tai-nghi-dinh-181-2025-nd-cp.html">Thanh toán không dùng tiền mặt từ 5 triệu, Nghị định 181/2025</a></li>
<li><a href="https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Luat-Thue-thu-nhap-doanh-nghiep-2025-so-67-2025-QH15-580594.aspx">Luật Thuế TNDN 67/2025/QH15</a></li>
<li><a href="https://luatvietnam.vn/thue-phi-le-phi/diem-moi-nghi-dinh-320-2025-nd-cp-ve-thue-tndn-565-105990-article.html">Điểm mới Nghị định 320/2025/NĐ-CP</a></li>
<li><a href="https://luatvietnam.vn/tin-van-ban-moi/chinh-thuc-bai-bo-le-phi-mon-bai-tu-01-01-2026-186-102164-article.html">Bãi bỏ lệ phí môn bài từ 01/01/2026</a></li>
<li><a href="https://www.ey.com/vi_vn/technical/tax/tax-and-law-updates/luat-thue-thu-nhap-ca-nhan-109-2025-qh15">Luật Thuế TNCN 109/2025/QH15 (EY)</a></li>
<li><a href="https://luatvietan.vn/lo-trinh-ap-dung-luat-thue-tncn-nam-2026-cap-nhat-luat-so-109-2025-qh15-moi-nhat.html">Lộ trình áp dụng Luật Thuế TNCN 2026</a></li>
<li><a href="https://vietnamnet.vn/5-thay-doi-lon-cua-luat-thue-thu-nhap-ca-nhan-2025-tu-1-7-2481753.html">5 thay đổi lớn của Luật Thuế TNCN</a></li>
<li><a href="https://thanhnien.vn/luong-toi-thieu-vung-tang-tu-112026-ai-duoc-tang-tang-bao-nhieu-185260101182419626.htm">Lương tối thiểu vùng từ 01/01/2026</a></li>
<li><a href="https://thuvienphapluat.vn/phap-luat/muc-luong-toi-thieu-vung-tinh-tay-ninh-tu-112026-theo-nghi-dinh-2932025ndcp-chi-tiet-ra-sao-241020.html">Lương tối thiểu vùng tỉnh Tây Ninh 2026</a></li>
<li><a href="https://thuvienphapluat.vn/phap-luat-doanh-nghiep/bai-viet/bang-luong-co-so-2026-va-muc-luong-co-so-moi-tu-01-7-2026-18709.html">Lương cơ sở mới từ 01/7/2026</a></li>
<li><a href="https://luatvietnam.vn/bao-hiem/ty-le-dong-bhxh-cua-doanh-nghiep-va-nguoi-lao-dong-563-100379-article.html">Tỷ lệ đóng BHXH năm 2026</a></li>
<li><a href="https://luatvietnam.vn/lao-dong-tien-luong/muc-dong-doan-phi-kinh-phi-cong-doan-562-23118-article.html">Kinh phí công đoàn 2026</a></li>
<li><a href="https://www.talentnetgroup.com/vn/vi/phan-tich-chuyen-sau/tinh-luong-lam-them-gio">Tiền lương làm thêm giờ 2026</a></li>
<li><a href="https://xaydungchinhsach.chinhphu.vn/nghi-dinh-70-2025-nd-cp-sua-doi-bo-sung-quy-dinh-ve-hoa-don-chung-tu-11925032321512617.htm">Nghị định 70/2025/NĐ-CP về hóa đơn, chứng từ</a></li>
<li><a href="https://xaydungchinhsach.chinhphu.vn/toan-van-luat-quan-ly-thue-co-hieu-luc-tu-1-7-2026-119260626174633402.htm">Luật Quản lý thuế có hiệu lực từ 01/7/2026</a></li>
<li><a href="https://congbao.chinhphu.vn/van-ban/luat-so-91-2025-qh15-45578.htm">Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15</a></li>
<li><a href="https://vanban.chinhphu.vn/?pageid=27160&docid=213853&classid=1&typegroupid=6">Thông tư 30/2025/TT-BTC sửa Thông tư 45/2013</a></li>
</ul>
</section>
<footer>Mở rộng từ “Bản thiết kế ERP LiFeOOD” và “Phương án công nghệ ERP LiFeOOD”. Số liệu pháp lý tra cứu ngày 14/09/2026.</footer>
</main></div>
<script>
(function(){{
  const q = document.getElementById('q'), onlynew = document.getElementById('onlynew'), shown = document.getElementById('shown');
  let ph = '0';
  function apply(){{
    const s = q.value.trim().toLowerCase(); let total = 0;
    document.querySelectorAll('[data-grp]').forEach(g => {{
      let c = 0;
      g.querySelectorAll('tbody tr').forEach(tr => {{
        const ok = (ph === '0' || tr.dataset.p === ph) && (!onlynew.checked || tr.dataset.new === '1') && (!s || tr.dataset.q.includes(s));
        tr.hidden = !ok; if (ok) c++;
      }});
      g.querySelector('[data-cnt]').textContent = c;
      g.hidden = c === 0; total += c;
    }});
    shown.textContent = total + ' nghiệp vụ';
  }}
  q.addEventListener('input', apply); onlynew.addEventListener('change', apply);
  document.querySelectorAll('[data-ph]').forEach(b => b.addEventListener('click', () => {{
    ph = b.dataset.ph; document.querySelectorAll('[data-ph]').forEach(x => x.classList.toggle('on', x === b)); apply();
  }}));
  window.addEventListener('beforeprint', () => {{ q.value=''; onlynew.checked=false; ph='0'; apply(); }});
}})();
</script>'''

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write(PAGE)
print('OUT', OUT, 'N', N, 'NEW', NEW, 'PH', PH, 'LAW', LAW)
for g in GROUPS:
    print(f"\n**{g['name']} ({len(g['items'])})**")
    print(' · '.join(f"{it['code']} {it['name']}" for it in g['items']))
