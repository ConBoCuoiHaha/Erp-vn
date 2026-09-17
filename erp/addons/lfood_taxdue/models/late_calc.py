"""Tiền chậm nộp thuế, không phụ thuộc Odoo.

Luật Quản lý thuế 108/2025/QH15 và Nghị định 252/2026/NĐ-CP: mức 0,03%/ngày trên số tiền thuế chậm nộp, tính liên tục
từ ngày tiếp theo ngày hết hạn nộp đến ngày liền kề trước ngày nộp tiền vào ngân sách.
"""


def late_days(due, paid_on):
    """Số ngày tính tiền chậm nộp khi nộp vào ngày paid_on."""
    return max((paid_on - due).days - 1, 0)


def late_interest(amount, due, payments, as_of, rate_percent):
    """Tiền chậm nộp đến ngày as_of.

    payments: [(ngày nộp, số tiền)]; mỗi lần nộp trả cho phần nợ còn lại. Phần chưa nộp coi như nộp vào as_of.
    Trả về (tiền chậm nộp, [(số tiền, số ngày, tiền chậm nộp)]).
    """
    remaining, detail = amount, []
    for day, paid in sorted(payments):
        if remaining <= 0:
            break
        part = min(paid, remaining)
        detail.append((part, late_days(due, day)))
        remaining -= part
    if remaining > 0:
        detail.append((remaining, late_days(due, as_of)))
    rows = [(part, days, round(part * days * rate_percent / 100)) for part, days in detail]
    return sum(r[2] for r in rows), rows


if __name__ == '__main__':
    from datetime import date
    # hạn 20/7, nộp 25/7: tính từ 21/7 đến 24/7 = 4 ngày
    assert late_days(date(2026, 7, 20), date(2026, 7, 25)) == 4
    assert late_days(date(2026, 7, 20), date(2026, 7, 21)) == 0
    assert late_days(date(2026, 7, 20), date(2026, 7, 10)) == 0
    total, rows = late_interest(100_000_000, date(2026, 7, 20),
                                [(date(2026, 7, 20), 40_000_000), (date(2026, 7, 31), 60_000_000)],
                                date(2026, 8, 31), 0.03)
    assert rows == [(40_000_000, 0, 0), (60_000_000, 10, 180_000)] and total == 180_000
    total, _ = late_interest(10_000_000, date(2026, 7, 20), [], date(2026, 7, 31), 0.03)
    assert total == 30_000  # 10 ngày x 0,03% x 10 triệu
    print('ok')
