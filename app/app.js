/* =====================================================================
   ERP LiFeOOD — Tài sản cố định & Khấu hao
   4 sheet nhập liệu (theo file "Thử AI.xlsx")  ->  Lưu  ->  Chứng từ kết quả
     1. Mua hàng (ghi tăng)   2. Tính khấu hao
     3. Danh sách mua hàng    4. Khấu hao
   Dữ liệu lưu trong localStorage (key: lfood_tscd_v2)
   ===================================================================== */
'use strict';

const LS_KEY = 'lfood_tscd_v2';

/* ---------------------------------------------------------------- tiện ích */
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const nf0 = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 0 });
const nf2 = new Intl.NumberFormat('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nf5 = new Intl.NumberFormat('vi-VN', { minimumFractionDigits: 5, maximumFractionDigits: 5 });
const nfq = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 5 });

const money = n => nf0.format(Math.round(n || 0));
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const uid = () => Math.random().toString(36).slice(2, 10);
const pad = (n, w = 5) => String(n).padStart(w, '0');
const today = () => { const d = new Date(); return d.getFullYear() + '-' + pad(d.getMonth() + 1, 2) + '-' + pad(d.getDate(), 2); };
const vnDate = iso => (iso ? iso.split('-').reverse().join('/') : '');
const monthLabel = p => (p ? 'Tháng ' + Number(p.slice(5, 7)) + '/' + p.slice(0, 4) : '');

/** "1.234.567,5" -> 1234567.5 */
function num(s) {
  if (typeof s === 'number') return s;
  s = String(s ?? '').trim().replace(/\./g, '').replace(/,/g, '.').replace(/[^\d.\-]/g, '');
  const v = parseFloat(s);
  return isNaN(v) ? 0 : v;
}
/** chênh lệch số tháng giữa 2 kỳ "YYYY-MM" */
function monthDiff(a, b) {
  if (!a || !b) return 0;
  return (+b.slice(0, 4) - +a.slice(0, 4)) * 12 + (+b.slice(5, 7) - +a.slice(5, 7));
}

/** chia `total` theo tỷ trọng, tổng các phần luôn khớp tuyệt đối (phương pháp số dư lớn nhất) */
function allocate(total, weights) {
  const n = weights.length;
  if (!n) return [];
  total = Math.round(total);
  let w = weights.map(x => Math.max(0, +x || 0));
  let sum = w.reduce((a, b) => a + b, 0);
  if (sum <= 0) { w = w.map(() => 1); sum = n; }
  const raw = w.map(x => total * x / sum);
  const out = raw.map(Math.floor);
  let rem = total - out.reduce((a, b) => a + b, 0);
  const ord = raw.map((x, i) => ({ i, f: x - Math.floor(x) })).sort((a, b) => b.f - a.f || a.i - b.i);
  for (let k = 0; rem > 0; k++, rem--) out[ord[k % n].i]++;
  return out;
}

/* ---------------------------------------------------------------- danh mục */
const TYPES = ['Máy móc', 'Xe'];
const WAREHOUSES = ['Kho 1', 'Kho 2', 'Kho 3'];
const ROLES = { kho: 'Nhân viên kho', ktt: 'Kế toán trưởng', ktv: 'Kế toán viên' };
const CAN_PURCHASE = ['kho', 'ktt'];                     // sheet 1: chỉ thủ kho + kế toán trưởng
const COST_ITEMS = { 1: 'Chi phí', 2: 'Khấu hao' };      // sheet 4: 1 = chi phí, 2 = khấu hao
const VAT_RATES = [0, 5, 8, 10];

/* ---------------------------------------------------------------- dữ liệu */
let DB;

function blankLine() {
  return {
    id: uid(), code: '', name: '', type: 'Máy móc', wh: 'Kho 1', qty: 1, price: 0,
    unit: '', noDep: false, life: 0, lifeUnit: 'thang',
    accDebt: '627', accStock: '214', cost: 2,
  };
}
function blankDraft() {
  const d = today();
  return { gtDate: d, period: d.slice(0, 7), lines: [blankLine()], sel: 0 };
}
function demoDraft() {
  const d = blankDraft();
  Object.assign(d.lines[0], {
    code: '11222', name: 'ABC', type: 'Máy móc', wh: 'Kho 1', qty: 1, price: 1000000000,
    unit: 'Phân xưởng sản xuất', life: 5, lifeUnit: 'nam',
  });
  return d;
}
function seed() {
  return { seq: { gt: 0, ds: 0, kh: 0 }, role: 'ktt', showAcc: true, draft: demoDraft(), vouchers: [] };
}
function save() { try { localStorage.setItem(LS_KEY, JSON.stringify(DB)); } catch (e) { toast('Không lưu được vào trình duyệt: ' + e.message, true); } }
function load() {
  try { const raw = localStorage.getItem(LS_KEY); if (raw) { DB = JSON.parse(raw); return; } } catch (e) { /* hỏng -> nạp mới */ }
  DB = seed(); save();
}
const nextNo = (prefix, key) => prefix + pad((DB.seq[key] || 0) + 1);

/* ---------------------------------------------------------------- tính toán */
const amountOf = l => Math.round((+l.qty || 0) * (+l.price || 0));          // Thành tiền = SL × Đơn giá
const lifeMonths = l => (l.lifeUnit === 'nam' ? (+l.life || 0) * 12 : (+l.life || 0));

/** Giá trị khấu hao tháng / năm — đúng công thức sheet "Tính khấu hao" */
function depMonthly(l) {
  if (l.noDep || !(+l.life > 0)) return 0;
  const ng = amountOf(l);
  return l.lifeUnit === 'thang' ? Math.round(ng / l.life) : Math.round(ng / l.life / 12);
}
function depYearly(l) {
  if (l.noDep || !(+l.life > 0)) return 0;
  const ng = amountOf(l);
  return l.lifeUnit === 'nam' ? Math.round(ng / l.life) : Math.round(ng / l.life * 12);
}
/** lịch khấu hao từng tháng — tháng cuối nhận phần làm tròn để tổng = nguyên giá */
function schedule(l) {
  const n = lifeMonths(l);
  if (l.noDep || n <= 0) return [];
  const ng = amountOf(l), m = depMonthly(l), out = [];
  let acc = 0;
  for (let i = 0; i < n; i++) {
    const v = i === n - 1 ? ng - acc : Math.min(m, ng - acc);
    acc += v; out.push(v);
  }
  return out;
}
/** Hao mòn lũy kế tại kỳ: tháng đầu = N1, tháng sau = N1 + khấu hao tháng tiếp theo ... */
function accumulated(l, startMonth, period) {
  const s = schedule(l), k = Math.min(s.length, monthDiff(startMonth, period) + 1);
  let t = 0; for (let i = 0; i < k; i++) t += s[i];
  return Math.max(0, t);
}
function depInPeriod(l, startMonth, period) {
  const s = schedule(l), i = monthDiff(startMonth, period);
  return i >= 0 && i < s.length ? s[i] : 0;
}
const draftStart = d => (d.gtDate || '').slice(0, 7);
const sumQty = lines => lines.reduce((a, l) => a + (+l.qty || 0), 0);
const sumAmount = lines => lines.reduce((a, l) => a + amountOf(l), 0);

