"""Kiểm tra chất lượng khi nhập (CL01, CL03) và hành động khắc phục (CL04).

Quy trình nội bộ theo hệ thống quản lý an toàn thực phẩm (ISO 22000, HACCP) của công ty, không phải mẫu pháp lý:
mặt hàng đánh dấu cần kiểm tra thì mỗi lô nhập mua hoặc nhập thành phẩm tự bị cách ly và sinh phiếu kiểm tra theo bộ
chỉ tiêu; đạt thì giải phóng lô, không đạt thì giữ cách ly và mở hành động khắc phục có hạn xử lý.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

QC_STAGES = {'purchase': 'incoming', 'factory': 'finished'}


class LfoodQcTemplate(models.Model):
    _name = 'lfood.qc.template'
    _description = 'Bộ chỉ tiêu kiểm tra'

    name = fields.Char('Tên bộ chỉ tiêu', required=True)
    line_ids = fields.One2many('lfood.qc.template.line', 'template_id', 'Chỉ tiêu', copy=True)
    active = fields.Boolean(default=True)


class LfoodQcTemplateLine(models.Model):
    _name = 'lfood.qc.template.line'
    _description = 'Chỉ tiêu kiểm tra'
    _order = 'sequence, id'

    template_id = fields.Many2one('lfood.qc.template', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char('Chỉ tiêu', required=True)
    requirement = fields.Char('Yêu cầu', required=True)


class LfoodProduct(models.Model):
    _inherit = 'lfood.product'

    qc_required = fields.Boolean('Cần kiểm tra chất lượng khi nhập')
    qc_template_id = fields.Many2one('lfood.qc.template', 'Bộ chỉ tiêu kiểm tra')


class LfoodStockPicking(models.Model):
    _inherit = 'lfood.stock.picking'

    qc_check_ids = fields.One2many('lfood.qc.check', 'picking_id', 'Phiếu kiểm tra chất lượng')

    def action_done(self):
        todo = self.filtered(lambda p: p.state == 'draft' and p.kind == 'in' and p.purpose in QC_STAGES)
        res = super().action_done()
        Check = self.env['lfood.qc.check'].sudo()
        for picking in todo.filtered(lambda p: p.state == 'done'):
            for line in picking.line_ids.filtered(lambda l: l.product_id.qc_required and l.lot_id):
                lot = line.lot_id
                if not lot.hold:
                    lot.sudo().write({'hold': True, 'hold_reason': _('Chờ kiểm tra chất lượng'), 'hold_by': self.env.uid,
                                      'hold_date': picking.date})
                template = line.product_id.qc_template_id
                Check.create({
                    'company_id': picking.company_id.id, 'picking_id': picking.id, 'lot_id': lot.id,
                    'stage': QC_STAGES[picking.purpose], 'quantity': line.quantity, 'date': picking.date,
                    'line_ids': [(0, 0, {'name': t.name, 'requirement': t.requirement}) for t in template.line_ids]})
        return res


class LfoodQcCheck(models.Model):
    _name = 'lfood.qc.check'
    _description = 'Phiếu kiểm tra chất lượng'
    _order = 'date desc, id desc'

    name = fields.Char('Số', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    stage = fields.Selection([('incoming', 'Nguyên liệu, hàng mua đầu vào'), ('finished', 'Thành phẩm trước khi xuất')],
                             'Giai đoạn', required=True, default='incoming')
    picking_id = fields.Many2one('lfood.stock.picking', 'Phiếu nhập', readonly=True, index=True)
    partner_id = fields.Many2one(related='picking_id.partner_id', string='Nhà cung cấp')
    lot_id = fields.Many2one('lfood.stock.lot', 'Lô', required=True, index=True)
    product_id = fields.Many2one(related='lot_id.product_id', store=True)
    quantity = fields.Float('Số lượng', digits=(16, 3))
    date = fields.Date('Ngày', required=True, default=fields.Date.context_today)
    inspector = fields.Char('Người kiểm tra')
    line_ids = fields.One2many('lfood.qc.check.line', 'check_id', 'Kết quả theo chỉ tiêu')
    conclusion = fields.Text('Kết luận')
    action_ids = fields.One2many('lfood.qc.action', 'check_id', 'Hành động khắc phục')
    decided_by = fields.Many2one('res.users', 'Người quyết định', readonly=True, copy=False)
    state = fields.Selection([('pending', 'Chờ kiểm tra'), ('passed', 'Đạt'), ('failed', 'Không đạt')], 'Kết quả',
                             default='pending', required=True, readonly=True, copy=False, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('lfood.qc.check') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_qc_system') and self.filtered(lambda r: r.state != 'pending'):
            raise UserError(_('Phiếu kiểm tra đã kết luận không sửa được.'))
        return super().write(vals)

    def _decide(self, state):
        if not (self.env.user.has_group('lfood_base.group_chief_accountant')
                or self.env.user.has_group('lfood_base.group_director')):
            raise UserError(_('Chỉ Kế toán trưởng hoặc Giám đốc được kết luận kiểm tra, giải phóng lô.'))
        for rec in self.filtered(lambda r: r.state == 'pending'):
            if not rec.inspector:
                raise UserError(_('Ghi người kiểm tra.'))
            if rec.line_ids.filtered(lambda l: not l.result):
                raise UserError(_('Ghi kết quả cho mọi chỉ tiêu.'))
            if state == 'passed' and rec.line_ids.filtered(lambda l: not l.passed):
                raise UserError(_('Còn chỉ tiêu không đạt, không kết luận Đạt được.'))
            if state == 'failed' and not rec.conclusion:
                raise UserError(_('Ghi kết luận, nguyên nhân không đạt.'))
            rec.with_context(lfood_qc_system=True).write({'state': state, 'decided_by': self.env.uid})
            lot = rec.lot_id.sudo()
            others = self.search([('lot_id', '=', lot.id), ('state', '=', 'pending'), ('id', '!=', rec.id)])
            if state == 'passed' and not others:
                lot.write({'hold': False})
            elif state == 'failed':
                lot.write({'hold': True, 'hold_reason': _('Không đạt kiểm tra %s') % rec.name})
                self.env['lfood.qc.action'].create({
                    'check_id': rec.id, 'company_id': rec.company_id.id, 'name': _('Xử lý lô %s không đạt') % lot.name,
                    'cause': rec.conclusion, 'deadline': fields.Date.add(rec.date, days=7)})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Kiểm tra lô %s của %s: %s') % (lot.name, lot.product_id.display_name,
                                                          dict(self._fields['state'].selection)[state]))
        return True

    def action_pass(self):
        return self._decide('passed')

    def action_fail(self):
        return self._decide('failed')


class LfoodQcCheckLine(models.Model):
    _name = 'lfood.qc.check.line'
    _description = 'Kết quả chỉ tiêu'

    check_id = fields.Many2one('lfood.qc.check', required=True, ondelete='cascade', index=True)
    name = fields.Char('Chỉ tiêu', required=True)
    requirement = fields.Char('Yêu cầu')
    result = fields.Char('Kết quả')
    passed = fields.Boolean('Đạt')

    def write(self, vals):
        if self.filtered(lambda l: l.check_id.state != 'pending'):
            raise UserError(_('Phiếu kiểm tra đã kết luận không sửa được.'))
        return super().write(vals)


class LfoodQcAction(models.Model):
    _name = 'lfood.qc.action'
    _description = 'Hành động khắc phục'
    _order = 'state, deadline'

    name = fields.Char('Nội dung', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    check_id = fields.Many2one('lfood.qc.check', 'Phiếu kiểm tra', index=True)
    cause = fields.Text('Nguyên nhân')
    measure = fields.Text('Biện pháp khắc phục, phòng ngừa')
    responsible = fields.Char('Người phụ trách')
    deadline = fields.Date('Hạn xử lý', required=True)
    done_on = fields.Date('Ngày hoàn thành', readonly=True)
    state = fields.Selection([('open', 'Đang xử lý'), ('done', 'Đã xong')], 'Trạng thái', default='open',
                             required=True, readonly=True)

    def action_done(self):
        for rec in self.filtered(lambda r: r.state == 'open'):
            if not (rec.measure and rec.responsible):
                raise UserError(_('Ghi biện pháp và người phụ trách trước khi đóng.'))
            rec.write({'state': 'done', 'done_on': fields.Date.context_today(self)})
        return True


class LfoodReminder(models.Model):
    _inherit = 'lfood.reminder'

    category = fields.Selection(selection_add=[('quality', 'Chất lượng')], ondelete={'quality': 'cascade'})

    def _collect_extra(self, company, today, horizon):
        out = super()._collect_extra(company, today, horizon)
        for act in self.env['lfood.qc.action'].sudo().search([
                ('company_id', '=', company.id), ('state', '=', 'open'), ('deadline', '<=', horizon)]):
            out.append({'key': 'qcact-%s-%s' % (act.id, act.deadline), 'category': 'quality', 'title': act.name,
                        'due_date': act.deadline, 'res_model': act._name, 'res_id': act.id})
        for chk in self.env['lfood.qc.check'].sudo().search([('company_id', '=', company.id), ('state', '=', 'pending')]):
            out.append({'key': 'qcchk-%s' % chk.id, 'category': 'quality',
                        'title': _('Kiểm tra chất lượng lô %s (%s) đang chờ') % (chk.lot_id.name, chk.product_id.display_name),
                        'due_date': chk.date, 'res_model': chk._name, 'res_id': chk.id})
        return out
