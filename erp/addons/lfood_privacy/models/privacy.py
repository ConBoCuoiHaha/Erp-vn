"""Bảo vệ dữ liệu cá nhân (HT11) theo Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 và Nghị định 356/2025/NĐ-CP
(cùng hiệu lực 01/01/2026).

- Sổ ghi nhận sự đồng ý hoặc căn cứ xử lý khác; đồng ý phải lưu được thời điểm, nội dung, cách thể hiện; rút lại được.
- Yêu cầu của chủ thể dữ liệu: hạn phản hồi 2 ngày làm việc và hạn thực hiện theo từng loại; nhắc hạn.
- Sổ sự cố vi phạm; dữ liệu vị trí, sinh trắc học phải báo chủ thể trong 72 giờ; hồ sơ lưu tối thiểu 5 năm.
- Nhật ký mở xem hồ sơ nhân sự, bảng lương (dữ liệu tài chính là dữ liệu nhạy cảm).
- Thông tin người phụ trách bảo vệ dữ liệu và tình trạng miễn trừ của doanh nghiệp.
Chưa làm: hồ sơ đánh giá tác động (Mẫu 09, 10) nộp Bộ Công an, xóa hoặc ẩn danh dữ liệu (sổ kế toán phải lưu theo
Luật Kế toán nên yêu cầu xóa được ghi nhận và xử lý thủ công).
"""
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .privacy_calc import deadlines

SUBJECT_KINDS = [('employee', 'Người lao động'), ('partner', 'Khách hàng, nhà cung cấp'), ('other', 'Khác')]
REQUEST_KINDS = [('withdraw', 'Rút lại sự đồng ý, hạn chế hoặc phản đối xử lý'),
                 ('access', 'Xem, chỉnh sửa, cung cấp dữ liệu'), ('delete', 'Xóa dữ liệu'),
                 ('protect', 'Yêu cầu biện pháp bảo vệ dữ liệu')]
BASES = [('consent', 'Sự đồng ý của chủ thể'), ('contract', 'Thực hiện hợp đồng'),
         ('labor', 'Quản lý lao động theo hợp đồng, nội quy'), ('law', 'Thực hiện nghĩa vụ theo luật')]
CHANNELS = [('paper', 'Văn bản giấy'), ('email', 'Thư điện tử'), ('call', 'Cuộc gọi có ghi âm'),
            ('web', 'Trang web, ứng dụng')]
SIZES = [('micro', 'Siêu nhỏ'), ('small', 'Nhỏ'), ('medium', 'Vừa'), ('large', 'Lớn'), ('startup', 'Khởi nghiệp')]


class ResCompany(models.Model):
    _inherit = 'res.company'

    lfood_dpo_name = fields.Char('Người phụ trách bảo vệ dữ liệu cá nhân')
    lfood_dpo_contact = fields.Char('Liên hệ phụ trách bảo vệ dữ liệu')
    lfood_size = fields.Selection(SIZES, 'Quy mô doanh nghiệp', default='small')
    lfood_sensitive_data = fields.Boolean('Trực tiếp xử lý dữ liệu cá nhân nhạy cảm', default=True,
                                          help='Dữ liệu tài chính (lương, tài khoản ngân hàng), sức khỏe của người lao động '
                                               'là dữ liệu nhạy cảm')
    lfood_subject_count = fields.Integer('Số chủ thể dữ liệu đã xử lý (tích lũy)')
    lfood_privacy_exempt = fields.Char('Miễn trừ bảo vệ dữ liệu', compute='_compute_privacy_exempt')

    @api.depends('lfood_size', 'lfood_sensitive_data', 'lfood_subject_count')
    def _compute_privacy_exempt(self):
        for rec in self:
            if rec.lfood_sensitive_data or rec.lfood_subject_count >= 100_000:
                rec.lfood_privacy_exempt = _('Không được miễn: trực tiếp xử lý dữ liệu nhạy cảm hoặc từ 100.000 chủ thể; '
                                             'phải có người phụ trách và lập hồ sơ đánh giá tác động')
            elif rec.lfood_size == 'micro':
                rec.lfood_privacy_exempt = _('Doanh nghiệp siêu nhỏ: miễn bổ nhiệm người phụ trách, lập hồ sơ đánh giá tác động')
            elif rec.lfood_size in ('small', 'startup'):
                rec.lfood_privacy_exempt = _('Miễn bổ nhiệm người phụ trách, lập hồ sơ đánh giá tác động đến 31/12/2030')
            else:
                rec.lfood_privacy_exempt = _('Không thuộc diện miễn trừ')