/** Sheet 3: 1 dòng tổng, có mã riêng cho dòng tổng */
function purchaseSummary(d) {
  const valid = d.lines.filter(l => l.code || l.name);
  const q = sumQty(d.lines), t = sumAmount(d.lines);
  const names = valid.map(l => l.name || l.code);
  return {
    code: nextNo('DSMH', 'ds'),
    name: names.length <= 1 ? (names[0] || '') : 'Tổng hợp ' + names.length + ' tài sản: ' + names.join(', '),
    qty: q, price: q ? t / q : 0, amount: t, count: valid.length,
  };
}

/* ---------------------------------------------------------------- trạng thái giao diện */
const ROUTES = {
  s1: { n: 1, title: 'Mua hàng (ghi tăng)' },
  s2: { n: 2, title: 'Tính khấu hao' },
  s3: { n: 3, title: 'Danh sách mua hàng' },
  s4: { n: 4, title: 'Khấu hao' },
};
const ST = { route: 's1', vid: null, v: null, dirty: false, tab: 'hach', act: -1, menu: false };

/* =====================================================================
   RENDER
   ===================================================================== */
function render() {
  renderSide();
  const r = ST.route;
  if (ROUTES[r]) renderSheet(r);
  else if (r === 'result') renderResult();
  else renderList();
  $('#role').innerHTML = Object.entries(ROLES).map(([k, v]) => `<option value="${k}" ${DB.role === k ? 'selected' : ''}>${v}</option>`).join('');
}

function renderSide() {
  const item = (r, label, n) => `<a class="${ST.route === r ? 'on' : ''}" data-go="${r}"><span class="n">${n}</span><span>${label}</span></a>`;
  $('#side').innerHTML = `
    <div class="grp">Tài sản cố định</div>
    ${Object.entries(ROUTES).map(([k, v]) => item(k, v.title, v.n)).join('')}
    <div class="grp">Kết quả</div>
    <a class="${ST.route === 'list' || ST.route === 'result' ? 'on' : ''}" data-go="list">
      <span class="n">≡</span><span>Chứng từ khấu hao</span><span class="cnt">${DB.vouchers.length}</span>
    </a>`;
}

/* ------------------------------------------------------------ 4 SHEET */
function renderSheet(r) {
  const d = DB.draft, R = ROUTES[r];
  $('#ph').innerHTML = `
    <h1>${R.n}. ${R.title}</h1>
    <span class="sub">Số CT ghi tăng dự kiến: <b>${nextNo('GT', 'gt')}</b></span>
    <div class="r"><button class="btn sm" data-act="demo" title="Điền lại dữ liệu mẫu từ file Excel">Dữ liệu mẫu</button></div>`;

  $('#pb').innerHTML = r === 's1' ? sheet1(d) : r === 's2' ? sheet2(d) : r === 's3' ? sheet3(d) : sheet4(d);

  const keys = Object.keys(ROUTES), i = keys.indexOf(r);
  $('#pf').innerHTML = `
    <div class="fbar">
      <div class="steps">
        <button class="btn sm" data-go="${keys[i - 1] || ''}" ${i === 0 ? 'disabled' : ''}>‹ Trước</button>
        <span>Sheet <b>${i + 1}</b>/4</span>
        <button class="btn sm" data-go="${keys[i + 1] || ''}" ${i === keys.length - 1 ? 'disabled' : ''}>Tiếp ›</button>
      </div>
      <div class="r">
        <button class="btn" data-act="reset">Hủy</button>
        <button class="btn p" data-act="saveDraft">Lưu</button>
      </div>
    </div>`;
}

/* Sheet 1 — Mua hàng (ghi tăng) */
function sheet1(d) {
  const can = CAN_PURCHASE.includes(DB.role), dis = can ? '' : 'disabled';
  const opt = (arr, v) => arr.map(x => `<option ${x === v ? 'selected' : ''}>${x}</option>`).join('');
  const rows = d.lines.map((l, i) => `
    <tr data-i="${i}">
      <td class="ix">${i + 1}</td>
      <td class="cellin"><input class="ci" data-k="code" value="${esc(l.code)}" ${dis} style="min-width:110px"></td>
      <td class="cellin"><input class="ci" data-k="name" value="${esc(l.name)}" ${dis} style="min-width:220px"></td>
      <td class="cellin"><select class="ci" data-k="type" ${dis} style="min-width:120px">${opt(TYPES, l.type)}</select></td>
      <td class="cellin"><select class="ci" data-k="wh" ${dis} style="min-width:100px">${opt(WAREHOUSES, l.wh)}</select></td>
      <td class="cellin"><input class="ci num" data-k="qty" data-n="1" value="${nfq.format(l.qty || 0)}" ${dis} style="min-width:90px"></td>
      <td class="cellin"><input class="ci num" data-k="price" data-n="1" value="${money(l.price)}" ${dis} style="min-width:140px"></td>
      <td class="num" data-calc="amt${i}">${money(amountOf(l))}</td>
      <td class="cellin">${can && d.lines.length > 1 ? `<button class="del" data-act="rmLine" data-i="${i}" title="Xóa dòng">${trash()}</button>` : ''}</td>
    </tr>`).join('');

  return `
    ${can ? '' : `<div class="banner warn">🔒 Vai trò <b>${ROLES[DB.role]}</b> chỉ được xem. Sheet này chỉ <b>Nhân viên kho</b> và <b>Kế toán trưởng</b> được nhập — đổi vai trò ở góc trên bên phải.</div>`}
    <div class="card">
      <div class="tw">
        <table class="g">
          <thead><tr>
            <th class="ix">#</th><th>Mã hàng <span style="color:var(--red)">*</span></th><th>Tên tài sản <span style="color:var(--red)">*</span></th>
            <th>Loại tài sản</th><th>Kho</th><th class="num">Số lượng</th><th class="num">Đơn giá</th><th class="num">Thành tiền</th><th style="width:44px"></th>
          </tr></thead>
          <tbody>${rows}</tbody>
          <tfoot><tr>
            <td></td><td colspan="4" style="text-align:right">Tổng :</td>
            <td class="num" data-calc="sq">${nfq.format(sumQty(d.lines))}</td><td></td>
            <td class="num" data-calc="sa">${money(sumAmount(d.lines))}</td><td></td>
          </tr></tfoot>
        </table>
      </div>
      <div class="card-b tools">
        <button class="btn" data-act="addLine" ${dis}>＋ Thêm dòng</button>
        <span class="muted" style="align-self:center">Thành tiền = Số lượng × Đơn giá (tự tính)</span>
      </div>
    </div>`;
}

