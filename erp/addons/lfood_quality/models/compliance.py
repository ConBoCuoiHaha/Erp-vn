"""Hồ sơ công bố sản phẩm (CL07), kiểm nghiệm định kỳ (CL08), sức khỏe và tập huấn người trực tiếp sản xuất (CL09).

- Nghị quyết 66.13/2026/NQ-CP (hiệu lực 27/01/2026) thay thủ tục tự công bố bằng công bố tiêu chuẩn áp dụng (thực phẩm
  thường, phụ gia, bao bì) và đăng ký bản công bố (thực phẩm bảo vệ sức khỏe, dinh dưỡng y học, cho trẻ dưới 36 tháng);
  hồ sơ kèm phiếu kiểm nghiệm trong 12 tháng của phòng thử nghiệm ISO/IEC 17025; sản phẩm đã tự công bố phải công bố lại
  trước 27/01/2027, nhóm đăng ký hoàn thành trước 27/01/2028.
- Nghị định 46/2026/NĐ-CP, Điều 4-6: đăng ký bản công bố hợp quy, thời hạn theo kết quả chứng nhận, không quá 3 năm.
- Luật An toàn, vệ sinh lao động 2015, Điều 21: khám sức khỏe ít nhất 1 lần/năm (nặng nhọc, độc hại 6 tháng/lần).
Kiểm nghiệm định kỳ và tập huấn kiến thức an toàn thực phẩm theo chu kỳ công ty tự đặt trên từng mặt hàng, từng người.
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

DECL_KINDS = [('standard', 'Công bố tiêu chuẩn áp dụng'), ('registration', 'Đăng ký bản công bố sản phẩm'),
              ('conformity', 'Đăng ký bản công bố hợp quy'), ('legacy', 'Tự công bố cũ (trước 27/01/2026)'),
              ('legacy_reg', 'Đăng ký bản công bố cũ (trước 27/01/2026)')]
TRANSITION = {'legacy': date(2027, 1, 27), 'legacy_reg': date(2028, 1, 27)}


class LfoodProduct(models.Model):
    _inherit = 'lfood.product'

    declaration_required = fields.Boolean('Phải công bố sản phẩm')
    lab_test_months = fields.Integer('Chu kỳ kiểm nghiệm định kỳ (tháng)', help='0 là không theo dõi')
    declaration_ids = fields.One2many('lfood.product.declaration', 'product_id', 'Hồ sơ công bố')

    def _declaration_valid(self, at):
        self.ensure_one()
        return self.declaration_ids.filtered(lambda d: d.state == 'published' and d.date_published <= at
                                             and (not d.valid_until or d.valid_until >= at))


class LfoodLabTest(models.Model):
    _name = 'lfood.lab.test'
    _description = 'Phiếu kết quả kiểm nghiệm'
    _order = 'date desc, id desc'

    name = fields.Char('Số phiếu', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    product_id = fields.Many2one('lfood.product', 'Sản phẩm', required=True, index=True)
    lot_id = fields.Many2one('lfood.stock.lot', 'Lô mẫu', domain="[('product_id', '=', product_id)]")
    lab = fields.Char('Phòng thử nghiệm', required=True)
    lab_iso17025 = fields.Boolean('Phòng thử nghiệm đạt ISO/IEC 17025')
    date = fields.Date('Ngày có kết quả', required=True)
    passed = fields.Boolean('Đạt', default=True)
    sample_kept_until = fields.Date('Lưu mẫu đến')
    file = fields.Binary('Phiếu kết quả', attachment=True, required=True)
    file_name = fields.Char()
    note = fields.Char('Ghi chú')


class LfoodProductDeclaration(models.Model):
    _name = 'lfood.product.declaration'
    _description = 'Hồ sơ công bố sản phẩm'
    _order = 'date_submitted desc, id desc'

    name = fields.Char('Số hồ sơ, số tiếp nhận', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    product_id = fields.Many2one('lfood.product', 'Sản phẩm', required=True, index=True)
    kind = fields.Selection(DECL_KINDS, 'Loại hồ sơ', required=True, default='standard')
    authority = fields.Char('Cơ quan tiếp nhận')
    date_submitted = fields.Date('Ngày nộp', required=True)
    date_published = fields.Date('Ngày cơ quan đăng tải, tiếp nhận')
    lab_test_id = fields.Many2one('lfood.lab.test', 'Phiếu kiểm nghiệm kèm hồ sơ',
                                  domain="[('product_id', '=', product_id), ('passed', '=', True)]")
    certificate_until = fields.Date('Kết quả chứng nhận hợp quy có hiệu lực đến')
    valid_until = fields.Date('Hồ sơ hiệu lực đến', compute='_compute_valid', store=True)
    deadline = fields.Date('Hạn phải công bố lại', compute='_compute_valid', store=True)
    dossier = fields.Binary('Hồ sơ đã nộp', attachment=True)
    dossier_name = fields.Char()
    label = fields.Binary('Nhãn sản phẩm', attachment=True)
    label_name = fields.Char()
    state = fields.Selection([('draft', 'Nháp'), ('submitted', 'Đã nộp'), ('published', 'Đã được đăng tải'),
                              ('expired', 'Hết hiệu lực')], 'Trạng thái', default='draft', required=True, readonly=True,
                             index=True)

    @api.depends('kind', 'date_published', 'certificate_until')
    def _compute_valid(self):
        for rec in self:
            rec.deadline = TRANSITION.get(rec.kind, False)
            if rec.kind == 'conformity' and rec.date_published:
                years = int(self.env['lfood.legal.param'].get_value('CONG_BO_HOP_QUY_TOI_DA_NAM', rec.date_published,
                                                                    default=3))
                cap = rec.date_published + relativedelta(years=years, days=-1)
                rec.valid_until = min(cap, rec.certificate_until) if rec.certificate_until else cap
            else:
                rec.valid_until = rec.deadline

    def action_submit(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if rec.kind in ('standard', 'registration', 'conformity'):
                test = rec.lab_test_id
                months = int(self.env['lfood.legal.param'].get_value('CONG_BO_KIEM_NGHIEM_THANG', rec.date_submitted,
                                                                     default=12))
                if not test or not test.lab_iso17025:
                    raise ValidationError(_('Hồ sơ phải kèm phiếu kiểm nghiệm đạt của phòng thử nghiệm ISO/IEC 17025.'))
                if test.date < rec.date_submitted - relativedelta(months=months):
                    raise ValidationError(_('Phiếu kiểm nghiệm quá %s tháng tính đến ngày nộp.') % months)
                if not (rec.dossier and rec.label):
                    raise ValidationError(_('Đính kèm hồ sơ đã nộp và mẫu nhãn.'))
            if rec.kind == 'conformity' and not rec.certificate_until:
                raise ValidationError(_('Công bố hợp quy phải ghi thời hạn kết quả chứng nhận hợp quy.'))
            rec.state = 'submitted'
        return True

    def action_publish(self):
        for rec in self.filtered(lambda r: r.state == 'submitted'):
            if not rec.date_published:
                raise UserError(_('Ghi ngày cơ quan đăng tải, tiếp nhận hồ sơ; trước ngày đó chưa được sản xuất, kinh doanh.'))
            rec.state = 'published'
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Hồ sơ công bố %s của %s được đăng tải ngày %s') % (
                    rec.name, rec.product_id.display_name, rec.date_published.strftime('%d/%m/%Y')))
        return True


class LfoodWorkerCheck(models.Model):
    _name = 'lfood.worker.check'
    _description = 'Khám sức khỏe, tập huấn người lao động'
    _order = 'date desc, id desc'

    employee_id = fields.Many2one('lfood.employee', 'Người lao động', required=True, index=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    kind = fields.Selection([('health', 'Khám sức khỏe định kỳ'), ('food_safety', 'Tập huấn, xác nhận kiến thức an toàn thực phẩm'),
                             ('ohs', 'Huấn luyện an toàn, vệ sinh lao động')], 'Loại', required=True, default='health')
    date = fields.Date('Ngày', required=True)
    valid_months = fields.Integer('Hiệu lực (tháng)', required=True, default=12)
    valid_until = fields.Date('Hiệu lực đến', compute='_compute_until', store=True)
    result = fields.Char('Kết quả, loại sức khỏe')
    fit = fields.Boolean('Đủ điều kiện làm việc trực tiếp với thực phẩm', default=True)
    provider = fields.Char('Cơ sở khám, đơn vị tập huấn')
    file = fields.Binary('Giấy tờ', attachment=True)
    file_name = fields.Char()

    @api.depends('date', 'valid_months')
    def _compute_until(self):
        for rec in self:
            rec.valid_until = rec.date + relativedelta(months=rec.valid_months, days=-1) if rec.date else False

    @api.constrains('kind', 'valid_months', 'date')
    def _check_valid(self):
        for rec in self.filtered(lambda r: r.kind == 'health'):
            limit = int(self.env['lfood.legal.param'].get_value('KHAM_SUC_KHOE_DINH_KY_THANG', rec.date, default=12))
            if rec.valid_months > limit:
                raise ValidationError(_('Khám sức khỏe định kỳ ít nhất %s tháng một lần.') % limit)


class LfoodEmployee(models.Model):
    _inherit = 'lfood.employee'

    food_handler = fields.Boolean('Trực tiếp sản xuất, chế biến thực phẩm')
    worker_check_ids = fields.One2many('lfood.worker.check', 'employee_id', 'Khám sức khỏe, tập huấn')


class LfoodReminder(models.Model):
    _inherit = 'lfood.reminder'

    def _collect_extra(self, company, today, horizon):
        out = super()._collect_extra(company, today, horizon)
        products = self.env['lfood.product'].sudo().search([('company_id', 'in', (company.id, False)),
                                                           ('declaration_required', '=', True)])
        for p in products:
            valid = p._declaration_valid(today)
            end = min([d for d in valid.mapped('valid_until') if d] or [False]) if valid else False
            if not valid:
                out.append({'key': 'decl-missing-%s-%s' % (company.id, p.id), 'category': 'quality',
                            'title': _('%s chưa có hồ sơ công bố còn hiệu lực') % p.display_name, 'due_date': today,
                            'res_model': p._name, 'res_id': p.id})
            elif end and end <= horizon:
                out.append({'key': 'decl-exp-%s-%s-%s' % (company.id, p.id, end), 'category': 'quality',
                            'title': _('Hồ sơ công bố %s hết hiệu lực, phải công bố lại') % p.display_name,
                            'due_date': end, 'res_model': p._name, 'res_id': p.id})
            if p.lab_test_months:
                last = self.env['lfood.lab.test'].sudo().search([('product_id', '=', p.id), ('passed', '=', True)],
                                                                limit=1)
                due = last.date + relativedelta(months=p.lab_test_months) if last else today
                if due <= horizon:
                    out.append({'key': 'labtest-%s-%s-%s' % (company.id, p.id, due), 'category': 'quality',
                                'title': _('Kiểm nghiệm định kỳ %s') % p.display_name, 'due_date': due,
                                'res_model': p._name, 'res_id': p.id})
        emps = self.env['lfood.employee'].sudo().search([('company_id', '=', company.id), ('food_handler', '=', True)])
        for e in emps:
            for kind, label in (('health', _('Khám sức khỏe')), ('food_safety', _('Tập huấn an toàn thực phẩm'))):
                last = e.worker_check_ids.filtered(lambda c: c.kind == kind and c.fit).sorted('valid_until')[-1:]
                due = last.valid_until if last else today
                if due <= horizon:
                    out.append({'key': 'worker-%s-%s-%s' % (e.id, kind, due), 'category': 'hr',
                                'title': _('%s cho %s') % (label, e.name), 'due_date': due,
                                'res_model': e._name, 'res_id': e.id})
        return out
