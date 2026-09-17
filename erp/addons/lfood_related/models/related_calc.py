"""Khống chế chi phí lãi vay theo khoản 3 Điều 16 Nghị định 255/2026/NĐ-CP, không phụ thuộc Odoo.

Chi phí lãi vay thuần (sau khi trừ lãi tiền gửi, lãi cho vay) được trừ không vượt quá 30% của
(lợi nhuận thuần từ hoạt động kinh doanh + chi phí lãi vay thuần + chi phí khấu hao). Phần vượt được chuyển sang
kỳ sau khi chi phí lãi vay thuần của kỳ đó thấp hơn mức khống chế, liên tục không quá 5 năm.
"""


def interest_cap(op_profit, net_interest, depreciation, rate_percent):
    """(mức khống chế, phần vượt không được trừ, khoảng trống còn lại để trừ phần chuyển từ kỳ trước)."""
    ebitda = op_profit + net_interest + depreciation
    cap = max(round(ebitda * rate_percent / 100), 0)
    excess = max(round(net_interest) - cap, 0)
    room = max(cap - round(net_interest), 0)
    return cap, excess, room


def carry_pool(prior, year, years):
    """prior: [(năm, phần vượt, phần chuyển đã dùng ở năm đó)] các năm trước, theo thứ tự năm.
    Phần đã dùng mỗi năm trừ vào phần vượt cũ nhất còn hạn. Trả về [(năm phát sinh, số còn được chuyển)] cho `year`."""
    pool = []
    for y, excess, used in sorted(prior):
        pool = [[py, amt] for py, amt in pool if y - py <= years]
        for item in pool:
            take = min(item[1], used)
            item[1] -= take
            used -= take
        pool.append([y, excess])
    return [(py, amt) for py, amt in pool if 0 < year - py <= years and amt > 0]


def tp_exemption(parties, own_rate, own_incentive, revenue, related_total, apa, net_revenue, margin_profit,
                 sector, limits):
    """Đánh giá miễn kê khai, miễn lập hồ sơ xác định giá (Nghị định 255/2026/NĐ-CP).

    parties: [(tên, là đối tượng nộp thuế TNDN tại Việt Nam, thuế suất, được ưu đãi)]
    limits: dict revenue_small, related_small, revenue_margin, margin_<sector>
    Trả về (trạng thái, [lý do]) với trạng thái: 'none' không có giao dịch liên kết, 'full' miễn kê khai và miễn lập hồ sơ,
    'doc' phải kê khai nhưng miễn lập hồ sơ, 'required' phải kê khai và lập hồ sơ.
    """
    if not parties:
        return 'none', ['Không có giao dịch với bên liên kết']
    domestic_same = not own_incentive and all(dom and rate == own_rate and not inc for _n, dom, rate, inc in parties)
    if domestic_same:
        return 'full', ['Chỉ giao dịch với bên liên kết nộp thuế TNDN tại Việt Nam, cùng thuế suất %g%%, '
                        'không bên nào được ưu đãi' % own_rate]
    reasons = ['Không thuộc trường hợp miễn kê khai: ' + ', '.join(
        n for n, dom, rate, inc in parties if not dom or rate != own_rate or inc) if not own_incentive
        else 'Không thuộc trường hợp miễn kê khai: doanh nghiệp đang được ưu đãi thuế TNDN']
    if revenue < limits['revenue_small'] and related_total < limits['related_small']:
        return 'doc', reasons + ['Doanh thu %s dưới %s và giao dịch liên kết %s dưới %s' % (
            _m(revenue), _m(limits['revenue_small']), _m(related_total), _m(limits['related_small']))]
    if apa:
        return 'doc', reasons + ['Đã có thỏa thuận trước về phương pháp xác định giá tính thuế (APA)']
    margin = round(margin_profit / net_revenue * 100, 2) if net_revenue > 0 else None
    need = limits.get('margin_' + (sector or ''))
    if revenue < limits['revenue_margin'] and need is not None and margin is not None and margin >= need:
        return 'doc', reasons + ['Doanh thu dưới %s, tỷ suất lợi nhuận thuần trước lãi vay và thuế %s%% đạt mức %s%%' % (
            _m(limits['revenue_margin']), margin, '%g' % need)]
    reasons.append('Không đạt điều kiện miễn lập hồ sơ: doanh thu %s, giao dịch liên kết %s, tỷ suất %s' % (
        _m(revenue), _m(related_total), '%s%%' % margin if margin is not None else 'không xác định'))
    return 'required', reasons


def _m(amount):
    return '{:,.0f}'.format(amount).replace(',', '.')


if __name__ == '__main__':
    L = {'revenue_small': 50e9, 'related_small': 30e9, 'revenue_margin': 500e9,
         'margin_distribution': 5, 'margin_manufacturing': 10, 'margin_processing': 15}
    vn = [('Văn phòng', True, 20, False)]
    assert tp_exemption([], 20, False, 1e9, 0, False, 1e9, 0, 'manufacturing', L)[0] == 'none'
    assert tp_exemption(vn, 20, False, 900e9, 100e9, False, 900e9, 0, 'manufacturing', L)[0] == 'full'
    person = [('Cá nhân', False, 0, False)]
    assert tp_exemption(person, 20, False, 40e9, 1e9, False, 40e9, 0, 'manufacturing', L)[0] == 'doc'
    assert tp_exemption(person, 20, False, 400e9, 40e9, False, 400e9, 44e9, 'manufacturing', L)[0] == 'doc'
    assert tp_exemption(person, 20, False, 400e9, 40e9, False, 400e9, 30e9, 'manufacturing', L)[0] == 'required'
    assert tp_exemption(person, 20, False, 400e9, 40e9, True, 400e9, 0, 'manufacturing', L)[0] == 'doc'
    assert tp_exemption(vn, 20, True, 900e9, 100e9, False, 900e9, 0, 'manufacturing', L)[0] == 'required'

    # EBITDA 1.000 -> mức khống chế 300; lãi thuần 400 thì vượt 100
    assert interest_cap(500, 400, 100, 30) == (300, 100, 0)
    assert interest_cap(900, 50, 50, 30) == (300, 0, 250)
    assert interest_cap(-2000, 100, 100, 30) == (0, 100, 0)
    # vượt 100 năm 2026, năm 2027 dùng 30 -> năm 2028 còn 70
    assert carry_pool([(2026, 100, 0), (2027, 0, 30)], 2028, 5) == [(2026, 70)]
    # quá 5 năm thì mất
    assert carry_pool([(2026, 100, 0)], 2032, 5) == []
    assert carry_pool([(2026, 100, 0)], 2031, 5) == [(2026, 100)]
    print('ok')