/* Sheet 2 — Tính khấu hao (theo từng tài sản) */
function sheet2(d) {
  const sel = Math.min(d.sel || 0, d.lines.length - 1);
  const l = d.lines[sel], start = draftStart(d);
  const ng = amountOf(l), acc = accumulated(l, start, d.period);
  const sch = schedule(l);

  const picker = d.lines.length > 1 ? `
    <div class="card" style="margin-bottom:12px"><div class="card-b" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
      <span class="muted">Tài sản:</span>
      ${d.lines.map((x, i) => `<button class="btn sm ${i === sel ? 'p' : ''}" data-act="pick" data-i="${i}">${esc(x.code || '(chưa mã)')} – ${esc(x.name || '')}</button>`).join('')}
    </div></div>` : '';

  const schRows = sch.map((v, i) => {
    const p = addMonths(start, i), cum = sch.slice(0, i + 1).reduce((a, b) => a + b, 0);
    return `<tr class="${p === d.period ? 'act' : ''}"><td class="ix">${i + 1}</td><td>${monthLabel(p)}</td>
      <td class="num">${money(v)}</td><td class="num">${money(cum)}</td><td class="num">${money(ng - cum)}</td></tr>`;
  }).join('');

  return `${picker}
  <div class="card" data-i="${sel}"><div class="card-b">
    <div class="sec">Thông tin chung</div>
    <div class="grid c4">
      <div class="fld"><label>Số CT ghi tăng</label><div class="ro">${nextNo('GT', 'gt')}</div></div>
      <div class="fld"><label>Ngày ghi tăng</label><input class="inp" type="date" data-d="gtDate" value="${d.gtDate}"></div>
      <div class="fld"><label>Loại tài sản</label><div class="ro">${esc(l.type)}</div></div>
      <div class="fld"><label>Đơn vị sử dụng</label><input class="inp" data-k="unit" value="${esc(l.unit)}" placeholder="Tự nhập"></div>
      <div class="fld"><label>Mã tài sản</label><div class="ro">${esc(l.code) || '<span class="muted">— lấy từ sheet 1 —</span>'}</div></div>
      <div class="fld span2"><label>Tên tài sản</label><div class="ro">${esc(l.name) || '<span class="muted">— lấy từ sheet 1 —</span>'}</div></div>
      <div class="fld"><label>&nbsp;</label><label class="chk" style="height:32px"><input type="checkbox" data-k="noDep" ${l.noDep ? 'checked' : ''}> Không tính khấu hao</label></div>
    </div>
  </div></div>

  <div class="card" data-i="${sel}"><div class="card-b">
    <div class="sec">Thông tin khấu hao</div>
    <div class="grid c4">
      <div class="fld"><label>TK nguyên giá</label><div class="ro">211</div></div>
      <div class="fld"><label>Giá trị nguyên giá</label><div class="ro num">${money(ng)}</div></div>
      <div class="fld"><label>TK khấu hao</label><div class="ro">214</div></div>
      <div class="fld"><label>Giá trị khấu hao</label><div class="ro num">${money(ng)}</div></div>

      <div class="fld"><label>Thời gian sử dụng <span class="req">*</span></label>
        <div class="inline">
          <input class="inp num" data-k="life" data-n="1" value="${l.life || ''}" ${l.noDep ? 'disabled' : ''} placeholder="Tự nhập">
          <select class="inp" data-k="lifeUnit" style="width:96px;flex:0 0 96px" ${l.noDep ? 'disabled' : ''}>
            <option value="thang" ${l.lifeUnit === 'thang' ? 'selected' : ''}>Tháng</option>
            <option value="nam" ${l.lifeUnit === 'nam' ? 'selected' : ''}>Năm</option>
          </select>
        </div></div>
      <div class="fld"><label>Giá trị khấu hao tháng</label><div class="ro num hl">${money(depMonthly(l))}</div></div>
      <div class="fld"><label>Giá trị khấu hao năm</label><div class="ro num hl">${money(depYearly(l))}</div></div>
      <div class="fld"><label>Ngày bắt đầu khấu hao</label><div class="ro">${vnDate(d.gtDate)}</div></div>

      <div class="fld"><label>Kỳ tính khấu hao</label><input class="inp" type="month" data-d="period" value="${d.period}"></div>
      <div class="fld"><label>Hao mòn lũy kế</label><div class="ro num">${money(acc)}</div></div>
      <div class="fld"><label>Giá trị còn lại</label><div class="ro num">${money(ng - acc)}</div></div>
      <div class="fld"><label>Tổng số kỳ</label><div class="ro num">${lifeMonths(l) || 0} tháng</div></div>
    </div>
  </div></div>

  <div class="card"><div class="card-b" style="padding-bottom:6px">
    <div class="sec">Bảng khấu hao theo tháng</div>
    <div class="muted" style="margin:-4px 0 10px">Tháng đầu = N1; mỗi tháng sau cộng dồn thêm khấu hao tháng. Dòng tô xanh là kỳ đang tính.</div>
  </div>
    ${sch.length ? `<div class="tw" style="max-height:320px"><table class="g">
      <thead><tr><th class="ix">#</th><th>Kỳ</th><th class="num">Khấu hao trong kỳ</th><th class="num">Hao mòn lũy kế</th><th class="num">Giá trị còn lại</th></tr></thead>
      <tbody>${schRows}</tbody></table></div>`
    : `<div class="card-b muted">${l.noDep ? 'Tài sản được đánh dấu không tính khấu hao.' : 'Nhập thời gian sử dụng để xem bảng khấu hao.'}</div>`}
  </div>`;
}
function addMonths(p, k) {
  let y = +p.slice(0, 4), m = +p.slice(5, 7) - 1 + k;
  y += Math.floor(m / 12); m = ((m % 12) + 12) % 12;
  return y + '-' + pad(m + 1, 2);
}

/* Sheet 3 — Danh sách mua hàng: 1 dòng tổng + mã */
function sheet3(d) {
  const s = purchaseSummary(d);
  return `
  <div class="banner info">Tự tổng hợp từ sheet <b>1. Mua hàng</b> thành <b>một dòng tổng</b> và cấp mã riêng cho dòng tổng. Không cần nhập tay.</div>
  <div class="card"><div class="tw"><table class="g">
    <thead><tr><th class="ix">#</th><th>Mã hàng</th><th>Tên tài sản</th><th class="num">Số lượng</th><th class="num">Đơn giá</th><th class="num">Thành tiền</th></tr></thead>
    <tbody><tr>
      <td class="ix">1</td>
      <td><b>${s.code}</b></td>
      <td style="white-space:normal;min-width:260px">${esc(s.name) || '<span class="muted">Chưa có dữ liệu</span>'}${s.count > 1 ? `<div class="muted" style="font-size:12px">Gồm ${s.count} tài sản</div>` : ''}</td>
      <td class="num">${nfq.format(s.qty)}</td>
      <td class="num">${money(s.price)}</td>
      <td class="num"><b>${money(s.amount)}</b></td>
    </tr></tbody>
  </table></div></div>`;
}

