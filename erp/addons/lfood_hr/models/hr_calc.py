"""Tính phép năm, tiền làm thêm giờ, kiểm tra hợp đồng và giới hạn làm thêm.

Căn cứ Bộ luật Lao động 45/2019/QH14 (đã tra trước khi viết):
- Điều 20: hợp đồng xác định thời hạn không quá 36 tháng.
- Điều 25: thử việc không quá 180 ngày (quản lý doanh nghiệp), 60 ngày (trình độ cao đẳng trở lên),
  30 ngày (trung cấp, công nhân kỹ thuật, nhân viên nghiệp vụ), 6 ngày làm việc (công việc khác).
- Điều 26: tiền lương thử việc ít nhất bằng 85% mức lương của công việc đó.
- Điều 98: làm thêm ngày thường ít nhất 150%, ngày nghỉ hằng tuần 200%, ngày lễ tết 300%;
  làm việc ban đêm trả thêm ít nhất 30%; làm thêm vào ban đêm trả thêm 20% tiền lương ban ngày.
- Điều 107: làm thêm không quá 50% giờ làm việc bình thường trong ngày, 40 giờ trong tháng,
  200 giờ trong năm (một số ngành, nghề được tới 300 giờ).
- Điều 113, 114: phép năm 12, 14 hoặc 16 ngày theo điều kiện làm việc; chưa đủ 12 tháng thì tính
  theo tỷ lệ; cứ đủ 5 năm làm việc được thêm 1 ngày.
Mọi mức là tham số pháp lý; hàm chỉ nhận số.
"""
from datetime import date


def months_between(start, end):
    """Số tháng làm việc tròn từ ngày bắt đầu tới ngày tính."""
    if not start or not end or end < start:
        return 0
    months = (end.year - start.year) * 12 + end.month - start.month
    if end.day < start.day:
        months -= 1
    return max(0, months)


def annual_leave(base_days, date_start, year, seniority_step=5):
    """Số ngày phép năm của một năm dương lịch.

    Đủ 12 tháng thì được đủ số ngày cộng thâm niên; vào làm trong năm thì tính theo tỷ lệ số tháng
    làm việc trong năm, làm tròn tới nửa ngày.
    """
    if not date_start or date_start.year > year:
        return 0.0
    year_end = date(year, 12, 31)
    years = months_between(date_start, year_end) // 12
    extra = years // seniority_step if seniority_step else 0
    if date_start.year < year:
        return float(base_days + extra)
    worked = months_between(date_start, year_end) + 1
    return round((base_days * min(worked, 12) / 12) * 2) / 2


def hourly_rate(monthly_salary, standard_days, hours_per_day):
    """Tiền lương giờ làm việc bình thường."""
    if not standard_days or not hours_per_day:
        return 0.0
    return (monthly_salary or 0) / standard_days / hours_per_day


def overtime_pay(rate, hours, factors, night_hours=0, night_extra=0, ot_night_hours=0, ot_night_extra=0):
    """Tiền làm thêm và làm đêm.

    hours: {'normal': giờ, 'weekend': giờ, 'holiday': giờ}
    factors: {'normal': 150, 'weekend': 200, 'holiday': 300} (phần trăm)
    night_extra: phần trăm trả thêm khi làm việc ban đêm trong giờ bình thường.
    ot_night_extra: phần trăm trả thêm khi làm thêm vào ban đêm, tính trên đơn giá ban ngày.
    """
    total = sum(rate * (hours.get(k) or 0) * factors[k] / 100 for k in factors)
    total += rate * (night_hours or 0) * (night_extra or 0) / 100
    total += rate * (ot_night_hours or 0) * (ot_night_extra or 0) / 100
    return round(total)


def overtime_warnings(day_hours, month_hours, year_hours, normal_day_hours, day_ratio, month_limit, year_limit):
    """Danh sách vượt giới hạn làm thêm; rỗng nếu trong giới hạn."""
    out = []
    if normal_day_hours and day_hours > normal_day_hours * day_ratio / 100 + 1e-9:
        out.append('day')
    if month_hours > month_limit + 1e-9:
        out.append('month')
    if year_hours > year_limit + 1e-9:
        out.append('year')
    return out


def contract_months(date_start, date_end):
    """Độ dài hợp đồng tính theo tháng, phần lẻ ngày tính thành một tháng."""
    if not date_start or not date_end:
        return 0
    months = months_between(date_start, date_end)
    probe = date_start
    y, m = divmod(probe.month - 1 + months, 12)
    try:
        boundary = probe.replace(year=probe.year + y, month=m + 1)
    except ValueError:
        boundary = date(probe.year + y, m + 1, 28)
    return months + (1 if date_end >= boundary else 0)


