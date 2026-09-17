"""Tính dự phòng nợ phải thu khó đòi và dự phòng giảm giá hàng tồn kho.

Căn cứ (đã tra trước khi viết): Thông tư 48/2019/TT-BTC.
- Điều 6: nợ phải thu quá hạn trích 30% nếu quá hạn từ 6 tháng đến dưới 1 năm, 50% nếu từ 1 năm đến
  dưới 2 năm, 70% nếu từ 2 năm đến dưới 3 năm, 100% nếu từ 3 năm trở lên. Chênh lệch tăng giảm so với
  số đã trích ghi vào chi phí quản lý doanh nghiệp.
- Điều 4: mức trích dự phòng giảm giá hàng tồn kho = lượng hàng tồn kho thực tế tại thời điểm lập báo
  cáo tài chính năm nhân với phần chênh lệch giá gốc trên sổ kế toán cao hơn giá trị thuần có thể thực
  hiện được. Chênh lệch tăng thì trích thêm vào giá vốn hàng bán, giảm thì hoàn nhập ghi giảm giá vốn.
Trích lập tại thời điểm lập báo cáo tài chính năm. Mọi tỷ lệ và mốc tháng là tham số pháp lý.
"""

# (số tháng quá hạn tối thiểu, tỷ lệ %) theo Điều 6 Thông tư 48/2019/TT-BTC
DEFAULT_BRACKETS = [(6, 30), (12, 50), (24, 70), (36, 100)]


def months_overdue(due_date, at_date):
    """Số tháng tròn kể từ ngày đến hạn tới ngày lập dự phòng; chưa tới hạn trả về 0."""
    if not due_date or not at_date or at_date <= due_date:
        return 0
    months = (at_date.year - due_date.year) * 12 + at_date.month - due_date.month
    if at_date.day < due_date.day:
        months -= 1
    return max(0, months)


def receivable_rate(months, brackets=None):
    """Tỷ lệ trích lập theo số tháng quá hạn; dưới mốc nhỏ nhất thì không trích."""
    rate = 0
    for min_months, value in sorted(brackets or DEFAULT_BRACKETS):
        if months >= min_months:
            rate = value
    return rate


def receivable_provision(amount, months, brackets=None):
    """Số dự phòng của một khoản nợ phải thu quá hạn."""
    return round(max(0, amount or 0) * receivable_rate(months, brackets) / 100)


def inventory_provision(quantity, unit_cost, net_realisable):
    """Mức trích dự phòng giảm giá hàng tồn kho của một mặt hàng.

    Chỉ trích khi giá gốc cao hơn giá trị thuần có thể thực hiện được.
    """
    gap = (unit_cost or 0) - (net_realisable or 0)
    if gap <= 0 or (quantity or 0) <= 0:
        return 0
    return round(quantity * gap)


def adjustment(required, already):
    """Chênh lệch phải ghi trong kỳ: dương là trích thêm, âm là hoàn nhập."""
    return round((required or 0) - (already or 0))


if __name__ == '__main__':
    from datetime import date
    # số tháng quá hạn
    assert months_overdue(date(2026, 1, 31), date(2026, 7, 30)) == 5
    assert months_overdue(date(2026, 1, 31), date(2026, 7, 31)) == 6
    assert months_overdue(date(2026, 1, 31), date(2025, 12, 31)) == 0
    assert months_overdue(False, date(2026, 7, 31)) == 0
    # bậc tỷ lệ theo Điều 6
    assert receivable_rate(5) == 0
    assert receivable_rate(6) == 30 and receivable_rate(11) == 30
    assert receivable_rate(12) == 50 and receivable_rate(23) == 50
    assert receivable_rate(24) == 70 and receivable_rate(35) == 70
    assert receivable_rate(36) == 100 and receivable_rate(120) == 100
    assert receivable_provision(100_000_000, 13) == 50_000_000
    assert receivable_provision(100_000_000, 3) == 0
    # doanh nghiệp viễn thông, bán lẻ dùng bậc riêng: truyền brackets khác
    assert receivable_rate(3, [(3, 30), (6, 50), (9, 70), (12, 100)]) == 30
    # dự phòng giảm giá hàng tồn kho
    assert inventory_provision(100, 12_000, 9_000) == 300_000
    assert inventory_provision(100, 9_000, 12_000) == 0
    assert inventory_provision(0, 12_000, 9_000) == 0
    # chênh lệch với số đã trích
    assert adjustment(300_000, 100_000) == 200_000
    assert adjustment(100_000, 300_000) == -200_000
    print('ok')
