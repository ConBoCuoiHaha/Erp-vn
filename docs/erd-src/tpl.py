HEAD = r"""<title>Bản thiết kế ERP LiFeOOD</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{
  --ground:#F4F7F5; --surface:#FFFFFF; --sunk:#EAF0EC;
  --ink:#14201A; --muted:#58665F; --rule:#D5DFD9;
  --green:#0F7A4A; --green-soft:#DCEFE4;
  --blue:#2C5E8F; --blue-soft:#DDE8F3;
  --amber:#9A5B00; --amber-soft:#FBEBD0;
  --sans:"Be Vietnam Pro","Segoe UI",system-ui,-apple-system,Arial,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Consolas,"Courier New",monospace;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#0E1411; --surface:#151D19; --sunk:#1B2520;
    --ink:#E2EBE6; --muted:#97A69E; --rule:#2A3831;
    --green:#4CC48A; --green-soft:#183526;
    --blue:#86B1DD; --blue-soft:#1A2A3B;
    --amber:#F0B45B; --amber-soft:#3A2B12;
  }
}
:root[data-theme="dark"]{
  --ground:#0E1411; --surface:#151D19; --sunk:#1B2520;
  --ink:#E2EBE6; --muted:#97A69E; --rule:#2A3831;
  --green:#4CC48A; --green-soft:#183526;
  --blue:#86B1DD; --blue-soft:#1A2A3B;
  --amber:#F0B45B; --amber-soft:#3A2B12;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion: reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--ground);color:var(--ink);font:15px/1.65 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--blue)}
a:focus-visible,summary:focus-visible{outline:2px solid var(--green);outline-offset:2px;border-radius:3px}
code{font-family:var(--mono);font-size:.88em}
.page{max-width:1260px;margin:0 auto;padding:40px 24px 80px;display:grid;grid-template-columns:230px minmax(0,1fr);gap:48px}
.toc{position:sticky;top:24px;align-self:start;font-size:13px;max-height:calc(100vh - 48px);overflow:auto}
.toc b{display:block;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 10px}
.toc ol{list-style:none;margin:0;padding:0;display:grid;gap:1px}
.toc a{display:block;padding:4px 10px;border-radius:5px;color:var(--ink);text-decoration:none;border-left:2px solid transparent}
.toc a:hover{background:var(--sunk);border-left-color:var(--green)}
.toc .sub a{padding-left:22px;color:var(--muted);font-size:12.5px}
header.doc{border-bottom:1px solid var(--rule);padding-bottom:28px}
.eyebrow{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600}
h1{font-size:36px;line-height:1.15;margin:8px 0 14px;font-weight:700;letter-spacing:-.02em;text-wrap:balance}
.lede{max-width:68ch;color:var(--muted);font-size:16px;margin:0}
.facts{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}
.fact{background:var(--surface);border:1px solid var(--rule);border-radius:6px;padding:8px 14px;display:flex;align-items:baseline;gap:8px}
.fact strong{font-size:20px;font-variant-numeric:tabular-nums}
.fact span{color:var(--muted);font-size:13px}
section{padding-top:48px}
h2{font-size:24px;line-height:1.25;margin:0 0 6px;letter-spacing:-.01em;text-wrap:balance;display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
h2 .no{font-family:var(--mono);font-size:14px;color:var(--muted);font-weight:500}
h3{font-size:18px;margin:0 0 6px;text-wrap:balance;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
h3.grp{margin:40px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--rule)}
.intro{max-width:70ch;color:var(--muted);margin:0 0 18px}
.tag{font-size:11.5px;font-weight:600;padding:2px 9px;border-radius:20px;white-space:nowrap}
.tag.a{background:var(--green-soft);color:var(--green)}
.tag.b{background:var(--blue-soft);color:var(--blue)}
.tag.c{background:var(--sunk);color:var(--muted)}
.tag.star{background:var(--amber-soft);color:var(--amber)}
figure{margin:0}
.diagram{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:20px;overflow-x:auto}
.diagram pre.mermaid{margin:0;background:transparent;font-family:var(--sans);min-width:640px}
figcaption{font-size:13px;color:var(--muted);margin-top:10px;max-width:84ch}
.svgwrap{overflow-x:auto}
.svgwrap svg{width:100%;min-width:780px;height:auto;display:block}
.legend{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1px;background:var(--rule);border:1px solid var(--rule);border-radius:8px;overflow:hidden;margin-top:14px}
.legend div{background:var(--surface);padding:9px 14px;font-size:13px;display:flex;gap:12px;align-items:baseline}
.legend code{color:var(--ink);background:var(--sunk);padding:1px 6px;border-radius:4px;white-space:nowrap}
.scope{border:1px solid var(--rule);border-radius:8px;overflow-x:auto;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;padding:9px 14px;border-bottom:1px solid var(--rule);vertical-align:top}
tr:last-child td{border-bottom:0}
th{font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:600;background:var(--sunk);white-space:nowrap}
td.mn{font-weight:600;min-width:170px}
td.od{font-family:var(--mono);font-size:12px;color:var(--muted);min-width:160px}
td.ph{white-space:nowrap}
td.num{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.rules{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px;margin:18px 0}
.rule{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:16px 18px}
.rule h4{margin:0 0 6px;font-size:15px}
.rule p{margin:0;font-size:13.5px;color:var(--muted)}
.rule .formula{font-family:var(--mono);font-size:12.5px;background:var(--sunk);border-radius:5px;padding:7px 10px;margin:8px 0 0;color:var(--ink);overflow-x:auto;white-space:nowrap}
.stack{display:grid;gap:30px;margin-top:22px}
.stack .why{color:var(--muted);margin:0 0 12px;max-width:72ch;font-size:14px}
.stepno{font-family:var(--mono);font-size:13px;color:var(--muted);font-weight:500}
.mod{margin-top:34px}
.mod > .why{color:var(--muted);margin:0 0 12px;max-width:80ch;font-size:14px}
.dictmod{margin-top:26px}
.dictmod h3{margin-bottom:10px}
.dict{display:grid;gap:8px}
details.ent{background:var(--surface);border:1px solid var(--rule);border-radius:8px}
details.ent summary{cursor:pointer;list-style:none;padding:10px 16px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 14px;align-items:center}
details.ent summary::-webkit-details-marker{display:none}
details.ent summary::before{content:"+";grid-row:1;position:absolute;opacity:0}
details.ent .nm{font-family:var(--mono);font-weight:500;font-size:13.5px}
details.ent .vn{font-weight:600}
details.ent .ds{grid-column:1 / -1;color:var(--muted);font-size:13px}
details.ent .od{font-family:var(--mono);font-size:11.5px;color:var(--muted);white-space:nowrap}
details.ent[open] summary{border-bottom:1px solid var(--rule)}
.tw{overflow-x:auto}
td.f{font-family:var(--mono);font-size:12.5px;white-space:nowrap}
td.t{font-family:var(--mono);font-size:12px;color:var(--muted);white-space:nowrap}
td.k{white-space:nowrap}
.key{font-family:var(--mono);font-size:11px;font-weight:500;padding:1px 6px;border-radius:4px;border:1px solid var(--rule);color:var(--muted)}
.key.pk{border-color:var(--green);color:var(--green)}
.key.fk{border-color:var(--blue);color:var(--blue)}
.gaps{display:grid;gap:10px;margin:0;padding:0;list-style:none}
.gaps li{background:var(--surface);border:1px solid var(--rule);border-left:3px solid var(--amber);border-radius:6px;padding:12px 16px}
.gaps b{display:block;margin-bottom:2px}
.gaps span{color:var(--muted);font-size:14px}
footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--rule);font-size:13px;color:var(--muted)}
@media (max-width:980px){
  .page{grid-template-columns:minmax(0,1fr);gap:0;padding-top:28px}
  .toc{position:static;max-height:none;margin-bottom:12px;background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:14px}
  .toc ol{grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}
  .toc .sub{display:none}
  h1{font-size:28px}
}
@media print{
  :root{--ground:#fff;--surface:#fff}
  .toc{display:none}
  .page{display:block;max-width:none;padding:0}
  section{padding-top:24px}
  figure,.rule,details.ent{break-inside:avoid}
  .diagram{overflow:visible}
}
</style>
"""