def allowance_years(months):
    """Số năm tính trợ cấp thôi việc, mất việc (Nghị định 145/2020/NĐ-CP, Điều 8 khoản 3).

    Tính theo năm đủ 12 tháng; tháng lẻ từ 1 đến 6 tháng tính 1/2 năm, trên 6 tháng tính 1 năm.
    """
    months = max(0, int(months or 0))
    years, rest = divmod(months, 12)
    if rest:
        years += 0.5 if rest <= 6 else 1
    return years


def severance(kind, months_worked, months_counted, avg_salary, min_service=12, resign_rate=0.5,
              redundancy_rate=1.0, redundancy_min=2.0):
    """Trợ cấp thôi việc (Điều 46) hoặc mất việc làm (Điều 47) của Bộ luật Lao động 2019.

    months_worked: tổng thời gian làm việc thực tế, dùng xét điều kiện đủ 12 tháng.
    months_counted: thời gian tính trợ cấp, đã trừ thời gian tham gia BHTN và thời gian đã được chi trả.
    """
    if (months_worked or 0) < min_service:
        return 0
    years = allowance_years(months_counted)
    if not years:
        # toàn bộ thời gian đã đóng BHTN hoặc đã được chi trả: luật không nói rõ còn áp mức tối thiểu 2 tháng
        # của Điều 47 hay không, app trả 0 và để kế toán trưởng xác định
        return 0
    if kind == 'resign':
        return round(years * resign_rate * avg_salary)
    if kind == 'redundancy':
        return round(max(years * redundancy_rate, redundancy_min) * avg_salary)
    return 0


if __name__ == '__main__':
    # làm tròn thời gian tính trợ cấp
    assert allowance_years(0) == 0 and allowance_years(12) == 1
    assert allowance_years(13) == 1.5 and allowance_years(18) == 1.5
    assert allowance_years(19) == 2 and allowance_years(30) == 2.5
    # thôi việc: 3,5 năm tính trợ cấp x 1/2 tháng lương 10 triệu = 17,5 triệu
    assert severance('resign', 60, 42, 10_000_000) == 17_500_000
    # chưa đủ 12 tháng thì không có trợ cấp
    assert severance('resign', 11, 11, 10_000_000) == 0
    # đã đóng BHTN toàn bộ thời gian thì thời gian tính trợ cấp bằng 0
    assert severance('resign', 60, 0, 10_000_000) == 0
    # mất việc: mỗi năm 1 tháng, ít nhất 2 tháng
    assert severance('redundancy', 14, 14, 10_000_000) == 20_000_000
    assert severance('redundancy', 60, 42, 10_000_000) == 35_000_000
    assert severance('other', 60, 42, 10_000_000) == 0
    assert severance('redundancy', 60, 0, 10_000_000) == 0
    # phép năm: vào làm từ năm trước thì đủ 12 ngày; đủ 5 năm thêm 1 ngày
    assert annual_leave(12, date(2025, 3, 1), 2026) == 12
    assert annual_leave(12, date(2020, 1, 1), 2026) == 13
    assert annual_leave(12, date(2016, 1, 1), 2026) == 14
    assert annual_leave(14, date(2020, 1, 1), 2026) == 15
    # vào làm 01/7/2026: 6 tháng làm việc, 12 x 6/12 = 6 ngày
    assert annual_leave(12, date(2026, 7, 1), 2026) == 6
    # vào làm 16/9/2026: tính tháng 9, 10, 11, 12 là 4 tháng làm việc trong năm, 12 x 4/12 = 4
    assert annual_leave(12, date(2026, 9, 16), 2026) == 4
    assert annual_leave(12, date(2027, 1, 1), 2026) == 0
    # tiền làm thêm: lương 10.400.000, 26 công, 8 giờ = 50.000 đồng/giờ
    r = hourly_rate(10_400_000, 26, 8)
    assert r == 50_000
    factors = {'normal': 150, 'weekend': 200, 'holiday': 300}
    assert overtime_pay(r, {'normal': 10}, factors) == 750_000
    assert overtime_pay(r, {'normal': 10, 'weekend': 8, 'holiday': 8}, factors) == 750_000 + 800_000 + 1_200_000
    # làm đêm 10 giờ trong giờ bình thường: thêm 30%; làm thêm ban đêm 4 giờ: thêm 20%
    assert overtime_pay(r, {}, factors, night_hours=10, night_extra=30) == 150_000
    assert overtime_pay(r, {'normal': 4}, factors, ot_night_hours=4, ot_night_extra=20) == 300_000 + 40_000
    # giới hạn làm thêm
    assert overtime_warnings(4, 40, 200, 8, 50, 40, 200) == []
    assert overtime_warnings(5, 41, 201, 8, 50, 40, 200) == ['day', 'month', 'year']
    # độ dài hợp đồng
    assert contract_months(date(2026, 1, 1), date(2028, 12, 31)) == 36
    assert contract_months(date(2026, 1, 1), date(2029, 1, 1)) == 37
    assert contract_months(date(2026, 1, 15), date(2026, 2, 14)) == 1
    print('ok')
