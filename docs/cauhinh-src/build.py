import html, os, sys, io
from data import SECTIONS

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), 'cauhinh-lifeood.html')
e = lambda s: html.escape(s, quote=True)
KIND = {'L': 'Theo luật', 'Q': 'Quy chế công ty', 'H': 'Hệ thống'}

ALL = [it for s in SECTIONS for it in s['items']]
N = len(ALL)
C = {k: sum(1 for it in ALL if it['kind'] == k) for k in KIND}

summary = ''.join(
    f'<tr><td class="b"><a href="#s-{s["code"].lower()}">{e(s["name"])}</a></td><td class="n">{len(s["items"])}</td>'
    + ''.join(f'<td class="n">{sum(1 for it in s["items"] if it["kind"] == k) or "–"}</td>' for k in KIND) + '</tr>'
    for s in SECTIONS)

lists = ''
for s in SECTIONS:
    rows, last = '', None
    for it in s['items']:
        g = it['group'] if it['group'] != last else ''
        last = it['group']
        rows += f'''<tr data-k="{it["kind"]}" data-q="{e((s["name"]+" "+it["group"]+" "+it["name"]+" "+it["desc"]).lower())}">
<td class="grpc">{e(g)}</td><td><div class="nm">{e(it["name"])}</div><div class="ds">{e(it["desc"])}</div></td>
<td><span class="kd k{it["kind"]}">{KIND[it["kind"]]}</span></td><td class="use">{e(it["used"])}</td></tr>'''
    lists += f'''<div class="sec" id="s-{s["code"].lower()}" data-sec>
<h3>{e(s["name"])} <span class="cnt" data-cnt>{len(s["items"])}</span></h3>
<div class="tbl"><table class="list"><thead><tr><th style="width:130px">Nhóm</th><th>Mục cấu hình</th><th style="width:130px">Loại</th><th style="width:150px">Nghiệp vụ dùng</th></tr></thead><tbody>{rows}</tbody></table></div></div>'''

CSS = open(os.path.join(HERE, 'style.css'), encoding='utf-8').read()
MOCK = open(os.path.join(HERE, 'mock.html'), encoding='utf-8').read()
RESEARCH = open(os.path.join(HERE, 'research.html'), encoding='utf-8').read()