class LfoodPrivacyConsent(models.Model):
    _name = 'lfood.privacy.consent'
    _description = 'Căn cứ xử lý dữ liệu cá nhân'
    _order = 'given_on desc, id desc'

    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    subject_kind = fields.Selection(SUBJECT_KINDS, 'Chủ thể là', required=True, default='employee')
    employee_id = fields.Many2one('lfood.employee', 'Người lao động', index=True)
    partner_id = fields.Many2one('res.partner', 'Đối tượng', index=True)
    subject_name = fields.Char('Tên chủ thể', compute='_compute_subject_name', store=True)
    purpose = fields.Char('Mục đích xử lý', required=True)
    data_types = fields.Char('Loại dữ liệu', required=True, help='Ví dụ: họ tên, số định danh, tài khoản ngân hàng, lương')
    sensitive = fields.Boolean('Có dữ liệu nhạy cảm')
    basis = fields.Selection(BASES, 'Căn cứ xử lý', required=True, default='consent')
    channel = fields.Selection(CHANNELS, 'Cách thể hiện đồng ý')
    given_on = fields.Datetime('Thời điểm đồng ý, ghi nhận', required=True, default=fields.Datetime.now)
    evidence = fields.Binary('Bằng chứng (văn bản, ghi âm)', attachment=True)
    evidence_name = fields.Char('Tên tệp')
    withdrawn_on = fields.Datetime('Thời điểm rút lại', readonly=True)
    state = fields.Selection([('active', 'Đang hiệu lực'), ('withdrawn', 'Đã rút lại')], 'Trạng thái',
                             compute='_compute_state', store=True)

    @api.depends('employee_id', 'partner_id', 'subject_kind')
    def _compute_subject_name(self):
        for rec in self:
            rec.subject_name = rec.employee_id.name if rec.subject_kind == 'employee' else rec.partner_id.name

    @api.depends('withdrawn_on')
    def _compute_state(self):
        for rec in self:
            rec.state = 'withdrawn' if rec.withdrawn_on else 'active'

    @api.constrains('basis', 'channel', 'evidence', 'subject_kind', 'employee_id', 'partner_id')
    def _check_consent(self):
        for rec in self:
            if rec.basis == 'consent' and not (rec.channel and rec.evidence):
                raise ValidationError(_('Sự đồng ý phải ghi cách thể hiện và đính kèm bằng chứng để kiểm chứng được.'))
            if (rec.subject_kind == 'employee' and not rec.employee_id) or (rec.subject_kind == 'partner' and not rec.partner_id):
                raise ValidationError(_('Chọn chủ thể dữ liệu.'))

    def write(self, vals):
        if self.filtered('withdrawn_on') and not self.env.context.get('lfood_privacy_system'):
            raise UserError(_('Ghi nhận đã rút lại không sửa được.'))
        return super().write(vals)

    def action_withdraw(self):
        for rec in self.filtered(lambda r: not r.withdrawn_on):
            if rec.basis != 'consent':
                raise UserError(_('Chỉ rút lại được căn cứ là sự đồng ý; căn cứ hợp đồng, lao động, luật không rút lại được.'))
            rec.with_context(lfood_privacy_system=True).write({'withdrawn_on': fields.Datetime.now()})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.subject_name, company_id=rec.company_id.id,
                summary=_('%s rút lại sự đồng ý: %s') % (rec.subject_name, rec.purpose))
        return True