MECH_SVG = r"""
<figure class="diagram">
<div class="svgwrap">
<svg viewBox="0 0 960 330" role="img" aria-label="Chứng từ MDV00433 có 3 phiên bản. Chỉ phiên bản 1, số gốc lúc mua vào, sinh bút toán và được báo cáo đọc. Phiên bản 2 và 3 ghi vào nhật ký và bảng so sánh. Đường nét đứt là tùy chọn đưa sửa đổi vào báo cáo bằng bút toán điều chỉnh khi kế toán trưởng duyệt.">
  <defs>
    <marker id="ah2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="currentColor"/></marker>
  </defs>
  <text x="40" y="36" font-size="12" font-weight="700" letter-spacing=".06em" style="fill:var(--muted)">CHỨNG TỪ MUA DỊCH VỤ MDV00433 · CÁC PHIÊN BẢN</text>

  <rect x="40" y="56" width="240" height="100" rx="8" style="fill:var(--green-soft);stroke:var(--green)" stroke-width="1.6"/>
  <text x="58" y="82" font-size="13" font-weight="700" style="fill:var(--ink)">Phiên bản 1 · gốc lúc mua vào</text>
  <text x="58" y="104" font-size="12.5" style="fill:var(--muted)">Tổng tiền dịch vụ</text>
  <text x="262" y="104" text-anchor="end" font-size="13" style="fill:var(--ink);font-family:var(--mono)">97.505.000</text>
  <rect x="58" y="120" width="128" height="22" rx="11" style="fill:var(--green)"/>
  <text x="122" y="135" text-anchor="middle" font-size="11.5" font-weight="600" style="fill:var(--surface)">phiên bản báo cáo</text>

  <rect x="360" y="56" width="240" height="100" rx="8" style="fill:var(--surface);stroke:var(--rule)" stroke-width="1.4"/>
  <text x="378" y="82" font-size="13" font-weight="700" style="fill:var(--ink)">Phiên bản 2 · sửa đổi</text>
  <text x="378" y="104" font-size="12.5" style="fill:var(--muted)">Tổng tiền dịch vụ</text>
  <text x="582" y="104" text-anchor="end" font-size="13" style="fill:var(--ink);font-family:var(--mono)">100.000.000</text>
  <text x="378" y="136" font-size="12" style="fill:var(--muted)">lý do, người sửa, thời điểm</text>

  <rect x="680" y="56" width="240" height="100" rx="8" style="fill:var(--surface);stroke:var(--blue)" stroke-width="1.6"/>
  <text x="698" y="82" font-size="13" font-weight="700" style="fill:var(--ink)">Phiên bản 3 · sửa đổi</text>
  <text x="698" y="104" font-size="12.5" style="fill:var(--muted)">Tổng tiền dịch vụ</text>
  <text x="902" y="104" text-anchor="end" font-size="13" style="fill:var(--ink);font-family:var(--mono)">120.000.000</text>
  <rect x="698" y="120" width="112" height="22" rx="11" style="fill:var(--blue)"/>
  <text x="754" y="135" text-anchor="middle" font-size="11.5" font-weight="600" style="fill:var(--surface)">đang hiện hành</text>

  <g stroke="currentColor" style="color:var(--muted)" stroke-width="1.4" fill="none">
    <line x1="280" y1="106" x2="356" y2="106" marker-end="url(#ah2)"/>
    <line x1="600" y1="106" x2="676" y2="106" marker-end="url(#ah2)"/>
    <line x1="160" y1="156" x2="160" y2="224" marker-end="url(#ah2)"/>
    <line x1="280" y1="248" x2="356" y2="248" marker-end="url(#ah2)"/>
    <line x1="800" y1="156" x2="800" y2="224" marker-end="url(#ah2)"/>
    <path d="M480 156V190H740V224" marker-end="url(#ah2)"/>
  </g>
  <text x="318" y="98" text-anchor="middle" font-size="11.5" style="fill:var(--muted)">Sửa</text>
  <text x="638" y="98" text-anchor="middle" font-size="11.5" style="fill:var(--muted)">Sửa</text>
  <text x="170" y="196" font-size="11.5" style="fill:var(--muted)">ghi sổ khi Cất</text>
  <text x="318" y="240" text-anchor="middle" font-size="11.5" style="fill:var(--muted)">đọc</text>
  <text x="810" y="196" font-size="11.5" style="fill:var(--muted)">ghi chênh lệch</text>

  <rect x="40" y="226" width="240" height="44" rx="6" style="fill:var(--sunk);stroke:var(--rule)"/>
  <text x="160" y="253" text-anchor="middle" font-size="12.5" style="fill:var(--ink)">Bút toán Nợ 6277, 1331 / Có 3311</text>
  <rect x="360" y="226" width="240" height="44" rx="6" style="fill:var(--sunk);stroke:var(--green)" stroke-width="1.4"/>
  <text x="480" y="253" text-anchor="middle" font-size="12.5" font-weight="600" style="fill:var(--ink)">Báo cáo · không đổi</text>
  <rect x="680" y="226" width="240" height="44" rx="6" style="fill:var(--sunk);stroke:var(--rule)"/>
  <text x="800" y="253" text-anchor="middle" font-size="12.5" style="fill:var(--ink)">Nhật ký và bảng so sánh</text>

  <line x1="680" y1="262" x2="604" y2="262" style="stroke:var(--amber)" stroke-width="1.6" stroke-dasharray="5 4" marker-end="url(#ah2)" color="var(--amber)"/>
  <text x="640" y="300" text-anchor="middle" font-size="11.5" font-weight="600" style="fill:var(--amber)">tùy chọn · bút toán điều chỉnh khi KTT duyệt</text>
</svg>
</div>
<figcaption>Sửa không ghi đè: mỗi lần lưu thêm một phiên bản. Chỉ phiên bản báo cáo sinh bút toán, nên báo cáo giữ nguyên dù chứng từ đã sửa nhiều lần. Số của phiên bản 2 và 3 là ví dụ minh họa.</figcaption>
</figure>
"""

