"""Đánh giá lại khoản mục tiền tệ có gốc ngoại tệ cuối kỳ.

Căn cứ Thông tư 99/2025/TT-BTC (đã tra trước khi viết): đánh giá lại số dư các khoản mục tiền tệ có gốc
ngoại tệ theo tỷ giá mua bán chuyển khoản trung bình của ngân hàng thương mại nơi doanh nghiệp thường xuyên
giao dịch; chênh lệch ghi thẳng vào doanh thu hoạt động tài chính (lãi) hoặc chi phí tài chính (lỗ) và
trình bày theo số thuần giữa tổng lãi và tổng lỗ.
"""


def average_rate(buy, sell):
    """Tỷ giá mua bán chuyển khoản trung bình."""
    return round(((buy or 0) + (sell or 0)) / 2, 4)


def revalue(amount_currency, book_value, rate):
    """Chênh lệch = số dư ngoại tệ quy đổi theo tỷ giá cuối kỳ trừ số dư đồng Việt Nam trên sổ.

    Dùng dấu Nợ trừ Có cho cả tài sản và nợ phải trả: dương là tăng số dư Nợ (lãi với tài sản,
    lãi với nợ phải trả vì số nợ giảm), âm là ngược lại.
    """
    return round((amount_currency or 0) * (rate or 0)) - round(book_value or 0)


def net_result(diffs):
    """(tổng lãi, tổng lỗ, số thuần); số thuần dương ghi Có 515, âm ghi Nợ 635."""
    gain = sum(d for d in diffs if d > 0)
    loss = -sum(d for d in diffs if d < 0)
    return gain, loss, gain - loss


if __name__ == '__main__':
    assert average_rate(25_000, 25_400) == 25_200
    # tiền gửi 1.000 USD, sổ 25.000.000; tỷ giá cuối kỳ 25.200 -> lãi 200.000
    assert revalue(1_000, 25_000_000, 25_200) == 200_000
    # phải trả 2.000 USD (số dư Có), sổ -50.000.000; tỷ giá 25.200 -> nợ tăng, lỗ 400.000
    assert revalue(-2_000, -50_000_000, 25_200) == -400_000
    # phải trả giảm khi tỷ giá giảm: lãi
    assert revalue(-2_000, -50_000_000, 24_900) == 200_000
    assert net_result([200_000, -400_000]) == (200_000, 400_000, -200_000)
    assert net_result([]) == (0, 0, 0)
    print('ok')