class LfoodPrivacyRequest(models.Model):
    _name = 'lfood.privacy.request'
    _description = 'Yêu cầu của chủ thể dữ liệu'
    _order = 'due_date, id'

    name = fields.Char('Số', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    subject_kind = fields.Selection(SUBJECT_KINDS, 'Chủ thể là', required=True, default='employee')
    employee_id = fields.Many2one('lfood.employee', 'Người lao động')
    partner_id = fields.Many2one('res.partner', 'Đối tượng')
    subject_name = fields.Char('Tên người yêu cầu', required=True)
    kind = fields.Selection(REQUEST_KINDS, 'Loại yêu cầu', required=True)
    detail = fields.Text('Nội dung yêu cầu', required=True)
    received_on = fields.Date('Ngày nhận', required=True, default=fields.Date.context_today)
    third_party = fields.Boolean('Cần bên xử lý, bên thứ ba phối hợp')
    extended = fields.Boolean('Đã gia hạn một lần', readonly=True)
    respond_by = fields.Date('Hạn phản hồi', compute='_compute_deadlines', store=True)
    due_date = fields.Date('Hạn thực hiện', compute='_compute_deadlines', store=True)
    responded_on = fields.Date('Ngày phản hồi', readonly=True)
    done_on = fields.Date('Ngày hoàn thành', readonly=True)
    result = fields.Text('Kết quả xử lý')
    state = fields.Selection([('new', 'Mới nhận'), ('responded', 'Đã phản hồi'), ('done', 'Đã thực hiện'),
                              ('refused', 'Từ chối có lý do')], 'Trạng thái', default='new', required=True,
                             readonly=True, copy=False, index=True)
    late = fields.Boolean('Trễ hạn', compute='_compute_late')

    @api.depends('kind', 'received_on', 'third_party', 'extended')
    def _compute_deadlines(self):
        for rec in self:
            if rec.kind and rec.received_on:
                rec.respond_by = self.env['lfood.holiday'].add_working_days(rec.received_on, 2)
                rec.due_date = deadlines(rec.kind, rec.received_on, rec.third_party, rec.extended)
            else:
                rec.respond_by = rec.due_date = False

    def _compute_late(self):
        today = fields.Date.context_today(self)
        for rec in self:
            end = rec.done_on or (today if rec.state in ('new', 'responded') else rec.due_date)
            rec.late = bool(rec.due_date and end and end > rec.due_date)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('lfood.privacy.request') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_privacy_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái chỉ đổi bằng các nút trên màn hình.'))
            if self.filtered(lambda r: r.state in ('done', 'refused')):
                raise UserError(_('Yêu cầu đã xử lý xong không sửa được.'))
        return super().write(vals)

    def _log(self, text):
        self.env['lfood.audit.log']._record_event(
            'state', model=self._name, res_id=self.id, res_name=self.name, company_id=self.company_id.id,
            summary='%s (%s): %s' % (self.name, self.subject_name, text))

    def action_respond(self):
        for rec in self.filtered(lambda r: r.state == 'new'):
            rec.with_context(lfood_privacy_system=True).write(
                {'state': 'responded', 'responded_on': fields.Date.context_today(self)})
            rec._log(_('đã phản hồi đã nhận yêu cầu, hạn thực hiện %s') % rec.due_date.strftime('%d/%m/%Y'))
        return True

    def action_extend(self):
        for rec in self:
            if rec.extended or rec.state not in ('new', 'responded'):
                raise UserError(_('Chỉ được gia hạn một lần cho yêu cầu đang xử lý.'))
            rec.with_context(lfood_privacy_system=True).write({'extended': True})
            rec._log(_('gia hạn, hạn mới %s') % rec.due_date.strftime('%d/%m/%Y'))
        return True

    def _finish(self, state):
        for rec in self:
            if rec.state == 'new':
                raise UserError(_('Phản hồi cho người yêu cầu trước khi kết thúc.'))
            if rec.state != 'responded':
                continue
            if not rec.result:
                raise UserError(_('Ghi kết quả xử lý hoặc lý do từ chối.'))
            rec.with_context(lfood_privacy_system=True).write({'state': state, 'done_on': fields.Date.context_today(self)})
            rec._log(_('%s: %s') % (dict(self._fields['state'].selection)[state], rec.result))
        return True

    def action_done(self):
        return self._finish('done')

    def action_refuse(self):
        return self._finish('refused')


class LfoodPrivacyBreach(models.Model):
    _name = 'lfood.privacy.breach'
    _description = 'Sự cố vi phạm dữ liệu cá nhân'
    _order = 'detected_at desc'

    name = fields.Char('Tóm tắt sự cố', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    detected_at = fields.Datetime('Thời điểm phát hiện', required=True, default=fields.Datetime.now)
    description = fields.Text('Diễn biến, dữ liệu bị ảnh hưởng', required=True)
    subject_count = fields.Integer('Số chủ thể bị ảnh hưởng')
    location_biometric = fields.Boolean('Có dữ liệu vị trí hoặc sinh trắc học')
    subject_notice_by = fields.Datetime('Hạn báo chủ thể', compute='_compute_notice_by', store=True)
    authority_notified_at = fields.Datetime('Đã báo cơ quan chuyên trách (A05, Bộ Công an)')
    subjects_notified_at = fields.Datetime('Đã báo chủ thể dữ liệu')
    remedy = fields.Text('Biện pháp khắc phục')
    fixed_on = fields.Date('Ngày khắc phục xong')
    keep_until = fields.Date('Lưu hồ sơ đến', compute='_compute_notice_by', store=True)

    @api.depends('detected_at', 'location_biometric', 'fixed_on')
    def _compute_notice_by(self):
        for rec in self:
            rec.subject_notice_by = rec.detected_at + timedelta(hours=72) if rec.location_biometric and rec.detected_at else False
            rec.keep_until = fields.Date.add(rec.fixed_on, years=5) if rec.fixed_on else False

    def unlink(self):
        today = fields.Date.context_today(self)
        if self.filtered(lambda r: not r.keep_until or r.keep_until > today):
            raise UserError(_('Hồ sơ sự cố phải lưu tối thiểu 5 năm sau khi khắc phục.'))
        return super().unlink()


class LfoodEmployee(models.Model):
    _inherit = 'lfood.employee'

    def _lfood_log_view(self):
        """Ghi nhật ký mở xem dữ liệu nhạy cảm, mỗi người mỗi hồ sơ một lần trong ngày."""
        if self.env.su or self.env.context.get('lfood_no_view_log'):
            return
        Log = self.env['lfood.audit.log'].sudo()
        start = fields.Datetime.to_string(fields.Datetime.start_of(fields.Datetime.now(), 'day'))
        for rec in self:
            if not Log.search_count([('action', '=', 'view'), ('model', '=', rec._name), ('res_id', '=', rec.id),
                                     ('user_id', '=', self.env.uid), ('event_time', '>=', start)]):
                Log._record_event('view', model=rec._name, res_id=rec.id, res_name=rec.display_name,
                                  company_id=rec.company_id.id, user=self.env.user,
                                  summary=_('Mở xem hồ sơ %s') % rec.display_name)

    def web_read(self, specification):
        if len(self) == 1:
            self._lfood_log_view()
        return super().web_read(specification)


class LfoodPayrollSlip(models.Model):
    _inherit = 'lfood.payroll.slip'

    def web_read(self, specification):
        if len(self) == 1:
            self.employee_id._lfood_log_view()
        return super().web_read(specification)


class LfoodReminder(models.Model):
    _inherit = 'lfood.reminder'

    category = fields.Selection(selection_add=[('privacy', 'Dữ liệu cá nhân')], ondelete={'privacy': 'cascade'})

    def _collect_extra(self, company, today, horizon):
        out = super()._collect_extra(company, today, horizon)
        for req in self.env['lfood.privacy.request'].sudo().search([
                ('company_id', '=', company.id), ('state', 'in', ('new', 'responded'))]):
            due = req.respond_by if req.state == 'new' else req.due_date
            what = _('Phản hồi') if req.state == 'new' else _('Thực hiện')
            out.append({'key': 'privacy-%s-%s-%s' % (req.id, req.state, due), 'category': 'privacy',
                        'title': _('%s yêu cầu dữ liệu cá nhân %s của %s') % (what, req.name, req.subject_name),
                        'due_date': due, 'res_model': req._name, 'res_id': req.id})
        return out
