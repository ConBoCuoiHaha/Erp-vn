def post_init_payroll(env):
    """Ghi rõ căn cứ giảm trừ gia cảnh: Nghị quyết 110/2025/UBTVQH15 (theo nguồn đã đối chiếu)."""
    ref = 'Nghị quyết 110/2025/UBTVQH15; Luật Thuế TNCN 109/2025/QH15'
    for xmlid in ('lfood_voucher.pv_pit_self', 'lfood_voucher.pv_pit_dep'):
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec:
            rec.with_context(lfood_audit_skip=True).legal_ref = ref