/* Sheet 4 — Khấu hao */
function sheet4(d) {
  const start = draftStart(d);
  const rows = d.lines.map((l, i) => `
    <tr data-i="${i}">
      <td class="ix">${i + 1}</td>
      <td>${esc(l.code)}</td>
      <td>${esc(l.name)}</td>
      <td>${esc(l.wh)}</td>
      <td class="cellin"><input class="ci" data-k="accDebt" value="${esc(l.accDebt)}" style="width:80px"></td>
      <td class="cellin"><input class="ci" data-k="accStock" value="${esc(l.accStock)}" style="width:80px"></td>
      <td class="num">${nfq.format(l.qty || 0)}</td>
      <td class="num">${money(l.price)}</td>
      <td class="num">${money(amountOf(l))}</td>
      <td class="num"><b>${money(depInPeriod(l, start, d.period))}</b></td>
      <td class="cellin"><select class="ci" data-k="cost" style="width:70px">
        ${Object.keys(COST_ITEMS).map(k => `<option value="${k}" ${+l.cost === +k ? 'selected' : ''}>${k}</option>`).join('')}
      </select></td>
      <td>${COST_ITEMS[l.cost] || ''}</td>
    </tr>`).join('');
  const totDep = d.lines.reduce((a, l) => a + depInPeriod(l, start, d.period), 0);
  return `
  <div class="banner info">Kỳ khấu hao: <b>${monthLabel(d.period)}</b> (đổi ở sheet 2). TK công nợ / TK kho tự điền <b>627 / 214</b>.
    Khoản mục chi phí: chọn <b>1</b> → <i>Chi phí</i>, chọn <b>2</b> → <i>Khấu hao</i>.</div>
  <div class="card"><div class="tw"><table class="g">
    <thead><tr><th class="ix">#</th><th>Mã hàng</th><th>Tên tài sản</th><th>Kho</th><th>TK công nợ</th><th>TK kho</th>
      <th class="num">Số lượng</th><th class="num">Đơn giá</th><th class="num">Thành tiền</th><th class="num">Số tiền khấu hao</th>
      <th>Khoản mục CP</th><th>Tên khoản mục CP</th></tr></thead>
    <tbody>${rows}</tbody>
    <tfoot><tr><td></td><td colspan="5" style="text-align:right">Tổng :</td>
      <td class="num">${nfq.format(sumQty(d.lines))}</td><td></td><td class="num">${money(sumAmount(d.lines))}</td>
      <td class="num">${money(totDep)}</td><td colspan="2"></td></tr></tfoot>
  </table></div></div>`;
}

/* ------------------------------------------------------------ MÀN KẾT QUẢ (giống MISA) */
const vSub = v => v.lines.reduce((a, l) => a + (l.amount || 0), 0);
const vVat = v => v.lines.reduce((a, l) => a + Math.round((l.amount || 0) * (+l.vat || 0) / 100), 0);
const vTotal = v => vSub(v) + vVat(v);

