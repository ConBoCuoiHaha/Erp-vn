"""Chế độ ốm đau, thai sản theo Luật Bảo hiểm xã hội 41/2024/QH15 (hiệu lực 01/7/2025), không phụ thuộc Odoo.

Ốm đau (Điều 43): tối đa trong năm 30/40/60 ngày làm việc theo thời gian đóng dưới 15 năm, 15 đến dưới 30 năm,
từ 30 năm; nghề nặng nhọc, độc hại hoặc nơi phụ cấp khu vực từ 0,7: 40/50/70 ngày. Chăm con ốm (Điều 44): con dưới 3
tuổi 20 ngày, từ 3 đến dưới 7 tuổi 15 ngày mỗi năm. Mức hưởng (Điều 45): 75% tiền lương đóng BHXH của tháng gần nhất
trước khi nghỉ; một ngày = mức tháng chia 24. Khám thai (Điều 51): tối đa 5 lần, mỗi lần 2 ngày. Sảy thai (Điều 52):
10/20/40/50 ngày theo tuổi thai dưới 5 tuần, 5 đến dưới 13, 13 đến dưới 22, từ 22 tuần. Lao động nam khi vợ sinh
(Điều 53): 5 ngày, 7 ngày nếu phẫu thuật hoặc sinh dưới 32 tuần, 10 ngày sinh đôi, 14 ngày sinh đôi phải phẫu thuật.
Mức hưởng thai sản (Điều 59): 100% bình quân tiền lương đóng BHXH 6 tháng gần nhất; một ngày = mức tháng chia 24.
Trợ cấp một lần (Điều 58): 2 lần mức tham chiếu cho mỗi con.
"""


def sick_limit(years, hard_job=False):
    base = (30, 40, 60) if not hard_job else (40, 50, 70)
    return base[0] if years < 15 else base[1] if years < 30 else base[2]


def child_sick_limit(child_age):
    return 20 if child_age < 3 else 15 if child_age < 7 else 0


def miscarriage_days(weeks):
    return 10 if weeks < 5 else 20 if weeks < 13 else 40 if weeks < 22 else 50


def male_birth_days(surgery=False, twins=False, preterm=False):
    if twins:
        return 14 if surgery else 10
    return 7 if (surgery or preterm) else 5


def daily_amount(monthly_salary, rate_percent):
    return monthly_salary * rate_percent / 100 / 24


if __name__ == '__main__':
    assert sick_limit(10) == 30 and sick_limit(15) == 40 and sick_limit(30) == 60 and sick_limit(10, True) == 40
    assert child_sick_limit(2) == 20 and child_sick_limit(5) == 15 and child_sick_limit(7) == 0
    assert miscarriage_days(4) == 10 and miscarriage_days(12) == 20 and miscarriage_days(21) == 40 and miscarriage_days(22) == 50
    assert male_birth_days() == 5 and male_birth_days(surgery=True) == 7 and male_birth_days(preterm=True) == 7
    assert male_birth_days(twins=True) == 10 and male_birth_days(True, True) == 14
    # lương đóng BHXH 8 triệu, ốm 3 ngày: 8.000.000 x 75% / 24 x 3 = 750.000
    assert round(daily_amount(8_000_000, 75) * 3) == 750_000
    print('ok')
