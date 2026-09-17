"""Thời hạn xử lý yêu cầu của chủ thể dữ liệu theo Nghị định 356/2025/NĐ-CP, không phụ thuộc Odoo.

Phản hồi: 2 ngày làm việc. Thực hiện (ngày): rút đồng ý, hạn chế, phản đối 15 (cần bên xử lý, bên thứ ba phối hợp 20,
gia hạn một lần tối đa 15); xem, chỉnh sửa, cung cấp 10 (15, gia hạn 10); xóa 20 (30, gia hạn 20);
biện pháp bảo vệ 15 (gia hạn 15).
"""
from datetime import timedelta

DAYS = {  # loại yêu cầu: (thời hạn, thời hạn khi cần bên thứ ba, gia hạn tối đa)
    'withdraw': (15, 20, 15),
    'access': (10, 15, 10),
    'delete': (20, 30, 20),
    'protect': (15, 15, 15),
}


def deadlines(kind, received, third_party=False, extended=False):
    """(hạn thực hiện tính theo ngày); hạn phản hồi 2 ngày làm việc tính bằng lịch nghỉ trong model."""
    base, with_third, ext = DAYS[kind]
    days = (with_third if third_party else base) + (ext if extended else 0)
    return received + timedelta(days=days)


if __name__ == '__main__':
    from datetime import date
    # nhận thứ Sáu 11/12/2026: phản hồi trước thứ Ba 15/12
    assert deadlines('access', date(2026, 12, 11)) == date(2026, 12, 21)
    assert deadlines('delete', date(2026, 12, 1), third_party=True) == date(2026, 12, 31)
    assert deadlines('withdraw', date(2026, 12, 1), extended=True) == date(2026, 12, 31)
    print('ok')