function renderResult() {
  const v = ST.v;
  $('#ph').innerHTML = `
    <h1>Chứng từ khấu hao TSCĐ ${esc(v.no)}</h1>
    ${v.status === 'hold' ? '<span class="pill hold">Hoãn</span>' : '<span class="pill ok">Đã cất</span>'}
    <div class="r">
      <button class="btn sm ghost hide-s" data-act="help">ⓘ Hướng dẫn sử dụng</button>
      <button class="icon-btn" data-act="close" title="Đóng">✕</button>
    </div>`;

  const acc = DB.showAcc;
  const L = v.lines;
  const qtySum = L.reduce((a, l) => a + (+l.qty || 0), 0);
  const depSum = L.reduce((a, l) => a + (l.dep || 0), 0);

  const cell = (i, k, val, cls = '', w = 110) => ST.act === i
    ? `<td class="cellin"><input class="ci ${cls}" data-k="${k}" value="${esc(val)}" style="min-width:${w}px"></td>`
    : `<td class="${cls}">${esc(val)}</td>`;

  const hach = L.map((l, i) => `
    <tr data-i="${i}" data-row="${i}" class="${ST.act === i ? 'act' : ''}">
      <td class="ix">${i + 1}</td>
      ${cell(i, 'svcCode', l.svcCode, '', 90)}
      ${cell(i, 'svcName', l.svcName, '', 240)}
      ${acc ? cell(i, 'accStock', l.accStock, '', 90) + cell(i, 'accDebt', l.accDebt, '', 90) : ''}
      ${cell(i, 'obj', l.obj, '', 100)}
      ${cell(i, 'objName', l.objName, '', 220)}
      ${cell(i, 'uom', l.uom, '', 60)}
      ${cell(i, 'qty', nf5.format(+l.qty || 0), 'num', 110)}
      ${cell(i, 'price', nf2.format(+l.price || 0), 'num', 120)}
      ${cell(i, 'amount', money(l.amount), 'num', 120)}
      ${cell(i, 'dep', money(l.dep), 'num', 120)}
      ${ST.act === i
        ? `<td class="cellin"><select class="ci" data-k="cost" style="min-width:120px">${Object.entries(COST_ITEMS).map(([k, t]) => `<option value="${k}" ${+l.cost === +k ? 'selected' : ''}>${k} - ${t}</option>`).join('')}</select></td>`
        : `<td>${l.cost ? l.cost + ' - ' + COST_ITEMS[l.cost] : ''}</td>`}
      <td class="cellin"><button class="del" data-act="rmVLine" data-i="${i}" title="Xóa dòng">${trash()}</button></td>
    </tr>`).join('');

  const thue = L.map((l, i) => `
    <tr data-i="${i}">
      <td class="ix">${i + 1}</td><td>${esc(l.svcCode)}</td><td>${esc(l.svcName)}</td>
      <td class="num">${money(l.amount)}</td>
      <td class="cellin"><select class="ci" data-k="vat" style="width:90px">${VAT_RATES.map(r => `<option value="${r}" ${+l.vat === r ? 'selected' : ''}>${r}%</option>`).join('')}</select></td>
      <td class="num">${money(Math.round((l.amount || 0) * (+l.vat || 0) / 100))}</td>
      <td>1331</td>
    </tr>`).join('');

  $('#pb').innerHTML = `
  <div class="card"><div class="card-b">
    <div class="optrow">
      <label class="chk"><input type="radio" name="paid" data-v="paid" value="0" ${!v.paid ? 'checked' : ''}> Chưa thanh toán</label>
      <label class="chk"><input type="radio" name="paid" data-v="paid" value="1" ${v.paid ? 'checked' : ''}> Thanh toán ngay</label>
      <select class="inp" data-v="payMethod">${['Tiền mặt', 'Chuyển khoản'].map(x => `<option ${v.payMethod === x ? 'selected' : ''}>${x}</option>`).join('')}</select>
      <select class="inp" data-v="invoice">${['Nhận kèm hóa đơn', 'Không kèm hóa đơn'].map(x => `<option ${v.invoice === x ? 'selected' : ''}>${x}</option>`).join('')}</select>
      <label class="chk"><input type="checkbox" data-v="isPurchase" ${v.isPurchase ? 'checked' : ''}> Là chi phí mua hàng</label>
    </div>
    <div class="vh">
      <div class="left grid c2">
        <div class="fld"><label>Đơn vị sử dụng</label><input class="inp" data-v="unit" value="${esc(v.unit)}"></div>
        <div class="fld"><label>Kho</label><input class="inp" data-v="wh" value="${esc(v.wh)}"></div>
        <div class="fld span2"><label>Diễn giải</label><input class="inp" data-v="memo" value="${esc(v.memo)}"></div>
        <div class="fld span2" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <span>Tham chiếu</span>
          <a class="link" data-act="goSheet" data-r="s2" title="Số CT ghi tăng">${esc(v.gtNo)}</a>
          <a class="link" data-act="goSheet" data-r="s3" title="Mã danh sách mua hàng (dòng tổng)">${esc(v.listCode)}</a>
          <span class="muted">· Kỳ khấu hao ${monthLabel(v.period)}</span>
        </div>
      </div>
      <div class="right">
        <div class="bigtotal"><div class="lb">Tổng tiền thanh toán</div><div class="v" data-calc="vt">${money(vTotal(v))}</div></div>
        <div class="grid" style="margin-top:12px">
          <div class="fld"><label>Ngày hạch toán</label><input class="inp" type="date" data-v="date" value="${v.date}"></div>
          <div class="fld"><label>Ngày chứng từ</label><input class="inp" type="date" data-v="docDate" value="${v.docDate}"></div>
          <div class="fld"><label>Số chứng từ</label><input class="inp" data-v="no" value="${esc(v.no)}"></div>
        </div>
      </div>
    </div>
  </div></div>

  <div class="card">
    <div class="tabs">
      <button class="t ${ST.tab === 'hach' ? 'on' : ''}" data-act="tab" data-t="hach">Hạch toán</button>
      <button class="t ${ST.tab === 'thue' ? 'on' : ''}" data-act="tab" data-t="thue">Thuế</button>
      <div class="r">
        <span class="ava hide-s"><span>✦ AVA Kế toán</span><i>⌄</i></span>
        <span class="hide-s">Chiết khấu</span>
        <select class="inp" data-v="discount" style="width:160px">${['Không chiết khấu', 'Theo % hóa đơn', 'Theo số tiền'].map(x => `<option ${v.discount === x ? 'selected' : ''}>${x}</option>`).join('')}</select>
      </div>
    </div>

    <div class="tw">
      ${ST.tab === 'hach' ? `
      <table class="g" id="hach">
        <thead><tr>
          <th class="ix">#</th><th>Mã dịch vụ</th><th>Tên dịch vụ</th>
          ${acc ? '<th>TK chi phí/TK kho</th><th>TK Công nợ</th>' : ''}
          <th>Đối tượng</th><th>Tên đối tượng</th><th>ĐVT</th>
          <th class="num">Số lượng</th><th class="num">Đơn giá</th><th class="num">Thành tiền</th>
          <th class="num">Số tiền khấu hao</th><th>Khoản mục CP</th><th style="width:44px"></th>
        </tr></thead>
        <tbody>${hach || `<tr><td colspan="${acc ? 14 : 12}" class="muted" style="text-align:center;height:60px">Chưa có dòng nào</td></tr>`}</tbody>
        <tfoot><tr>
          <td colspan="${acc ? 8 : 6}"></td>
          <td class="num">${nf5.format(qtySum)}</td><td></td>
          <td class="num" data-calc="vs">${money(vSub(v))}</td>
          <td class="num">${money(depSum)}</td><td colspan="2"></td>
        </tr></tfoot>
      </table>` : `
      <table class="g">
        <thead><tr><th class="ix">#</th><th>Mã dịch vụ</th><th>Tên dịch vụ</th><th class="num">Giá tính thuế</th><th>% thuế GTGT</th><th class="num">Tiền thuế GTGT</th><th>TK thuế GTGT</th></tr></thead>
        <tbody>${thue}</tbody>
        <tfoot><tr><td colspan="3"></td><td class="num">${money(vSub(v))}</td><td></td><td class="num">${money(vVat(v))}</td><td></td></tr></tfoot>
      </table>`}
    </div>

    <div class="vfoot">
      <div>
        <div class="tools">
          <button class="btn" data-act="addVLine">＋ Thêm dòng</button>
          <button class="btn" data-act="note">▤ Thêm ghi chú</button>
          <button class="btn" data-act="clearV"><span style="color:var(--red)">${trash()}</span> Xóa hết dòng</button>
        </div>
        ${v.note != null ? `<textarea class="inp" data-v="note" rows="2" style="margin-top:10px;max-width:560px" placeholder="Ghi chú">${esc(v.note)}</textarea>` : ''}
        <div class="ecom">
          <div class="fld"><label>Sàn thương mại điện tử</label>
            <select class="inp" data-v="market"><option></option>${['Shopee', 'Lazada', 'Tiki', 'TikTok Shop'].map(x => `<option ${v.market === x ? 'selected' : ''}>${x}</option>`).join('')}</select></div>
          <div class="fld"><label>Tên shop</label><input class="inp" data-v="shop" value="${esc(v.shop)}"></div>
        </div>
        <div style="margin-top:14px"><b>📎 Đính kèm</b> <span class="muted">Dung lượng tối đa 5MB</span></div>
        <label class="drop" id="drop"><input type="file" id="fileIn" multiple hidden>
          <span>⤒</span><span><span class="link">Chọn tệp</span> hoặc kéo và thả tệp vào đây</span></label>
        ${v.files.length ? `<div class="files">${v.files.map((f, i) => `<div><span>${esc(f.name)} <span class="muted">(${Math.ceil(f.size / 1024)} KB)</span></span><a class="link" data-act="rmFile" data-i="${i}">Xóa</a></div>`).join('')}</div>` : ''}
      </div>
      <div class="sums">
        <div class="row"><span>Tổng tiền dịch vụ</span>
          <input class="sumin" id="sumin" value="${money(vSub(v))}" title="Sửa tổng rồi Enter: tự phân bổ lại Thành tiền các dòng theo tỷ trọng"></div>
        <div class="row"><span>Thuế GTGT</span><span class="v" style="padding-right:7px">${money(vVat(v))}</span></div>
        <div class="row b"><span>Tổng tiền thanh toán</span><span class="v" style="padding-right:7px">${money(vTotal(v))}</span></div>
      </div>
    </div>
  </div>`;

  $('#pf').innerHTML = `
    <div class="keys">F9 - Thêm nhanh, Ctrl + S - Cất, Ctrl + F2 - Xem số tồn, Ctrl + 3 - Xem số dư tài khoản, Ctrl + V - Sao chép từ Excel, Ctrl + Shift + V - Sao chép từ Excel không tách dòng</div>
    <div class="fbar">
      <span class="toggle ${acc ? 'on' : ''}" data-act="toggleAcc"><span class="sw"></span> Hiển thị tài khoản</span>
      <div class="r">
        <button class="btn" data-act="vCancel">Hủy</button>
        <button class="btn" data-act="vHold">Hoãn</button>
        <button class="btn" data-act="vSave">Cất</button>
        <span class="split">
          <button class="btn p" data-act="vSaveClose">Cất và Đóng</button>
          <button class="btn p caret" data-act="menu" aria-label="Tùy chọn khác">⌄</button>
          ${ST.menu ? `<div class="menu"><button data-act="vSaveNew">Cất và Thêm</button><button data-act="vSaveClose">Cất và Đóng</button></div>` : ''}
        </span>
      </div>
    </div>`;

  wireDrop();
}

