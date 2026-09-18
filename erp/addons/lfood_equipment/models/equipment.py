"""Bảo trì thiết bị (TS11) và quản lý đội xe (TS12).

Thiết bị: chu kỳ bảo trì định kỳ (ngày), ngày bảo trì gần nhất, ngày đến hạn; phiếu bảo trì, sửa chữa ghi thời gian
dừng máy và chi phí (chi phí hạch toán bằng chứng từ mua dịch vụ hoặc phiếu chi, ở đây theo dõi quản trị).
Đội xe: biển số, vùng hoạt động, hạn giấy chứng nhận kiểm định (đăng kiểm) và hạn bảo hiểm bắt buộc trách nhiệm dân sự
nhập theo giấy tờ thực tế (chu kỳ kiểm định khác nhau theo loại xe, năm sản xuất nên app không tự tính);
nhật ký nhiên liệu tính mức tiêu hao lít/100 km so với định mức; chành xe (đơn vị vận chuyển thuê ngoài) theo vùng
và chi phí từng chuyến. Nhắc bảo trì, đăng kiểm, bảo hiểm sắp đến hạn.
"""
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd

REGIONS = [('north', 'Miền Bắc'), ('central', 'Miền Trung'), ('south', 'Miền Nam'), ('all', 'Toàn quốc')]


