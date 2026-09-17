"""Phân bổ ngân sách hai chiều trên cây khoản mục.

Số kế hoạch chỉ lưu ở khoản mục lá; số của khoản cha luôn là tổng các lá thuộc nhánh
nên sửa lá thì cha tự cộng lên. Sửa ở cấp cha thì chia xuống các lá theo tỷ trọng
hiện có, giữ nguyên dòng đang khóa. Dùng chung hàm chia số dư lớn nhất của chứng từ
để tổng luôn khớp tới đồng.
"""
try:
    from odoo.addons.lfood_voucher.models.tools import allocate
except ImportError:  # chạy trực tiếp tệp này để tự kiểm tra
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'lfood_voucher', 'models'))
    from tools import allocate


class SpreadError(ValueError):
    """Không chia được: tổng mới nhỏ hơn tổng các dòng đang khóa."""


def spread(total, current, locked):
    """Chia `total` xuống các dòng lá.

    current: số hiện tại của từng dòng; locked: dòng nào đang khóa.
    Trả về danh sách số mới, tổng đúng bằng `total`.
    """
    total = int(round(total))
    fixed = sum(int(round(a or 0)) for a, k in zip(current, locked) if k)
    free = [i for i, k in enumerate(locked) if not k]
    out = [int(round(a or 0)) for a in current]
    if not free:
        if total != fixed:
            raise SpreadError('Mọi dòng đều đang khóa, không chia được.')
        return out
    rest = total - fixed
    if rest < 0:
        raise SpreadError('Tổng mới nhỏ hơn tổng các dòng đang khóa.')
    for i, part in zip(free, allocate(rest, [out[i] for i in free])):
        out[i] = part
    return out


if __name__ == '__main__':
    # chia theo tỷ trọng, tổng khớp tới đồng
    r = spread(100, [10, 20, 70], [False] * 3)
    assert r == [10, 20, 70] and sum(r) == 100, r
    r = spread(1000, [10, 20, 70], [False] * 3)
    assert r == [100, 200, 700], r
    # số lẻ: phần dư về dòng có phần lẻ lớn nhất, tổng vẫn đúng
    r = spread(100, [1, 1, 1], [False] * 3)
    assert sum(r) == 100 and sorted(r) == [33, 33, 34], r
    # dòng khóa giữ nguyên, phần còn lại chia cho dòng tự do
    r = spread(100, [50, 10, 10], [True, False, False])
    assert r == [50, 25, 25], r
    # trọng số toàn 0 thì chia đều
    r = spread(90, [0, 0, 0], [False] * 3)
    assert r == [30, 30, 30], r
    # tổng nhỏ hơn phần đang khóa thì từ chối
    try:
        spread(40, [50, 10], [True, False])
        raise AssertionError('phải từ chối')
    except SpreadError:
        pass
    print('ok')
