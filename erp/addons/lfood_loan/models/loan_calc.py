"""Tính lãi vay theo dư nợ thực tế từng ngày, không phụ thuộc Odoo.

Dư nợ của ngày x = tổng giải ngân có ngày <= x trừ tổng gốc đã trả có ngày <= x: ngày giải ngân có tính lãi,
ngày trả gốc không tính lãi phần đã trả.
"""
from datetime import timedelta


def interest(events, rate_percent, start, end, basis=365):
    """Lãi từ start đến end (tính cả hai đầu). events: [(ngày, +giải ngân / -trả gốc)]."""
    if end < start:
        return 0
    total, day = 0.0, start
    ordered = sorted(events)
    while day <= end:
        outstanding = sum(amount for d, amount in ordered if d <= day)
        total += max(outstanding, 0) * rate_percent / 100 / basis
        day += timedelta(days=1)
    return round(total)


def equal_schedule(principal, first_due, count, months):
    """Lịch trả gốc đều: [(ngày, số tiền)]; kỳ cuối nhận phần lẻ do làm tròn."""
    from dateutil.relativedelta import relativedelta
    part = round(principal / count)
    rows = [(first_due + relativedelta(months=months * i), part) for i in range(count)]
    rows[-1] = (rows[-1][0], principal - part * (count - 1))
    return rows


def current_portion(schedule, paid, report_date):
    """Phần gốc phải trả đến ngày report_date + 1 năm, sau khi trừ số đã trả cho các kỳ sớm nhất."""
    from dateutil.relativedelta import relativedelta
    horizon = report_date + relativedelta(years=1)
    current = 0
    for due, amount in sorted(schedule):
        covered = min(paid, amount)
        paid -= covered
        if due <= horizon:
            current += amount - covered
    return current


def excess_part(amount, rate_percent, cap_percent):
    """Phần lãi vượt mức trần (không được trừ khi tính thuế TNDN)."""
    if not cap_percent or rate_percent <= cap_percent:
        return 0
    return round(amount * (rate_percent - cap_percent) / rate_percent)


if __name__ == '__main__':
    from datetime import date
    ev = [(date(2027, 1, 10), 365_000_000)]
    # 10/01 -> 31/01: 22 ngày x 365 triệu x 10% / 365 = 2.200.000
    assert interest(ev, 10, date(2027, 1, 10), date(2027, 1, 31)) == 2_200_000
    ev.append((date(2027, 2, 11), -182_500_000))
    # 01/02 -> 28/02: 10 ngày dư nợ 365 triệu (100.000/ngày) + 18 ngày dư nợ 182,5 triệu (50.000/ngày)
    assert interest(ev, 10, date(2027, 2, 1), date(2027, 2, 28)) == 1_000_000 + 900_000
    assert interest(ev, 10, date(2027, 3, 1), date(2027, 2, 28)) == 0
    sched = equal_schedule(100_000_000, date(2027, 6, 30), 3, 12)
    assert sched == [(date(2027, 6, 30), 33_333_333), (date(2028, 6, 30), 33_333_333), (date(2029, 6, 30), 33_333_334)]
    # báo cáo 31/03/2027: kỳ 30/06/2027 đến hạn trong 12 tháng
    assert current_portion(sched, 0, date(2027, 3, 31)) == 33_333_333
    # báo cáo 31/12/2027, đã trả kỳ đầu: kỳ 30/06/2028 đến hạn
    assert current_portion(sched, 33_333_333, date(2027, 12, 31)) == 33_333_333
    # quá hạn chưa trả vẫn là ngắn hạn: báo cáo 31/12/2027 chưa trả gì
    assert current_portion(sched, 0, date(2027, 12, 31)) == 66_666_666
    assert excess_part(1_200_000, 24, 20) == 200_000 and excess_part(1_000, 12, 20) == 0
    print('ok')