/* ------------------------------------------------------------ DANH SÁCH CHỨNG TỪ */
function renderList() {
  const rows = DB.vouchers.slice().reverse().map((v, i) => `
    <tr>
      <td class="ix">${i + 1}</td>
      <td><a class="link" data-act="open" data-id="${v.id}">${esc(v.no)}</a></td>
      <td>${vnDate(v.date)}</td>
      <td>${esc(v.gtNo)}</td>
      <td>${esc(v.listCode)}</td>
      <td style="white-space:normal;min-width:220px">${esc(v.memo)}</td>
      <td class="num">${money(v.lines.reduce((a, l) => a + (l.dep || 0), 0))}</td>
      <td class="num"><b>${money(vTotal(v))}</b></td>
      <td>${v.status === 'hold' ? '<span class="pill hold">Hoãn</span>' : '<span class="pill ok">Đã cất</span>'}</td>
      <td class="cellin"><button class="del" data-act="delV" data-id="${v.id}" title="Xóa">${trash()}</button></td>
    </tr>`).join('');
  $('#ph').innerHTML = `<h1>Chứng từ khấu hao TSCĐ</h1><span class="sub">${DB.vouchers.length} chứng từ</span>`;
  $('#pb').innerHTML = `
    <div class="card"><div class="tw"><table class="g">
      <thead><tr><th class="ix">#</th><th>Số chứng từ</th><th>Ngày hạch toán</th><th>Số CT ghi tăng</th><th>Mã DS mua hàng</th>
        <th>Diễn giải</th><th class="num">Số tiền khấu hao</th><th class="num">Tổng tiền thanh toán</th><th>Trạng thái</th><th style="width:44px"></th></tr></thead>
      <tbody>${rows || `<tr><td colspan="10" class="muted" style="text-align:center;height:80px">Chưa có chứng từ. Nhập 4 sheet rồi bấm <b>Lưu</b>.</td></tr>`}</tbody>
    </table></div></div>`;
  $('#pf').innerHTML = `<div class="fbar"><div class="r"><button class="btn p" data-go="s1">＋ Thêm mới (4 sheet)</button></div></div>`;
}

const trash = () => '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6"/></svg>';

/* =====================================================================
   HÀNH ĐỘNG
   ===================================================================== */

/** Lưu ở 4 sheet: kiểm tra -> sinh chứng từ -> chuyển sang màn kết quả */
function saveDraft() {
  const d = DB.draft;
  if (!CAN_PURCHASE.includes(DB.role)) return fail('Vai trò ' + ROLES[DB.role] + ' không được lưu phiếu mua hàng. Cần Nhân viên kho hoặc Kế toán trưởng.', 's1');
  if (!d.gtDate) return fail('Chưa nhập Ngày ghi tăng.', 's2');
  for (let i = 0; i < d.lines.length; i++) {
    const l = d.lines[i], r = 'Dòng ' + (i + 1) + ': ';
    if (!String(l.code).trim()) return fail(r + 'chưa nhập Mã hàng.', 's1');
    if (!String(l.name).trim()) return fail(r + 'chưa nhập Tên tài sản.', 's1');
    if (!(+l.qty > 0)) return fail(r + 'Số lượng phải lớn hơn 0.', 's1');
    if (!(+l.price > 0)) return fail(r + 'Đơn giá phải lớn hơn 0.', 's1');
    if (!l.noDep && !(+l.life > 0)) { d.sel = i; return fail('Tài sản ' + l.code + ': chưa nhập Thời gian sử dụng (hoặc tích "Không tính khấu hao").', 's2'); }
  }
  const dupe = d.lines.map(l => String(l.code).trim()).find((c, i, a) => a.indexOf(c) !== i);
  if (dupe) return fail('Mã hàng "' + dupe + '" bị trùng.', 's1');

  const start = draftStart(d);
  const summary = purchaseSummary(d);
  DB.seq.gt++; DB.seq.ds++; DB.seq.kh++;
  const gtNo = 'GT' + pad(DB.seq.gt), no = 'KH' + pad(DB.seq.kh);

  const v = {
    id: uid(), no, gtNo, listCode: summary.code, period: d.period,
    date: d.gtDate, docDate: d.gtDate, status: 'saved',
    memo: 'Khấu hao TSCĐ ' + monthLabel(d.period).toLowerCase() + ' theo chứng từ ghi tăng ' + gtNo,
    unit: [...new Set(d.lines.map(l => l.unit).filter(Boolean))].join(', '),
    wh: [...new Set(d.lines.map(l => l.wh))].join(', '),
    paid: false, payMethod: 'Tiền mặt', invoice: 'Nhận kèm hóa đơn', isPurchase: false,
    discount: 'Không chiết khấu', market: '', shop: '', note: null, files: [],
    summary, source: JSON.parse(JSON.stringify(d)),
    lines: d.lines.map(l => ({
      id: uid(), svcCode: String(l.code), svcName: l.name,
      accStock: l.accStock, accDebt: l.accDebt,
      obj: l.wh, objName: l.unit || l.type, uom: 'Cái',
      qty: +l.qty, price: +l.price, amount: amountOf(l),
      dep: depInPeriod(l, start, d.period), cost: +l.cost, vat: 8,
    })),
  };
  DB.vouchers.push(v);
  DB.draft = blankDraft();
  save();
  openVoucher(v.id);
  toast('Đã lưu. Tạo chứng từ ' + no + ' · ghi tăng ' + gtNo + ' · danh sách ' + summary.code + '.');
}
function fail(msg, route) {
  toast(msg, true);
  if (route && ST.route !== route) { ST.route = route; render(); }
  return false;
}