class LfoodEquipment(models.Model):
    _name = 'lfood.equipment'
    _description = 'Thiết bị cần bảo trì'
    _order = 'name'

    name = fields.Char('Thiết bị', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    asset_id = fields.Many2one('lfood.asset', 'Thẻ tài sản')
    location = fields.Char('Vị trí, dây chuyền')
    interval_days = fields.Integer('Chu kỳ bảo trì (ngày)', default=90)
    last_date = fields.Date('Bảo trì định kỳ gần nhất', compute='_compute_dates', store=True)
    next_date = fields.Date('Đến hạn bảo trì', compute='_compute_dates', store=True)
    start_date = fields.Date('Bắt đầu theo dõi', default=fields.Date.context_today)
    maintenance_ids = fields.One2many('lfood.maintenance', 'equipment_id', 'Phiếu bảo trì, sửa chữa')
    downtime_hours = fields.Float('Tổng giờ dừng máy', compute='_compute_totals')
    cost_total = fields.Float('Tổng chi phí', digits=(16, 0), compute='_compute_totals')
    active = fields.Boolean(default=True)

    @api.depends('interval_days', 'start_date', 'maintenance_ids.date', 'maintenance_ids.kind', 'maintenance_ids.state')
    def _compute_dates(self):
        for rec in self:
            done = rec.maintenance_ids.filtered(lambda m: m.kind == 'preventive' and m.state == 'done')
            rec.last_date = max(done.mapped('date')) if done else False
            base = rec.last_date or rec.start_date
            rec.next_date = base + timedelta(days=rec.interval_days) if base and rec.interval_days else False

    def _compute_totals(self):
        for rec in self:
            done = rec.maintenance_ids.filtered(lambda m: m.state == 'done')
            rec.downtime_hours = sum(done.mapped('downtime_hours'))
            rec.cost_total = sum(done.mapped('cost'))


class LfoodMaintenance(models.Model):
    _name = 'lfood.maintenance'
    _description = 'Phiếu bảo trì, sửa chữa'
    _order = 'date desc, id desc'

    equipment_id = fields.Many2one('lfood.equipment', 'Thiết bị', index=True)
    vehicle_id = fields.Many2one('lfood.vehicle', 'Xe', index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    kind = fields.Selection([('preventive', 'Bảo trì, bảo dưỡng định kỳ'), ('repair', 'Sửa chữa hỏng hóc')], 'Loại',
                            required=True, default='preventive')
    date = fields.Date('Ngày', required=True, default=fields.Date.context_today)
    description = fields.Text('Nội dung', required=True)
    vendor_id = fields.Many2one('res.partner', 'Đơn vị thực hiện')
    downtime_hours = fields.Float('Giờ dừng máy, dừng xe')
    cost = fields.Float('Chi phí', digits=(16, 0))
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục chi phí')
    odometer = fields.Float('Số km lúc bảo dưỡng')
    state = fields.Selection([('draft', 'Nháp'), ('done', 'Hoàn thành')], 'Trạng thái', default='draft', required=True)

    @api.constrains('equipment_id', 'vehicle_id', 'downtime_hours', 'cost', 'description')
    def _check_target(self):
        for rec in self:
            if bool(rec.equipment_id) == bool(rec.vehicle_id):
                raise ValidationError(_('Chọn thiết bị hoặc xe (một trong hai).'))
            if rec.downtime_hours < 0 or rec.cost < 0:
                raise ValidationError(_('Giờ dừng và chi phí không âm.'))

    def action_done(self):
        self.filtered(lambda m: m.state == 'draft').write({'state': 'done'})
        return True


class LfoodVehicle(models.Model):
    _name = 'lfood.vehicle'
    _description = 'Xe'
    _order = 'plate'

    plate = fields.Char('Biển số', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    model = fields.Char('Loại xe')
    asset_id = fields.Many2one('lfood.asset', 'Thẻ tài sản')
    region = fields.Selection(REGIONS, 'Vùng hoạt động', default='south')
    driver = fields.Char('Lái xe phụ trách')
    registration_expiry = fields.Date('Hạn kiểm định (đăng kiểm)')
    insurance_expiry = fields.Date('Hạn bảo hiểm bắt buộc trách nhiệm dân sự')
    body_insurance_expiry = fields.Date('Hạn bảo hiểm vật chất xe')
    fuel_norm = fields.Float('Định mức nhiên liệu (lít/100 km)')
    service_km = fields.Float('Bảo dưỡng mỗi (km)', default=10000)
    fuel_ids = fields.One2many('lfood.fuel.log', 'vehicle_id', 'Nhiên liệu')
    maintenance_ids = fields.One2many('lfood.maintenance', 'vehicle_id', 'Bảo dưỡng, sửa chữa')
    odometer = fields.Float('Số km hiện tại', compute='_compute_odometer')
    next_service_km = fields.Float('Bảo dưỡng tiếp ở km', compute='_compute_odometer')
    active = fields.Boolean(default=True)

    _plate_uniq = models.Constraint('unique(plate)', 'Biển số đã có.')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s %s' % (rec.plate, rec.model or '')

    def _compute_odometer(self):
        for rec in self:
            readings = rec.fuel_ids.mapped('odometer') + rec.maintenance_ids.mapped('odometer')
            rec.odometer = max(readings) if readings else 0
            last = rec.maintenance_ids.filtered(lambda m: m.kind == 'preventive' and m.state == 'done' and m.odometer)
            base = max(last.mapped('odometer')) if last else 0
            rec.next_service_km = base + rec.service_km if rec.service_km else 0


class LfoodFuelLog(models.Model):
    _name = 'lfood.fuel.log'
    _description = 'Đổ nhiên liệu'
    _order = 'vehicle_id, odometer'

    vehicle_id = fields.Many2one('lfood.vehicle', 'Xe', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(related='vehicle_id.company_id', store=True)
    date = fields.Date('Ngày', required=True, default=fields.Date.context_today)
    liters = fields.Float('Số lít', required=True)
    amount = fields.Float('Số tiền', digits=(16, 0))
    odometer = fields.Float('Số km khi đổ', required=True)
    full_tank = fields.Boolean('Đổ đầy bình', default=True)
    consumption = fields.Float('Tiêu hao (lít/100 km)', compute='_compute_consumption', store=True,
                               help='Tính giữa hai lần đổ đầy: số lít lần này chia quãng đường từ lần đổ đầy trước')
    over_norm = fields.Boolean('Vượt định mức', compute='_compute_consumption', store=True)

    @api.depends('liters', 'odometer', 'full_tank', 'vehicle_id.fuel_norm')
    def _compute_consumption(self):
        for rec in self:
            rec.consumption, rec.over_norm = 0, False
            if not rec.full_tank or not rec.vehicle_id:
                continue
            prev = self.search([('vehicle_id', '=', rec.vehicle_id.id), ('full_tank', '=', True),
                                ('odometer', '<', rec.odometer), ('id', '!=', rec.id)], order='odometer desc', limit=1)
            if not prev:
                continue
            between = self.search([('vehicle_id', '=', rec.vehicle_id.id), ('odometer', '>', prev.odometer),
                                   ('odometer', '<', rec.odometer), ('id', '!=', rec.id)])
            km = rec.odometer - prev.odometer
            liters = rec.liters + sum(between.mapped('liters'))
            rec.consumption = round(liters * 100 / km, 2) if km else 0
            norm = rec.vehicle_id.fuel_norm
            rec.over_norm = bool(norm and rec.consumption > norm * 1.1)

    @api.constrains('odometer', 'liters')
    def _check_values(self):
        for rec in self:
            if rec.liters <= 0:
                raise ValidationError(_('Số lít phải lớn hơn 0.'))
            later = self.search_count([('vehicle_id', '=', rec.vehicle_id.id), ('date', '<', rec.date),
                                       ('odometer', '>', rec.odometer)])
            if later:
                raise ValidationError(_('Số km %s nhỏ hơn số km của lần đổ trước.') % ('%g' % rec.odometer))


class LfoodCarrier(models.Model):
    _name = 'lfood.carrier'
    _description = 'Chành xe, đơn vị vận chuyển thuê ngoài'
    _order = 'region, name'

    partner_id = fields.Many2one('res.partner', 'Đơn vị vận chuyển', required=True)
    name = fields.Char(related='partner_id.name', store=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    region = fields.Selection(REGIONS, 'Vùng', required=True)
    route = fields.Char('Tuyến')
    rate_per_kg = fields.Float('Cước tham chiếu (đồng/kg)', digits=(16, 0))
    freight_ids = fields.One2many('lfood.freight.log', 'carrier_id', 'Chuyến hàng')
    active = fields.Boolean(default=True)


class LfoodFreightLog(models.Model):
    _name = 'lfood.freight.log'
    _description = 'Chuyến hàng gửi chành'
    _order = 'date desc'

    carrier_id = fields.Many2one('lfood.carrier', 'Chành xe', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(related='carrier_id.company_id', store=True)
    region = fields.Selection(related='carrier_id.region', store=True)
    date = fields.Date('Ngày gửi', required=True, default=fields.Date.context_today)
    destination = fields.Char('Nơi nhận')
    weight = fields.Float('Khối lượng (kg)')
    cost = fields.Float('Cước', digits=(16, 0))
    reference = fields.Char('Số phiếu gửi, hóa đơn')
    cost_per_kg = fields.Float('Cước/kg', compute='_compute_rate', store=True)
    above_rate = fields.Boolean('Cao hơn cước tham chiếu', compute='_compute_rate', store=True)

    @api.depends('weight', 'cost', 'carrier_id.rate_per_kg')
    def _compute_rate(self):
        for rec in self:
            rec.cost_per_kg = round(rec.cost / rec.weight) if rec.weight else 0
            ref = rec.carrier_id.rate_per_kg
            rec.above_rate = bool(ref and rec.cost_per_kg > ref)


class LfoodReminder(models.Model):
    _inherit = 'lfood.reminder'

    category = fields.Selection(selection_add=[('equipment', 'Thiết bị, xe')], ondelete={'equipment': 'cascade'})

    def _collect_extra(self, company, today, horizon):
        out = super()._collect_extra(company, today, horizon)
        for eq in self.env['lfood.equipment'].sudo().search([
                ('company_id', '=', company.id), ('next_date', '!=', False), ('next_date', '<=', horizon)]):
            out.append({'key': 'maint-%s-%s' % (eq.id, eq.next_date), 'category': 'equipment',
                        'title': _('Bảo trì định kỳ %s') % eq.name, 'due_date': eq.next_date,
                        'res_model': eq._name, 'res_id': eq.id})
        labels = {'registration_expiry': _('Hết hạn kiểm định (đăng kiểm) xe %s'),
                  'insurance_expiry': _('Hết hạn bảo hiểm bắt buộc trách nhiệm dân sự xe %s'),
                  'body_insurance_expiry': _('Hết hạn bảo hiểm vật chất xe %s')}
        for v in self.env['lfood.vehicle'].sudo().search([('company_id', '=', company.id)]):
            for field, title in labels.items():
                d = v[field]
                if d and d <= horizon:
                    out.append({'key': 'veh-%s-%s-%s' % (field, v.id, d), 'category': 'equipment',
                                'title': title % v.plate, 'due_date': d, 'res_model': v._name, 'res_id': v.id})
        return out