PAGE = f'''<title>Cấu hình và giao diện ERP LiFeOOD</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
<div class="page">
<nav class="toc" aria-label="Mục lục"><b>Mục lục</b><ol>
<li><a href="#nguyen-tac">1. Nguyên tắc cấu hình</a></li>
<li><a href="#danh-muc">2. Danh mục {N} mục cấu hình</a></li>
{"".join(f'<li class="sub"><a href="#s-{s["code"].lower()}">{e(s["name"])}</a></li>' for s in SECTIONS)}
<li><a href="#giao-dien">3. Giao diện</a></li>
<li><a href="#man-mau">4. Màn hình mẫu</a></li>
<li><a href="#nghien-cuu">5. Mức độ nghiên cứu</a></li>
</ol></nav>
<main>
<header class="doc">
  <div class="eyebrow">Thiết kế cấu hình và giao diện · Công ty LiFeOOD · 14/09/2026</div>
  <h1>Cấu hình và giao diện ERP LiFeOOD</h1>
  <p class="lede">Mọi con số dùng để tính lương, bảo hiểm, thuế, phí, khấu hao, giá kho và mọi quy tắc tự động đều nằm trong mục Cấu hình, người có quyền sửa được trên màn hình mà không cần lập trình. Kèm quy ước giao diện trắng xám, đơn giản như MISA và màn hình mẫu.</p>
  <div class="facts">
    <div><strong>{N}</strong><span>mục cấu hình</span></div>
    <div><strong>{len(SECTIONS)}</strong><span>nhóm</span></div>
    <div><strong>{C["L"]}</strong><span>theo luật, có ngày hiệu lực</span></div>
    <div><strong>{C["Q"]}</strong><span>quy chế công ty</span></div>
    <div><strong>{C["H"]}</strong><span>hệ thống</span></div>
  </div>
</header>

<section id="nguyen-tac">
<h2><span class="no">01</span>Nguyên tắc cấu hình</h2>
<div class="kinds">
  <div><span class="kd kL">Theo luật</span><p>Mức tiền, tỷ lệ, ngưỡng, biểu thuế, mẫu tờ khai do Nhà nước quy định. Mỗi giá trị có <b>ngày bắt đầu, ngày kết thúc và văn bản căn cứ</b>. Thêm mức mới chứ không sửa đè; Kế toán trưởng duyệt; chạy mô phỏng trước.</p></div>
  <div><span class="kd kQ">Quy chế công ty</span><p>Chính sách do công ty tự quyết: phụ cấp, thưởng, ca làm, hạn mức duyệt, tiêu thức phân bổ, quyền sửa chứng từ. Có ngày hiệu lực và lịch sử thay đổi; Giám đốc hoặc người được giao duyệt.</p></div>
  <div><span class="kd kH">Hệ thống</span><p>Cách app chạy: định dạng số, đánh số chứng từ, kết nối, sao lưu, bảo mật. Quản trị hệ thống sửa; ghi nhật ký.</p></div>
</div>
<ul class="rules">
  <li><b>Không số nào viết cứng trong code.</b> Công thức lương, thuế, bảo hiểm gọi mã tham số (ví dụ <code>TY_LE_BH_NLD</code>, <code>TRAN_BHXH</code>), app tự lấy giá trị đúng theo ngày của chứng từ hoặc kỳ lương.</li>
  <li><b>Kỳ đã khóa sổ không bị tính lại</b> khi tham số thay đổi; chỉ kỳ đang mở mới áp giá trị mới.</li>
  <li><b>Quyền sửa cấu hình tách riêng</b> với quyền nhập chứng từ. Mọi thay đổi ghi ai sửa, lúc nào, giá trị cũ và mới.</li>
  <li><b>Nhập sai thì chặn ngay:</b> tỷ lệ ngoài 0–100%, ngày hiệu lực chồng lấn, thiếu văn bản căn cứ với mục theo luật.</li>
  <li><b>Bản thử và bản thật dùng chung gói cấu hình:</b> chỉnh và kiểm tra trên bản thử, xuất gói, nhập vào bản thật.</li>
</ul>
</section>

<section id="danh-muc">
<h2><span class="no">02</span>Danh mục {N} mục cấu hình</h2>
<p class="intro">Mỗi mục cấu hình là một màn hình hoặc một bảng trong mục Cấu hình. Cột cuối là mã nghiệp vụ trong “Danh mục nghiệp vụ ERP LiFeOOD” dùng mục đó.</p>
<div class="tbl"><table>
<thead><tr><th>Nhóm cấu hình</th><th class="n">Tổng</th><th class="n">Theo luật</th><th class="n">Quy chế</th><th class="n">Hệ thống</th></tr></thead>
<tbody>{summary}</tbody>
<tfoot><tr><td>Cộng</td><td class="n">{N}</td><td class="n">{C["L"]}</td><td class="n">{C["Q"]}</td><td class="n">{C["H"]}</td></tr></tfoot>
</table></div>
<div class="filters">
  <input id="q" type="search" placeholder="Tìm mục cấu hình" aria-label="Tìm mục cấu hình">
  <div class="seg" role="group" aria-label="Loại">
    <button data-k="" class="on">Tất cả</button><button data-k="L">Theo luật</button><button data-k="Q">Quy chế</button><button data-k="H">Hệ thống</button>
  </div>
  <span class="shown" id="shown">{N} mục</span>
</div>
{lists}
</section>

<section id="giao-dien">
<h2><span class="no">03</span>Quy ước giao diện</h2>
<p class="intro">Phong cách cơ bản như MISA: nền trắng và xám nhạt, chữ đen xám, một màu nhấn duy nhất cho nút chính, biểu tượng nét mảnh. Không emoji, không gradient, không đổ bóng trang trí.</p>
<div class="ui">
  <div class="uic"><h4>Màu</h4>
    <div class="sw"><i style="background:#FFFFFF"></i><span>Nền nội dung</span><code>#FFFFFF</code></div>
    <div class="sw"><i style="background:#F7F7F8"></i><span>Nền trang, thanh bên</span><code>#F7F7F8</code></div>
    <div class="sw"><i style="background:#F1F1F3"></i><span>Tiêu đề bảng, ô chỉ đọc</span><code>#F1F1F3</code></div>
    <div class="sw"><i style="background:#E4E4E7"></i><span>Đường kẻ, viền ô</span><code>#E4E4E7</code></div>
    <div class="sw"><i style="background:#71717A"></i><span>Chữ phụ, nhãn</span><code>#71717A</code></div>
    <div class="sw"><i style="background:#18181B"></i><span>Chữ chính, nút chính</span><code>#18181B</code></div>
    <p class="uin">Màu trạng thái chỉ dùng cho chữ nhỏ: đỏ lỗi, vàng cảnh báo, xanh đã duyệt. Nếu sếp muốn giống MISA hơn, đổi riêng màu nút chính sang xanh lá; mọi thứ khác giữ nguyên.</p>
  </div>
  <div class="uic"><h4>Chữ và mật độ</h4>
    <ul>
      <li>Font hệ thống: Segoe UI trên Windows, như MISA</li>
      <li>Cỡ 13px cho bảng và ô nhập, 16px tiêu đề màn hình</li>
      <li>Dòng bảng cao 34px, ô nhập cao 32px</li>
      <li>Số canh phải, chữ số đều cột, dấu chấm phân cách nghìn</li>
      <li>Nhãn nằm trên ô nhập; ô bắt buộc có dấu *</li>
    </ul>
  </div>
  <div class="uic"><h4>Biểu tượng</h4>
    <div class="icons">
      <span><svg class="ic"><use href="#i-search"/></svg>Tìm</span>
      <span><svg class="ic"><use href="#i-plus"/></svg>Thêm</span>
      <span><svg class="ic"><use href="#i-file"/></svg>Chứng từ</span>
      <span><svg class="ic"><use href="#i-sliders"/></svg>Cấu hình</span>
      <span><svg class="ic"><use href="#i-wallet"/></svg>Lương</span>
      <span><svg class="ic"><use href="#i-percent"/></svg>Thuế</span>
    </div>
    <ul><li>Nét mảnh 1,5px, cỡ 16px, một màu theo chữ</li><li>Luôn đi kèm chữ ở menu và nút; không dùng biểu tượng đứng một mình cho thao tác quan trọng</li><li>Không emoji; ổ khóa, dấu sao trong bản chạy thử sẽ thay bằng biểu tượng nét</li></ul>
  </div>
  <div class="uic"><h4>Bố cục cố định</h4>
    <ul>
      <li>Thanh trên: tên app, ô tìm nhanh Ctrl K, chọn công ty, tài khoản</li>
      <li>Menu trái: các phân hệ, chữ kèm biểu tượng</li>
      <li>Đầu màn hình: đường dẫn, tiêu đề, nút thao tác bên phải</li>
      <li>Chân màn hình cố định: Hủy, Lưu, Cất và Đóng như MISA</li>
      <li>Phím tắt như MISA: Ctrl S cất, F9 thêm dòng</li>
    </ul>
  </div>
</div>
</section>

<section id="man-mau">
<h2><span class="no">04</span>Màn hình mẫu · mục Cấu hình</h2>
<p class="intro">Bấm các mục ở cột “Cấu hình” để xem 7 màn hình mẫu. Số liệu pháp lý lấy theo tra cứu 2026; tài khoản kế toán trong màn định khoản là ví dụ, cần đối chiếu hệ thống tài khoản Thông tư 99.</p>
<div class="mockwrap">{MOCK}</div>
</section>

{RESEARCH}

<footer>Bổ sung cho “Danh mục nghiệp vụ ERP LiFeOOD”, “Bản thiết kế ERP LiFeOOD” và “Phương án công nghệ ERP LiFeOOD”.</footer>
</main></div>
<script>
(function(){{
  const q=document.getElementById('q'), shown=document.getElementById('shown'); let k='';
  function apply(){{
    const s=q.value.trim().toLowerCase(); let t=0;
    document.querySelectorAll('[data-sec]').forEach(sec=>{{ let c=0;
      sec.querySelectorAll('tbody tr').forEach(tr=>{{ const ok=(!k||tr.dataset.k===k)&&(!s||tr.dataset.q.includes(s)); tr.hidden=!ok; if(ok)c++; }});
      sec.querySelector('[data-cnt]').textContent=c; sec.hidden=c===0; t+=c; }});
    shown.textContent=t+' mục';
  }}
  q.addEventListener('input',apply);
  document.querySelectorAll('.seg [data-k]').forEach(b=>b.addEventListener('click',()=>{{k=b.dataset.k;document.querySelectorAll('.seg [data-k]').forEach(x=>x.classList.toggle('on',x===b));apply();}}));
  document.querySelectorAll('.m-cfgnav [data-p]').forEach(b=>b.addEventListener('click',()=>{{
    document.querySelectorAll('.m-cfgnav [data-p]').forEach(x=>x.classList.toggle('on',x===b));
    document.querySelectorAll('.m-panel').forEach(p=>p.hidden=p.dataset.panel!==b.dataset.p);
  }}));
  window.addEventListener('beforeprint',()=>{{q.value='';k='';apply();}});
}})();
</script>'''

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write(PAGE)
print(OUT, 'N', N, C)
