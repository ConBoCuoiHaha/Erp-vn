"""Ghi nhật ký cho mọi tạo, sửa, xóa trên toàn bộ đối tượng của hệ thống.

Kế thừa 'base' nên áp dụng cho mọi model. Bỏ qua các bảng kỹ thuật tự sinh
(tài nguyên giao diện, phiên, hàng đợi) để nhật ký chỉ chứa thao tác của người dùng.
"""
from odoo import api, models

# bảng kỹ thuật không ghi (sinh tự động, không phải thao tác nghiệp vụ)
SKIP_MODELS = {
    'lfood.audit.log', 'res.users.log', 'res.users.apikeys', 'res.device', 'res.device.log',
    'bus.bus', 'bus.presence', 'ir.attachment', 'ir.logging', 'ir.cron', 'ir.cron.trigger',
    'ir.cron.progress', 'ir.model.data', 'ir.ui.view', 'ir.ui.menu', 'ir.translation',
    'ir.asset', 'ir.qweb', 'ir.profile', 'ir.module.module', 'ir.module.module.dependency',
    'ir.model', 'ir.model.fields', 'ir.model.fields.selection', 'ir.model.constraint',
    'ir.model.relation', 'ir.model.inherit', 'mail.notification', 'mail.tracking.value',
    'web_tour.tour', 'ir.sequence.date_range', 'res.users.settings', 'res.users.settings.volumes',
    'ir.default', 'ir.session', 'rpc.session',
}
# các bảng kỹ thuật NHƯNG phải ghi vì liên quan phân quyền, cấu hình
PERMISSION_MODELS = {'res.groups', 'ir.model.access', 'ir.rule', 'res.users', 'res.groups.privilege'}
CONFIG_MODELS = {'ir.config_parameter', 'res.company', 'ir.sequence', 'res.config.settings'}
SENSITIVE_FIELDS = {'password', 'new_password', 'totp_secret', 'api_key', 'signature'}
MAX_TEXT = 300


class Base(models.AbstractModel):
    _inherit = 'base'

    # ------------------------------------------------------------ có ghi không
    def _lfood_audit_enabled(self):
        ctx = self.env.context
        if ctx.get('lfood_audit_skip') or ctx.get('install_mode') or ctx.get('module'):
            return False
        name = self._name
        if name in SKIP_MODELS or self._abstract:
            return False
        if self._transient and name not in CONFIG_MODELS:
            return False
        if name.startswith(('ir.actions', 'ir.asset', 'base.module', 'base_import', 'bus.', 'web_editor')):
            return False
        return 'lfood.audit.log' in self.env

    def _lfood_audit_action(self, default):
        if self._name in PERMISSION_MODELS:
            return 'permission'
        if self._name in CONFIG_MODELS:
            return 'config'
        return default

    # ------------------------------------------------------------ đọc giá trị để so
    def _lfood_audit_value(self, fname):
        field = self._fields.get(fname)
        if not field:
            return None
        if fname in SENSITIVE_FIELDS or field.groups == 'base.group_no_one' and field.type == 'char' and 'password' in fname:
            return '(ẩn)'
        val = self[fname]
        ftype = field.type
        if ftype == 'many2one':
            return val.display_name if val else None
        if ftype in ('one2many', 'many2many'):
            names = val.mapped('display_name')
            return names[:20] + (['… %s mục' % len(names)] if len(names) > 20 else [])
        if ftype == 'binary':
            return '(tệp)' if val else None
        if ftype == 'selection':
            return dict(field._description_selection(self.env)).get(val, val) if val else None
        if ftype in ('date', 'datetime'):
            return str(val) if val else None
        if ftype in ('html', 'text', 'char', 'json'):
            s = str(val) if val else None
            return s[:MAX_TEXT] if s else None
        return val

    def _lfood_audit_fields(self, vals):
        out = []
        for fname in vals:
            field = self._fields.get(fname)
            if field and field.store and not field.compute and fname not in ('write_date', 'write_uid', '__last_update'):
                out.append(fname)
            elif field and field.type in ('one2many', 'many2many'):
                out.append(fname)
        return out

    def _lfood_audit_snapshot(self, fnames):
        return {rec.id: {f: rec._lfood_audit_value(f) for f in fnames} for rec in self.sudo()}

    def _lfood_company_id(self):
        if 'company_id' in self._fields:
            try:
                return self.sudo().company_id.id or False
            except Exception:
                return False
        return False

    # ------------------------------------------------------------ ghi đè
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if records and records._lfood_audit_enabled():
            Log = self.env['lfood.audit.log']
            for rec, vals in zip(records.sudo(), vals_list):
                fnames = rec._lfood_audit_fields(vals)
                changes = [{'field': f, 'label': rec._fields[f].string, 'old': None,
                            'new': rec._lfood_audit_value(f)} for f in fnames]
                Log._record_event(rec._lfood_audit_action('create'), model=rec._name, res_id=rec.id,
                                  res_name=rec.display_name, company_id=rec._lfood_company_id(),
                                  summary='Tạo %s: %s' % (rec._description or rec._name, rec.display_name),
                                  changes=[c for c in changes if c['new'] not in (None, False, '', [])])
        return records

    def write(self, vals):
        if not self or not self._lfood_audit_enabled():
            return super().write(vals)
        fnames = self._lfood_audit_fields(vals)
        before = self._lfood_audit_snapshot(fnames)
        res = super().write(vals)
        after = self._lfood_audit_snapshot(fnames)
        Log = self.env['lfood.audit.log']
        for rec in self.sudo():
            changes = []
            for f in fnames:
                old, new = before.get(rec.id, {}).get(f), after.get(rec.id, {}).get(f)
                if old != new:
                    changes.append({'field': f, 'label': rec._fields[f].string, 'old': old, 'new': new})
            if changes:
                Log._record_event(rec._lfood_audit_action('write'), model=rec._name, res_id=rec.id,
                                  res_name=rec.display_name, company_id=rec._lfood_company_id(),
                                  summary='Sửa %s: %s (%s)' % (rec._description or rec._name, rec.display_name,
                                                               ', '.join(c['label'] for c in changes)),
                                  changes=changes)
        return res

    def unlink(self):
        if not self or not self._lfood_audit_enabled():
            return super().unlink()
        snaps = []
        for rec in self.sudo():
            keep = [f for f, fld in rec._fields.items()
                    if fld.store and fld.type not in ('one2many', 'many2many', 'binary', 'html')
                    and f not in ('create_uid', 'write_uid', 'create_date', 'write_date', 'id')][:40]
            snaps.append((rec._name, rec.id, rec.display_name, rec._lfood_company_id(),
                          [{'field': f, 'label': rec._fields[f].string, 'old': rec._lfood_audit_value(f), 'new': None}
                           for f in keep if rec._lfood_audit_value(f) not in (None, False, '')],
                          rec._description, rec._lfood_audit_action('unlink')))
        res = super().unlink()
        Log = self.env['lfood.audit.log']
        for model, rid, name, cid, changes, desc, action in snaps:
            Log._record_event(action, model=model, res_id=rid, res_name=name, company_id=cid,
                              summary='Xóa %s: %s' % (desc or model, name), changes=changes)
        return res
