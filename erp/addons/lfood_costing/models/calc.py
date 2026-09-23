"""Công thức tính giá thành giản đơn (trực tiếp), đánh giá dở dang theo sản lượng hoàn thành tương đương.

Quy ước:
- Chi phí nguyên vật liệu trực tiếp (621) bỏ vào ngay từ đầu quy trình nên dở dang chịu đủ theo số lượng thực tế.
- Chi phí chế biến (622 nhân công trực tiếp + 627 sản xuất chung) chịu theo sản lượng tương đương:
  số lượng dở dang nhân mức độ hoàn thành.

Chạy trực tiếp tệp này để tự kiểm: python calc.py
"""


def wip_end(open_dm, cost_dm, open_conv, cost_conv, qty_done, qty_wip, pct):
    """Trả (dở dang cuối kỳ phần nguyên vật liệu, phần chế biến)."""
    total_qty = qty_done + qty_wip
    dm = (open_dm + cost_dm) * qty_wip / total_qty if total_qty else 0
    eq = qty_wip * pct / 100.0
    conv = (open_conv + cost_conv) * eq / (qty_done + eq) if qty_done + eq else 0
    return round(dm), round(conv)


def unit_cost(open_dm, cost_dm, open_conv, cost_conv, qty_done, qty_wip, pct):
    """Trả (tổng giá thành, giá thành đơn vị, dở dang cuối kỳ nguyên vật liệu, dở dang cuối kỳ chế biến)."""
    dm_end, conv_end = wip_end(open_dm, cost_dm, open_conv, cost_conv, qty_done, qty_wip, pct)
    total = (open_dm + cost_dm - dm_end) + (open_conv + cost_conv - conv_end)
    return round(total), (round(total / qty_done) if qty_done else 0), dm_end, conv_end


def allocate(pool, weights):
    """Phân bổ chi phí chung theo tiêu thức, khớp tới đồng: phần dư dồn vào đối tượng có tiêu thức lớn nhất."""
    total = sum(weights.values())
    if not pool or not total:
        return {k: 0 for k in weights}
    out = {k: int(pool * w / total) for k, w in weights.items()}
    diff = round(pool) - sum(out.values())
    if diff:
        out[max(weights, key=lambda k: weights[k])] += diff
    return out


if __name__ == '__main__':
    # dở dang cuối kỳ: nguyên vật liệu chia theo số lượng, chế biến chia theo sản lượng tương đương
    dm, conv = wip_end(0, 900, 0, 300, qty_done=800, qty_wip=200, pct=50)
    assert (dm, conv) == (180, 33), (dm, conv)          # 900*200/1000 = 180; 300*100/900 = 33,33
    total, unit, dm_end, conv_end = unit_cost(100, 900, 50, 250, 800, 200, 50)
    assert total == (100 + 900 - dm_end) + (50 + 250 - conv_end) and unit == round(total / 800)
    # dở dang 0 thì toàn bộ chi phí vào thành phẩm
    assert unit_cost(0, 800, 0, 200, 100, 0, 50) == (1000, 10, 0, 0)
    # phân bổ khớp tới đồng
    a = allocate(1000, {'A': 1, 'B': 2})
    assert a == {'A': 333, 'B': 667} and sum(a.values()) == 1000, a
    assert allocate(0, {'A': 1}) == {'A': 0} and allocate(500, {'A': 0, 'B': 0}) == {'A': 0, 'B': 0}
    print('calc.py: cac phep tinh gia thanh dat')
