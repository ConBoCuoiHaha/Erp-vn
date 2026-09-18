# Duyệt mọi menu như trình duyệt, theo từng vai trò: tải giao diện, đọc danh sách, mở bản ghi, mở biểu mẫu mới,
# áp từng bộ lọc / nhóm theo, pivot, graph, in báo cáo. Chạy độc lập hoặc nối sau smoke_test.py (để có dữ liệu).
#   Get-Content tests\ui_crawl.py -Raw | docker compose run --rm -T odoo odoo shell -c /etc/odoo/odoo.conf -d lfood --no-http
import traceback as _tb
from lxml import etree as _et
from odoo.tools.safe_eval import safe_eval as _se, datetime as _sdt, dateutil as _sdu, time as _stime
from odoo.exceptions import AccessError as _AE, UserError as _UE

_errs, _n = [], [0]


def _eval(expr, ctx):
    if not expr:
        return {} if expr is None else expr
    if not isinstance(expr, str):
        return expr
    return _se(expr, {'uid': ctx['uid'], 'context': ctx, 'context_today': _sdt.date.today, 'datetime': _sdt,
                      'relativedelta': _sdu.relativedelta.relativedelta, 'time': _stime, 'active_id': False, 'active_ids': [],
                      'allowed_company_ids': ctx.get('allowed_company_ids', []),
                      'current_company_id': ctx.get('allowed_company_ids', [False])[0]})


def _spec(Model, node):
    # đặc tả đọc giống web client: trường cấp trên cùng của view, many2one kèm display_name, x2many kèm trường con
    spec = {}
    for f in node.iter('field'):
        if any(a.tag in ('list', 'form', 'kanban') for a in f.iterancestors() if a is not node) or f.get('name') not in Model._fields:
            continue
        fld = Model._fields[f.get('name')]
        if fld.type == 'many2one':
            spec[fld.name] = {'fields': {'display_name': {}}}
        elif fld.type in ('one2many', 'many2many'):
            sub = next((c for c in f if c.tag in ('list', 'kanban')), None)
            Co = Model.env[fld.comodel_name]
            spec[fld.name] = {'fields': _spec(Co, sub) if sub is not None else {'display_name': {}}}
        else:
            spec[fld.name] = {}
    return spec


def _where():
    # dòng mã lfood gần nhất gây lỗi
    fr = [f for f in _tb.extract_tb(__import__('sys').exc_info()[2]) if 'lfood_' in f.filename]
    return ('  @ %s:%s %s' % (fr[-1].filename.split('addons/')[-1], fr[-1].lineno, fr[-1].name)) if fr else ''


def _try(who, what, fn):
    _n[0] += 1
    sp = 'c%s' % _n[0]
    env.cr.execute('SAVEPOINT %s' % sp)
    try:
        fn()
        env.flush_all()
    except (_AE, _UE) as e:
        # từ chối có chủ đích vẫn là lỗi giao diện nếu người dùng NHÌN THẤY menu đó
        _errs.append((who, what, '%s: %s%s' % (type(e).__name__, str(e).splitlines()[0][:200], _where())))
    except Exception as e:
        _errs.append((who, what, ''.join(_tb.format_exception_only(type(e), e)).strip()[:300] + _where()))
    env.cr.execute('ROLLBACK TO SAVEPOINT %s' % sp)
    env.invalidate_all()


