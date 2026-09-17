"""Lịch khấu hao đường thẳng theo ngày (Thông tư 45/2013/TT-BTC, sửa đổi bởi Thông tư 30/2025/TT-BTC):
trích từ ngày tài sản tăng, thôi trích từ ngày tài sản giảm; tháng đầu tính theo số ngày sử dụng,
tháng cuối nhận phần còn lại để tổng khấu hao bằng đúng giá trị phải khấu hao."""
import calendar
from datetime import date


def month_end(d):
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def next_month_end(d):
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return month_end(date(y, m, 1))


def monthly_amount(depreciable, life_months):
    return round(depreciable / life_months) if life_months > 0 else 0


def build_schedule(depreciable, life_months, start):
    """[(ngày cuối tháng, số khấu hao)]; tổng luôn bằng `depreciable`."""
    depreciable = int(round(depreciable))
    if depreciable <= 0 or life_months <= 0 or not start:
        return []
    monthly = monthly_amount(depreciable, life_months)
    days = calendar.monthrange(start.year, start.month)[1]
    amount = round(monthly * (days - start.day + 1) / days)
    out, remaining, period = [], depreciable, month_end(start)
    while remaining > 0:
        amount = min(max(amount, 1), remaining)
        out.append((period, amount))
        remaining -= amount
        period = next_month_end(period)
        amount = monthly
    return out


def prorate_until(monthly, dispose_date):
    """Khấu hao tháng giảm tài sản: tính tới ngày trước ngày giảm."""
    days = calendar.monthrange(dispose_date.year, dispose_date.month)[1]
    return round(monthly * (dispose_date.day - 1) / days)


if __name__ == '__main__':
    # 1 tỷ, 5 năm, bắt đầu 16/9/2026: tháng 9 có 30 ngày, dùng 15 ngày
    s = build_schedule(1_000_000_000, 60, date(2026, 9, 16))
    assert s[0] == (date(2026, 9, 30), 8_333_334), s[0]
    assert s[1] == (date(2026, 10, 31), 16_666_667), s[1]
    assert sum(a for _, a in s) == 1_000_000_000
    assert len(s) == 61 and s[-1][0] == date(2031, 9, 30), (len(s), s[-1])
    s = build_schedule(120_000_000, 12, date(2026, 1, 1))
    assert len(s) == 12 and all(a == 10_000_000 for _, a in s)
    assert prorate_until(10_000_000, date(2026, 6, 16)) == 5_000_000
    print('ok')