function openVoucher(id) {
  const v = DB.vouchers.find(x => x.id === id);
  if (!v) return;
  ST.route = 'result'; ST.vid = id; ST.v = JSON.parse(JSON.stringify(v));
  ST.dirty = false; ST.tab = 'hach'; ST.act = v.lines.length ? v.lines.length - 1 : -1; ST.menu = false;
  render();
  $('#pb').scrollTop = 0;
}
function commitVoucher(status) {
  const v = ST.v;
  if (!String(v.no).trim()) { toast('Chưa nhập Số chứng từ.', true); return false; }
  if (DB.vouchers.some(x => x.id !== v.id && x.no === v.no)) { toast('Số chứng từ ' + v.no + ' đã tồn tại.', true); return false; }
  if (status) v.status = status;
  const i = DB.vouchers.findIndex(x => x.id === v.id);
  DB.vouchers[i] = JSON.parse(JSON.stringify(v));
  save(); ST.dirty = false;
  return true;
}

/** sửa Tổng tiền dịch vụ -> phân bổ lại Thành tiền các dòng theo tỷ trọng */
function applyTotal(input) {
  const v = ST.v, target = Math.round(num(input.value)), cur = vSub(v);
  if (target === cur) { input.value = money(cur); return; }
  if (!v.lines.length) { toast('Chưa có dòng để phân bổ.', true); input.value = money(cur); return; }
  if (target < 0) { toast('Tổng tiền không được âm.', true); input.value = money(cur); return; }
  const parts = allocate(target, v.lines.map(l => l.amount));
  v.lines.forEach((l, i) => { l.amount = parts[i]; if (+l.qty) l.price = Math.round(parts[i] / l.qty * 100) / 100; });
  ST.dirty = true; renderResult();
  toast('Đã phân bổ ' + money(target) + ' cho ' + v.lines.length + ' dòng theo tỷ trọng.');
}

function confirmBox(title, msg, okLabel, onOk) {
  $('#modal').innerHTML = `<div class="ov"><div class="dlg"><h3>${title}</h3><p>${msg}</p>
    <div class="f"><button class="btn" data-m="no">Không</button><button class="btn p" data-m="ok">${okLabel}</button></div></div></div>`;
  $('#modal').onclick = e => {
    const b = e.target.closest('[data-m]');
    if (!b && !e.target.classList.contains('ov')) return;
    $('#modal').innerHTML = ''; $('#modal').onclick = null;
    if (b && b.dataset.m === 'ok') onOk();
  };
}
function toast(msg, err) {
  const t = document.createElement('div');
  t.className = 'toast' + (err ? ' err' : '');
  t.textContent = msg;
  $('#toasts').appendChild(t);
  setTimeout(() => t.remove(), err ? 4500 : 2800);
}

/** rời màn chứng từ khi còn thay đổi chưa cất */
function leave(fn) {
  if (ST.route === 'result' && ST.dirty) confirmBox('Dữ liệu chưa được cất', 'Bạn có muốn cất thay đổi trước khi rời màn hình?', 'Cất', () => { if (commitVoucher()) fn(); });
  else fn();
}
function go(r) {
  if (!r) return;
  leave(() => { ST.route = r; ST.menu = false; $('#shell').classList.remove('nav'); render(); $('#pb').scrollTop = 0; });
}

function wireDrop() {
  const drop = $('#drop'), inp = $('#fileIn');
  if (!drop) return;
  const add = files => {
    for (const f of files) {
      if (f.size > 5 * 1024 * 1024) { toast(f.name + ' vượt quá 5MB.', true); continue; }
      ST.v.files.push({ name: f.name, size: f.size });
    }
    ST.dirty = true; renderResult();
  };
  inp.onchange = () => add(inp.files);
  drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); };
  drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = e => { e.preventDefault(); add(e.dataTransfer.files); };
}

/* ---------------------------------------------------------------- sự kiện (ủy quyền) */
document.addEventListener('click', e => {
  const g = e.target.closest('[data-go]');
  if (g && !g.disabled) return go(g.dataset.go);

  // bấm vào 1 dòng lưới hạch toán -> dòng đó thành ô nhập (giống MISA)
  const row = e.target.closest('tr[data-row]');
  if (row && !e.target.closest('[data-act]') && ST.act !== +row.dataset.row) {
    ST.act = +row.dataset.row; renderResult();
    const inp = $(`tr[data-row="${ST.act}"] .ci`); inp && inp.focus();
    return;
  }

  const a = e.target.closest('[data-act]');
  if (!a) { if (ST.menu) { ST.menu = false; renderResult(); } return; }
  const act = a.dataset.act, i = +a.dataset.i;
  const d = DB.draft, v = ST.v;

  switch (act) {
    case 'nav': $('#shell').classList.toggle('nav'); break;
    case 'demo': confirmBox('Điền dữ liệu mẫu?', 'Dữ liệu đang nhập ở 4 sheet sẽ được thay bằng dữ liệu mẫu từ file Excel.', 'Điền', () => { DB.draft = demoDraft(); save(); render(); }); break;
    case 'reset': confirmBox('Hủy phiếu đang nhập?', 'Toàn bộ dữ liệu đang nhập ở 4 sheet sẽ bị xóa.', 'Hủy phiếu', () => { DB.draft = blankDraft(); save(); ST.route = 's1'; render(); }); break;
    case 'saveDraft': saveDraft(); break;
    case 'addLine': d.lines.push(blankLine()); save(); render(); { const r = $$('#pb tbody tr'); const x = r[r.length - 1]; x && x.querySelector('.ci').focus(); } break;
    case 'rmLine': d.lines.splice(i, 1); d.sel = 0; save(); render(); break;
    case 'pick': d.sel = i; save(); render(); break;

    case 'tab': ST.tab = a.dataset.t; renderResult(); break;
    case 'toggleAcc': DB.showAcc = !DB.showAcc; save(); renderResult(); break;
    case 'addVLine':
      v.lines.push({ id: uid(), svcCode: '', svcName: '', accStock: '214', accDebt: '627', obj: '', objName: '', uom: '', qty: 0, price: 0, amount: 0, dep: 0, cost: 2, vat: 8 });
      ST.act = v.lines.length - 1; ST.tab = 'hach'; ST.dirty = true; renderResult();
      { const x = $(`tr[data-row="${ST.act}"] .ci`); x && x.focus(); }
      break;
    case 'rmVLine': v.lines.splice(i, 1); ST.act = -1; ST.dirty = true; renderResult(); break;
    case 'clearV': confirmBox('Xóa hết dòng?', 'Toàn bộ ' + v.lines.length + ' dòng hạch toán sẽ bị xóa.', 'Xóa', () => { v.lines = []; ST.act = -1; ST.dirty = true; renderResult(); }); break;
    case 'note': if (v.note == null) { v.note = ''; ST.dirty = true; renderResult(); $('[data-v="note"]').focus(); } break;
    case 'rmFile': v.files.splice(i, 1); ST.dirty = true; renderResult(); break;
    case 'goSheet': toast('Chứng từ đã lưu. Dữ liệu gốc: ' + (a.dataset.r === 's2' ? 'Số CT ghi tăng ' + v.gtNo : 'Danh sách mua hàng ' + v.listCode + ' – ' + (v.summary ? v.summary.name : ''))); break;
    case 'help': toast('Bấm vào 1 dòng để sửa. Sửa "Tổng tiền dịch vụ" rồi Enter để tự phân bổ lại các dòng.'); break;
    case 'menu': ST.menu = !ST.menu; renderResult(); break;

    case 'vCancel':
      if (ST.dirty) confirmBox('Hủy thay đổi?', 'Các thay đổi chưa cất sẽ bị bỏ.', 'Hủy thay đổi', () => { ST.dirty = false; go('list'); });
      else go('list');
      break;
    case 'close': go('list'); break;
    case 'vHold': if (commitVoucher('hold')) { toast('Đã hoãn chứng từ ' + v.no + '.'); go('list'); } break;
    case 'vSave': if (commitVoucher('saved')) { toast('Đã cất chứng từ ' + v.no + '.'); renderResult(); renderSide(); } break;
    case 'vSaveClose': if (commitVoucher('saved')) { toast('Đã cất chứng từ ' + v.no + '.'); go('list'); } break;
    case 'vSaveNew': if (commitVoucher('saved')) { toast('Đã cất ' + v.no + '. Nhập phiếu mới.'); DB.draft = blankDraft(); save(); go('s1'); } break;

    case 'open': openVoucher(a.dataset.id); break;
    case 'delV': {
      const x = DB.vouchers.find(y => y.id === a.dataset.id);
      confirmBox('Xóa chứng từ ' + x.no + '?', 'Thao tác này không hoàn tác được.', 'Xóa', () => { DB.vouchers = DB.vouchers.filter(y => y.id !== x.id); save(); render(); });
      break;
    }
  }
});

