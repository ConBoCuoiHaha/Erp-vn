"""Tính bảo hiểm và thuế thu nhập cá nhân trên phiếu lương tháng.

Căn cứ (đã đối chiếu nguyên văn trước khi viết):
- Luật Bảo hiểm xã hội 41/2024/QH15: Điều 33 (người lao động 8% quỹ hưu trí và tử tuất), Điều 34 (doanh nghiệp 3% ốm đau
  và thai sản, 14% hưu trí và tử tuất); tiền lương làm căn cứ đóng tối đa 20 lần mức tham chiếu.
- Nghị định 158/2025/NĐ-CP: quỹ tai nạn lao động, bệnh nghề nghiệp 0,5% (0,3% nếu đủ điều kiện).
- Nghị định 188/2025/NĐ-CP, Điều 6: BHYT 4,5% tiền lương làm căn cứ đóng BHXH bắt buộc, doanh nghiệp 2/3, người lao động 1/3.
- Luật Việc làm 74/2025/QH15: Điều 33 (BHTN người lao động, doanh nghiệp mỗi bên tối đa 1%; không hưởng lương từ 14 ngày làm
  việc trở lên trong tháng thì không đóng BHTN tháng đó), Điều 34 (căn cứ đóng tối đa 20 lần lương tối thiểu vùng).
- Luật Công đoàn 50/2024/QH15, Điều 29: kinh phí công đoàn 2% quỹ tiền lương làm căn cứ đóng BHXH.
- Luật Thuế thu nhập cá nhân 109/2025/QH15, Điều 9: biểu thuế lũy tiến 5 bậc; Nghị quyết 110/2025/UBTVQH15: giảm trừ gia cảnh.
Mọi con số lấy từ Tham số pháp lý theo ngày, hàm này chỉ nhận số."""


def pit_progressive(taxable, brackets):
    """brackets: [(ngưỡng trên của bậc hoặc None, thuế suất %)] theo tháng."""
    tax, lower = 0.0, 0.0
    for upper, rate in brackets:
        if taxable <= lower:
            break
        part = (min(taxable, upper) if upper is not None else taxable) - lower
        tax += part * rate / 100
        if upper is None:
            break
        lower = upper
    return round(tax)


def compute_slip(p):
    """p: dict các đầu vào; trả về dict kết quả làm tròn tới đồng."""
    r = {}
    base = p['insurance_salary']
    enrolled = p['insurance_enrolled'] and not p.get('skip_insurance')
    # tiền lương đóng không thấp hơn lương tối thiểu vùng, không cao hơn mức trần
    si_base = min(max(base, p['min_wage']), p['cap_multiplier_si'] * p['reference_wage']) if enrolled else 0
    ui_enrolled = enrolled and p['unemployment_enrolled'] and p.get('unpaid_days', 0) < 14
    ui_base = min(max(base, p['min_wage']), p['cap_multiplier_ui'] * p['min_wage']) if ui_enrolled else 0
    rt = p['rates']
    r['si_base'], r['ui_base'] = round(si_base), round(ui_base)
    r['emp_si'] = round(si_base * rt['emp_si'] / 100)
    r['emp_hi'] = round(si_base * rt['emp_hi'] / 100)
    r['emp_ui'] = round(ui_base * rt['emp_ui'] / 100)
    r['co_si'] = round(si_base * (rt['co_sickness'] + rt['co_retirement'] + rt['co_accident']) / 100)
    r['co_hi'] = round(si_base * rt['co_hi'] / 100)
    r['co_ui'] = round(ui_base * rt['co_ui'] / 100)
    r['co_union'] = round(si_base * rt['union'] / 100)
    r['emp_insurance'] = r['emp_si'] + r['emp_hi'] + r['emp_ui']
    r['gross'] = round(p['gross'])
    r['taxable_income'] = round(p['taxable_gross'])
    r['family_deduction'] = round(p['self_deduction'] + p['dependents'] * p['dependent_deduction'])
    r['assessable'] = max(0, r['taxable_income'] - r['emp_insurance'] - r['family_deduction'])
    r['pit'] = pit_progressive(r['assessable'], p['brackets']) if p['resident'] else 0
    r['other_deductions'] = round(p.get('other_deductions', 0))
    r['net'] = r['gross'] - r['emp_insurance'] - r['pit'] - r['other_deductions']
    return r


if __name__ == '__main__':
    brackets = [(10e6, 5), (30e6, 10), (60e6, 20), (100e6, 30), (None, 35)]
    rates = {'emp_si': 8, 'emp_hi': 1.5, 'emp_ui': 1, 'co_sickness': 3, 'co_retirement': 14, 'co_accident': 0.5,
             'co_hi': 3, 'co_ui': 1, 'union': 2}
    base_input = dict(insurance_salary=40e6, insurance_enrolled=True, unemployment_enrolled=True, min_wage=5.31e6,
                      cap_multiplier_si=20, cap_multiplier_ui=20, reference_wage=2.53e6, rates=rates, gross=40e6, taxable_gross=40e6,
                      self_deduction=15.5e6, dependent_deduction=6.2e6, dependents=1, brackets=brackets, resident=True)
    r = compute_slip(base_input)
    # 40 triệu: BH người lao động 4.200.000; thu nhập tính thuế 40 - 4,2 - 15,5 - 6,2 = 14,1 triệu
    # thuế = 10 triệu x 5% + 4,1 triệu x 10% = 910.000
    assert (r['emp_insurance'], r['assessable'], r['pit'], r['net']) == (4_200_000, 14_100_000, 910_000, 34_890_000), r
    assert (r['co_si'], r['co_hi'], r['co_ui'], r['co_union']) == (7_000_000, 1_200_000, 400_000, 800_000), r
    # lương 80 triệu (tháng 7/2026): BHXH, BHYT tính trên trần 50,6 triệu; BHTN trần 106,2 triệu nên tính trên 80 triệu
    r = compute_slip(dict(base_input, insurance_salary=80e6, gross=80e6, taxable_gross=80e6, dependents=0))
    assert r['si_base'] == 50_600_000 and r['ui_base'] == 80_000_000, r
    assert r['emp_si'] == 4_048_000 and r['emp_hi'] == 759_000 and r['emp_ui'] == 800_000, r
    # thu nhập tính thuế 80 - 5,607 - 15,5 = 58,893 triệu: 0,5 + 2 + 28,893 x 20% = 8.278.600
    assert r['assessable'] == 58_893_000 and r['pit'] == 8_278_600, r
    # lương thấp hơn lương tối thiểu vùng: đóng trên lương tối thiểu vùng; nghỉ không lương 14 ngày: không đóng BHTN
    r = compute_slip(dict(base_input, insurance_salary=4e6, gross=4e6, taxable_gross=4e6, unpaid_days=14))
    assert r['si_base'] == 5_310_000 and r['ui_base'] == 0 and r['pit'] == 0, r
    print('ok')
