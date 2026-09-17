"""Tính thuế thu nhập doanh nghiệp: thuế suất theo doanh thu, chuyển lỗ, kiểm tra tạm nộp.

Căn cứ (đã tra trước khi viết):
- Luật Thuế thu nhập doanh nghiệp 67/2025/QH15 (hiệu lực 01/10/2025): thuế suất phổ thông 20%;
  15% nếu tổng doanh thu năm không quá 3 tỷ đồng; 17% nếu trên 3 tỷ đến không quá 50 tỷ đồng.
  Doanh thu làm căn cứ xác định mức 15%, 17% là tổng doanh thu của kỳ tính thuế liền kề trước đó.
- Chuyển lỗ: chuyển liên tục không quá 05 năm kể từ năm tiếp theo năm phát sinh lỗ.
- Tạm nộp: tổng số thuế đã tạm nộp của 04 quý không được thấp hơn 80% số thuế phải nộp theo
  quyết toán năm; nộp thiếu thì tính tiền chậm nộp trên phần thiếu kể từ ngày tiếp sau ngày cuối
  cùng của thời hạn tạm nộp quý 4.

Mọi mức và tỷ lệ đều là tham số pháp lý có ngày hiệu lực, hàm này chỉ nhận số.
"""


def rate_for(prior_revenue, small_limit, medium_limit, rate_small, rate_medium, rate_standard):
    """Thuế suất theo tổng doanh thu của kỳ tính thuế liền kề trước đó."""
    revenue = prior_revenue or 0
    if revenue <= small_limit:
        return rate_small
    if revenue <= medium_limit:
        return rate_medium
    return rate_standard


def offset_losses(income, losses, year, max_years):
    """Bù trừ lỗ các năm trước vào thu nhập năm nay.

    losses: [(năm phát sinh lỗ, số lỗ còn được chuyển)], lỗ cũ dùng trước.
    Chỉ dùng lỗ còn trong thời hạn: năm nay <= năm lỗ + max_years.
    Trả về ([(năm, số dùng)], thu nhập còn lại).
    """
    remain = max(0, round(income))
    used = []
    for loss_year, amount in sorted(losses):
        amount = max(0, round(amount or 0))
        if not remain:
            break
        if not amount or year <= loss_year or year > loss_year + max_years:
            continue
        take = min(remain, amount)
        used.append((loss_year, take))
        remain -= take
    return used, remain


def shortfall(provisional_paid, tax_due, min_ratio):
    """Số thuế tạm nộp còn thiếu so với tỷ lệ tối thiểu; 0 nếu đã đủ."""
    required = round((tax_due or 0) * (min_ratio or 0) / 100)
    return max(0, required - round(provisional_paid or 0))


if __name__ == '__main__':
    # thuế suất theo doanh thu năm liền kề trước
    assert rate_for(2_900_000_000, 3e9, 50e9, 15, 17, 20) == 15
    assert rate_for(3_000_000_000, 3e9, 50e9, 15, 17, 20) == 15
    assert rate_for(3_000_000_001, 3e9, 50e9, 15, 17, 20) == 17
    assert rate_for(50e9, 3e9, 50e9, 15, 17, 20) == 17
    assert rate_for(50_000_000_001, 3e9, 50e9, 15, 17, 20) == 20
    # chuyển lỗ: lỗ cũ dùng trước, bỏ lỗ quá 5 năm, không dùng lỗ của chính năm nay
    # lỗ 2021 dùng được tới hết kỳ 2026 (2021 + 5); lỗ của chính năm nay không bù vào năm nay
    used, remain = offset_losses(1_000, [(2021, 400), (2022, 300), (2026, 900)], 2026, 5)
    assert used == [(2021, 400), (2022, 300)] and remain == 300, (used, remain)
    used, remain = offset_losses(500, [(2024, 300), (2025, 400)], 2026, 5)
    assert used == [(2024, 300), (2025, 200)] and remain == 0, (used, remain)
    used, remain = offset_losses(0, [(2024, 300)], 2026, 5)
    assert used == [] and remain == 0
    # lỗ năm 2020 hết hạn ở kỳ 2026 (2020 + 5 = 2025)
    assert offset_losses(1_000, [(2020, 900)], 2026, 5) == ([], 1_000)
    assert offset_losses(1_000, [(2020, 900)], 2025, 5) == ([(2020, 900)], 100)
    # tạm nộp 4 quý phải đạt 80% số quyết toán
    assert shortfall(80, 100, 80) == 0
    assert shortfall(70, 100, 80) == 10
    assert shortfall(0, 0, 80) == 0
    print('ok')