/* gõ phím: cập nhật số liệu tính ngay, không vẽ lại cả trang (không mất con trỏ) */
document.addEventListener('input', e => {
  const el = e.target;
  if (el.id === 'sumin') return;
  if (ROUTES[ST.route]) {
    const row = el.closest('[data-i]'), k = el.dataset.k;
    if (row && k && el.type !== 'checkbox' && el.tagName !== 'SELECT') {
      const l = DB.draft.lines[+row.dataset.i];
      l[k] = el.dataset.n ? num(el.value) : el.value;
      save();
      if (ST.route === 's1') {
        const c = $(`[data-calc="amt${row.dataset.i}"]`); c && (c.textContent = money(amountOf(l)));
        $('[data-calc="sq"]').textContent = nfq.format(sumQty(DB.draft.lines));
        $('[data-calc="sa"]').textContent = money(sumAmount(DB.draft.lines));
      }
    }
  } else if (ST.route === 'result') {
    const v = ST.v;
    if (el.dataset.v && el.type !== 'radio' && el.type !== 'checkbox' && el.tagName !== 'SELECT') { v[el.dataset.v] = el.value; ST.dirty = true; }
    const row = el.closest('tr[data-i]'), k = el.dataset.k;
    if (row && k && el.tagName !== 'SELECT') {
      const l = v.lines[+row.dataset.i];
      if (['qty', 'price', 'amount', 'dep'].includes(k)) {
        l[k] = num(el.value);
        if (k === 'qty' || k === 'price') { l.amount = Math.round((+l.qty || 0) * (+l.price || 0)); const a = $(`tr[data-row="${row.dataset.i}"] [data-k="amount"]`); a && (a.value = money(l.amount)); }
        if (k === 'amount' && +l.qty) l.price = Math.round(l.amount / l.qty * 100) / 100;
      } else l[k] = el.value;
      ST.dirty = true;
      const vs = $('[data-calc="vs"]'); vs && (vs.textContent = money(vSub(v)));
      const vt = $('[data-calc="vt"]'); vt && (vt.textContent = money(vTotal(v)));
    }
  }
});

/* đổi giá trị xong (rời ô / chọn select): chuẩn hóa định dạng và vẽ lại */
document.addEventListener('change', e => {
  const el = e.target;
  if (el.id === 'role') { DB.role = el.value; save(); render(); return; }
  if (el.id === 'sumin' || el.id === 'fileIn') return;

  if (ROUTES[ST.route]) {
    const d = DB.draft;
    if (el.dataset.d) { d[el.dataset.d] = el.value; save(); render(); return; }
    const row = el.closest('[data-i]'), k = el.dataset.k;
    if (row && k) {
      const l = d.lines[+row.dataset.i];
      if (el.type === 'checkbox') l[k] = el.checked;
      else if (k === 'cost') l[k] = +el.value;
      else l[k] = el.dataset.n ? num(el.value) : el.value;
      save(); render();
    }
  } else if (ST.route === 'result') {
    const v = ST.v;
    if (el.dataset.v) {
      const f = el.dataset.v;
      v[f] = el.type === 'checkbox' ? el.checked : el.type === 'radio' ? el.value === '1' : el.value;
      ST.dirty = true;
      if (el.tagName === 'SELECT' || el.type === 'checkbox' || el.type === 'radio' || el.type === 'date') renderResult();
      return;
    }
    const row = el.closest('tr[data-i]'), k = el.dataset.k;
    if (row && k) {
      const l = v.lines[+row.dataset.i];
      if (k === 'cost' || k === 'vat') { l[k] = +el.value; ST.dirty = true; }
      renderResult();
    }
  }
});

document.addEventListener('keydown', e => {
  if (e.target.id === 'sumin') {
    if (e.key === 'Enter') { e.preventDefault(); applyTotal(e.target); }
    if (e.key === 'Escape') { e.target.value = money(vSub(ST.v)); e.target.blur(); }
    return;
  }
  if (ST.route === 'result') {
    if (e.key === 'F9') { e.preventDefault(); $('[data-act="addVLine"]').click(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); $('[data-act="vSave"]').click(); }
    if (e.key === 'Enter' && e.target.classList.contains('ci')) { e.preventDefault(); e.target.blur(); }
  } else if (ROUTES[ST.route]) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); saveDraft(); }
    if (e.key === 'Enter' && e.target.classList.contains('ci')) { e.preventDefault(); e.target.blur(); }
  }
});
document.addEventListener('focusout', e => { if (e.target.id === 'sumin') applyTotal(e.target); });
window.addEventListener('beforeunload', e => { if (ST.route === 'result' && ST.dirty) { e.preventDefault(); e.returnValue = ''; } });

/* ---------------------------------------------------------------- khởi động */
load();
render();