RULES = """
<div class="rules">
  <div class="rule"><h4>Cất lần đầu</h4><p>Số liệu lúc mua vào được lưu thành Phiên bản 1 và khóa. Bút toán sinh từ phiên bản này; phiên bản báo cáo = phiên bản hiện hành = 1.</p></div>
  <div class="rule"><h4>Bấm Sửa</h4><p>Tạo phiên bản mới sao chép từ phiên bản hiện hành. Mỗi dòng trỏ về dòng gốc, màn hình hiện cột <b>Gốc lúc mua vào</b> ngay cạnh để so. Kỳ đã khóa vẫn sửa được vì không đụng sổ cái.</p></div>
  <div class="rule"><h4>Tự động tính lại</h4><p>Sửa Tổng thì chia lại các dòng theo tỷ trọng; sửa SL hoặc Đơn giá thì ra Thành tiền; sửa Thành tiền thì ra Đơn giá; thuế và tổng theo cây cụ – ông – cha – con cập nhật ngay. Dòng khóa giữ nguyên.</p>
    <div class="formula">phần_i = sàn(Tổng × tỷ_trọng_i) + phần dư theo số lẻ lớn nhất</div></div>
  <div class="rule"><h4>Lưu sửa đổi</h4><p>Bắt buộc nhập lý do. Phiên bản mới thành hiện hành; ghi chênh lệch từng trường, phân biệt ô người sửa và ô hệ thống tự tính. Không phiên bản nào bị xóa.</p></div>
  <div class="rule"><h4>Báo cáo không đổi</h4><p>Báo cáo tổng hợp từ bút toán, bút toán chỉ sinh từ phiên bản báo cáo. Người xem có thể bật cột tham khảo theo phiên bản hiện hành, nhưng cột này không ghi vào báo cáo.</p></div>
  <div class="rule"><h4>Quyền</h4><p>Quyền <code>sua_sau_khi_cat</code> cấp theo nhóm. Đưa sửa đổi vào báo cáo (K6) là quyền riêng, cần Kế toán trưởng duyệt và chỉ ghi vào kỳ đang mở.</p></div>
</div>
"""

