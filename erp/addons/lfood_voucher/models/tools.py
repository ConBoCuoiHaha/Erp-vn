"""Hàm tính toán dùng chung."""
import math


def allocate(total, weights):
    """Chia `total` (số nguyên đồng) theo tỷ trọng `weights`.

    Dùng phương pháp số dư lớn nhất: tổng các phần luôn bằng đúng `total`,
    không lệch đồng nào do làm tròn. Trọng số toàn 0 thì chia đều.
    """
    n = len(weights)
    if not n:
        return []
    total = int(round(total))
    sign = -1 if total < 0 else 1
    total = abs(total)
    w = [max(0.0, float(x or 0)) for x in weights]
    s = sum(w)
    if s <= 0:
        w, s = [1.0] * n, float(n)
    raw = [total * x / s for x in w]
    out = [math.floor(x) for x in raw]
    rem = total - sum(out)
    order = sorted(range(n), key=lambda i: (-(raw[i] - math.floor(raw[i])), i))
    k = 0
    while rem > 0:
        out[order[k % n]] += 1
        rem -= 1
        k += 1
    return [sign * x for x in out]


def vnd(value):
    """Định dạng số tiền kiểu Việt Nam: 1.234.567"""
    return '{:,.0f}'.format(value or 0).replace(',', '.')


def num(value):
    """Số tham số: 2530000 -> 2.530.000, 10.5 -> 10,5."""
    whole, _, frac = ('%.4f' % value).rstrip('0').rstrip('.').partition('.')
    return '{:,}'.format(int(whole)).replace(',', '.') + (',' + frac if frac else '')