def _crawl_action(u, act, menu_path):
    ctx = {'uid': u.id, 'lang': 'vi_VN', 'tz': 'Asia/Ho_Chi_Minh', 'allowed_company_ids': u.company_ids.ids}
    who = u.login
    try:
        actx = dict(ctx, **_eval(act.context or '{}', ctx))
        dom = _eval(act.domain or '[]', ctx) or []
    except Exception as e:
        _errs.append((who, menu_path, 'context/domain hành động: %s' % e)); return
    M = env[act.res_model].with_user(u).with_context(actx)
    modes = [m.strip() for m in (act.view_mode or 'list').split(',')]
    views = []
    for m in modes:
        v = act.view_ids.filtered(lambda x: x.view_mode == m)[:1].view_id or (act.view_id if act.view_id.type == m else False)
        views.append((v.id if v else False, m))
    res = {}

    def load():
        res.update(M.get_views(views + [(act.search_view_id.id or False, 'search')], {'toolbar': True}))
    _try(who, '%s | tải giao diện' % menu_path, load)
    if not res:
        return
    arch = {k: _et.fromstring(v['arch']) for k, v in res['views'].items()}
    first = M.browse()

    if 'list' in arch or 'kanban' in arch:
        node = arch.get('list', arch.get('kanban'))

        def lst():
            r = M.web_search_read(dom, _spec(M, node), limit=80)
            nonlocal first
            first = M.browse([x['id'] for x in r['records'][:3]])
        _try(who, '%s | danh sách' % menu_path, lst)
    else:
        first = M.search(dom, limit=3)

    if 'form' in arch:
        fspec = _spec(M, arch['form'])
        if first:
            _try(who, '%s | mở bản ghi' % menu_path, lambda: first.web_read(fspec))
        if arch['form'].get('create') not in ('0', 'false', 'False') and M.has_access('create'):
            _try(who, '%s | biểu mẫu mới' % menu_path, lambda: M.onchange({}, [], fspec))

    for kind in ('pivot', 'graph'):
        if kind in arch:
            gb = [f.get('name') for f in arch[kind].iter('field') if f.get('type') in ('row', 'col') and f.get('name') in M._fields]
            ms = ['%s:sum' % f.get('name') for f in arch[kind].iter('field') if f.get('type') == 'measure' and f.get('name') in M._fields]
            _try(who, '%s | %s' % (menu_path, kind), lambda: M.formatted_read_group(dom, gb[:1], ['__count'] + ms))

    for flt in arch['search'].iter('filter'):
        name = flt.get('name') or flt.get('string')
        if flt.get('domain'):
            def fdom(flt=flt):
                M.search_count(dom + _eval(flt.get('domain'), ctx))
            _try(who, '%s | lọc "%s"' % (menu_path, name), fdom)
        if flt.get('context') and 'group_by' in flt.get('context'):
            def fgb(flt=flt):
                g = _eval(flt.get('context'), ctx).get('group_by')
                g = [g] if isinstance(g, str) else g
                # web client tự thêm :month cho trường ngày
                g = [x if ':' in x or M._fields[x].type not in ('date', 'datetime') else x + ':month' for x in g]
                M.formatted_read_group(dom, g, ['__count'])
            _try(who, '%s | nhóm "%s"' % (menu_path, name), fgb)


_logins = ['hugoboss.v6@gmail.com', 'giamdoc', 'ketoantruong', 'ketoanvien', 'nhanvien']
_seen = 0
for _u in env['res.users'].search([('login', 'in', _logins)]):
    # đúng danh sách menu web client hiển thị (search() không lọc menu có cha bị ẩn)
    _M = env['ir.ui.menu'].with_user(_u).with_context(lang='vi_VN')
    _menus = _M.browse([k for k in _M.load_menus(False) if isinstance(k, int)]).filtered('action')
    for _m in _menus:
        _a = _m.action.sudo()
        if _a._name != 'ir.actions.act_window' or _a.res_model not in env:
            continue
        _seen += 1
        _crawl_action(_u, _a, _m.complete_name)

# báo cáo in: mỗi mẫu in lfood trên một bản ghi có thật
_admin = env['res.users'].search([('login', '=', _logins[0])])
for _r in env['ir.actions.report'].search([('model', '!=', False)]):
    if not (_r.get_external_id().get(_r.id) or '').startswith('lfood'):
        continue
    _rec = env[_r.model].sudo().search([], limit=1)
    if _rec:
        _try('in', '%s (%s)' % (_r.name, _r.report_name),
             lambda: env['ir.actions.report'].with_user(_admin)._render_qweb_html(_r.report_name, _rec.ids))

print('\n==== DUYET GIAO DIEN ====')
print('Menu x vai tro: %s, thao tac: %s' % (_seen, _n[0]))
for _w, _p, _e in _errs:
    print('LOI  [%s] %s\n     %s' % (_w, _p, _e))
print('Tong loi giao dien: %s' % len(_errs))