FLOWCHART = """
flowchart LR
  NEN["Nền tảng, phân quyền, luồng duyệt"]
  BH["Bán hàng, CRM, TMĐT"]
  KHO["Kho, lô, mã vạch"]
  MH["Mua hàng"]
  CT["★ Chứng từ mua dịch vụ có phiên bản"]
  RD["R&D tách riêng"]
  CL["Chất lượng HACCP"]
  TS["Tài sản, bảo trì, đội xe"]
  HR["Nhân sự, lương"]
  NS["Khoản mục CP, ngân sách"]
  KT["Kế toán, báo cáo đã chốt"]
  BH -->|xuất giao| KHO
  MH -->|nhập mua| KHO
  CL -.->|kiểm tra nhập xuất| KHO
  MH -->|dịch vụ| CT
  RD -.->|không kết nối kế toán| NEN
  CT -->|ghi tăng| TS
  CT -->|gắn khoản mục| NS
  HR -->|lương theo khoản mục| NS
  NS -->|kế hoạch và thực tế| KT
  CT -->|bút toán từ phiên bản báo cáo| KT
  TS -->|khấu hao| KT
  BH -->|hóa đơn, thu tiền| KT
  MH -->|hóa đơn NCC| KT
  KHO -->|giá trị tồn| KT
  HR -->|bút toán lương| KT
  NEN -.->|quyền, duyệt, nhật ký| KT
"""

