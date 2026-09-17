"""Cài tiếng Việt, định dạng số và ngày kiểu Việt Nam, đặt tiếng Việt cho mọi người dùng."""


def setup_vietnamese(env):
    Lang = env['res.lang'].with_context(active_test=False)
    lang = Lang.search([('code', '=', 'vi_VN')], limit=1)
    if not lang or not lang.active:
        env['res.lang']._activate_lang('vi_VN')
        lang = Lang.search([('code', '=', 'vi_VN')], limit=1)
    # nạp bản dịch tiếng Việt cho mọi module đã cài
    env['ir.module.module'].search([('state', '=', 'installed')])._update_translations(['vi_VN'], overwrite=True)
    lang.write({
        'thousands_sep': '.', 'decimal_point': ',', 'grouping': '[3,0]',
        'date_format': '%d/%m/%Y', 'time_format': '%H:%M:%S', 'week_start': '1',
    })
    users = env['res.users'].with_context(active_test=False).search([('share', '=', False)])
    users.write({'lang': 'vi_VN'})
    env['res.company'].search([]).mapped('partner_id').write({'lang': 'vi_VN'})
    env['ir.default'].set('res.partner', 'lang', 'vi_VN')


def post_init_lang(env):
    setup_vietnamese(env)