GAPS = """
<ul class="gaps">
  <li><b>“Không thay đổi báo cáo” nghĩa là sổ sách giữ số gốc</b><span>Nếu hóa đơn gốc sai thật, sổ cái và báo cáo thuế vẫn mang số sai cho tới khi dùng K6. Cần quyết định: sửa đổi chỉ để quản trị nội bộ, hay có lúc phải đưa vào sổ.</span></li>
  <li><b>Ai được Sửa chứng từ đã cất, sửa trong bao lâu</b><span>Ví dụ: chỉ Kế toán tổng hợp trở lên, trong vòng 90 ngày, tối đa bao nhiêu lần.</span></li>
  <li><b>Sửa bắt đầu từ đâu</b><span>Thiết kế đang lấy phiên bản hiện hành và luôn hiện cột gốc lúc mua vào, có nút Khôi phục gốc. Nếu muốn lần nào cũng bắt đầu lại từ gốc thì đổi một quy tắc.</span></li>
  <li><b>Tự viết hay tùy biến trên Odoo</b><span>Các phân hệ đánh dấu tham chiếu Odoo đều có sẵn trong Odoo Enterprise; phần ★ phiên bản chứng từ và phân bổ cây khoản mục là phần phải viết thêm dù chọn cách nào. Quyết định này ảnh hưởng lớn tới thời gian và chi phí.</span></li>
  <li><b>Đối tác tích hợp</b><span>Nhà cung cấp hóa đơn điện tử, ngân hàng đồng bộ sao kê, sàn TMĐT nào kết nối trước.</span></li>
  <li><b>Hai điểm nghiệp vụ còn treo từ bản 4 sheet</b><span>Chiều hạch toán khấu hao (thông thường Nợ 627 / Có 214) và thuế GTGT mặc định trên chứng từ khấu hao.</span></li>
</ul>
"""
