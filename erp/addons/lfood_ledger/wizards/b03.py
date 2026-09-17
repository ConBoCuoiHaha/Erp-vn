"""Báo cáo lưu chuyển tiền tệ (Mẫu B03-DN, phương pháp trực tiếp) theo Phụ lục IV Thông tư 99/2025/TT-BTC.

Mỗi dòng thu, chi tiền (111, 112, 113) được phân loại theo tài khoản đối ứng trong cùng bút toán như hướng dẫn
"sau khi đối chiếu với sổ kế toán các tài khoản ..." của từng chỉ tiêu. Chuyển tiền giữa 111, 112, 113 không phải
luồng tiền. Một số trường hợp cần biết chứng từ nguồn (thanh lý TSCĐ, trả tiền mua TSCĐ) nên hàm nhận thêm `hint`."""

CASH = ('111', '112', '113')

# (tiền tố tài khoản đối ứng, mã chỉ tiêu) — xét theo thứ tự, tiền tố dài đặt trước
INFLOW = [
    ('3334', '06'), ('33311', '01'), ('3411', '33'), ('3412', '33'), ('41112', '33'),
    ('511', '01'), ('131', '01'), ('121', '01'), ('3387', '01'),
    ('128', '24'), ('171', '24'), ('221', '26'), ('222', '26'), ('228', '26'), ('515', '27'),
    ('411', '31'), ('343', '33'),
    ('711', '06'), ('133', '06'), ('1383', '06'), ('141', '06'), ('244', '06'), ('333', '06'), ('344', '06'),
]
OUTFLOW = [
    ('3334', '05'), ('3412', '35'), ('3411', '34'), ('41112', '34'), ('343', '34'),
    ('211', '21'), ('212', '21'), ('213', '21'), ('215', '21'), ('217', '21'), ('241', '21'),
    ('128', '23'), ('171', '23'), ('221', '25'), ('222', '25'), ('228', '25'),
    ('411', '32'), ('419', '32'), ('421', '36'), ('332', '36'),
    ('334', '03'), ('635', '04'), ('335', '04'),
    ('331', '02'), ('15', '02'), ('62', '02'), ('632', '02'), ('641', '02'), ('642', '02'), ('121', '02'), ('133', '02'),
    ('811', '07'), ('244', '07'), ('333', '07'), ('338', '07'), ('344', '07'), ('352', '07'), ('353', '07'),
    ('356', '07'), ('141', '07'),
]
OUT_CODES = {'02', '03', '04', '05', '07', '21', '23', '25', '32', '34', '35', '36'}

LINES = [
    ('', 'I. Lưu chuyển tiền từ hoạt động kinh doanh'),
    ('01', '1. Tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác'),
    ('02', '2. Tiền chi trả cho người cung cấp hàng hóa, dịch vụ'),
    ('03', '3. Tiền chi trả cho người lao động'), ('04', '4. Chi phí đi vay đã trả'), ('05', '5. Thuế thu nhập doanh nghiệp đã nộp'),
    ('06', '6. Tiền thu khác từ hoạt động kinh doanh'), ('07', '7. Tiền chi khác cho hoạt động kinh doanh'),
    ('20', 'Lưu chuyển tiền thuần từ hoạt động kinh doanh'),
    ('', 'II. Lưu chuyển tiền từ hoạt động đầu tư'),
    ('21', '1. Tiền chi để mua sắm, xây dựng TSCĐ và các tài sản dài hạn khác'),
    ('22', '2. Tiền thu từ thanh lý, nhượng bán TSCĐ và các tài sản dài hạn khác'),
    ('23', '3. Tiền chi cho vay, mua các công cụ nợ của đơn vị khác'),
    ('24', '4. Tiền thu hồi cho vay, bán lại các công cụ nợ của đơn vị khác'),
    ('25', '5. Tiền chi đầu tư góp vốn vào đơn vị khác'), ('26', '6. Tiền thu hồi đầu tư góp vốn vào đơn vị khác'),
    ('27', '7. Tiền thu lãi cho vay, cổ tức và lợi nhuận được chia'),
    ('30', 'Lưu chuyển tiền thuần từ hoạt động đầu tư'),
    ('', 'III. Lưu chuyển tiền từ hoạt động tài chính'),
    ('31', '1. Tiền thu từ phát hành cổ phiếu, nhận vốn góp của chủ sở hữu'),
    ('32', '2. Tiền trả lại vốn góp cho các chủ sở hữu, mua lại cổ phiếu của doanh nghiệp đã phát hành'),
    ('33', '3. Tiền thu từ đi vay'), ('34', '4. Tiền trả nợ gốc vay'), ('35', '5. Tiền trả nợ gốc thuê tài chính'),
    ('36', '6. Cổ tức, lợi nhuận đã trả cho chủ sở hữu'),
    ('40', 'Lưu chuyển tiền thuần từ hoạt động tài chính'),
    ('50', 'Lưu chuyển tiền thuần trong kỳ (50 = 20 + 30 + 40)'),
    ('60', 'Tiền và tương đương tiền đầu kỳ'),
    ('61', 'Ảnh hưởng của thay đổi tỷ giá hối đoái quy đổi ngoại tệ'),
    ('70', 'Tiền và tương đương tiền cuối kỳ (70 = 50 + 60 + 61)'),
]
BOLD = {'20', '30', '40', '50', '70'}


def classify(counter_code, inflow, hint=None):
    if hint:
        return hint
    for prefix, code in (INFLOW if inflow else OUTFLOW):
        if counter_code.startswith(prefix):
            return code
    return '06' if inflow else '07'


def split_amount(amount, weights):
    total = sum(weights)
    if not total:
        return [amount] + [0] * (len(weights) - 1)
    out = [round(amount * w / total) for w in weights]
    out[-1] += amount - sum(out)
    return out


def compute(moves, opening, fx=0):
    """moves: [(các dòng [(mã TK, Nợ trừ Có)], gợi ý chỉ tiêu hoặc None)] -> {mã: số}; chi ghi âm."""
    v = dict.fromkeys([c for c, _ in LINES if c], 0)
    for lines, hint in moves:
        cash = sum(b for c, b in lines if c.startswith(CASH))
        others = [(c, b) for c, b in lines if not c.startswith(CASH)]
        if not round(cash) or not others:
            continue  # chuyển tiền nội bộ giữa quỹ và ngân hàng
        inflow = cash > 0
        # đối ứng là các dòng ngược chiều với dòng tiền
        counters = [(c, abs(b)) for c, b in others if (b < 0) == inflow] or [(c, abs(b)) for c, b in others]
        for (code, _w), part in zip(counters, split_amount(abs(round(cash)), [w for _c, w in counters])):
            key = classify(code, inflow, hint)
            v[key] += part if inflow else -part
    v['20'] = sum(v[k] for k in ('01', '02', '03', '04', '05', '06', '07'))
    v['30'] = sum(v[k] for k in ('21', '22', '23', '24', '25', '26', '27'))
    v['40'] = sum(v[k] for k in ('31', '32', '33', '34', '35', '36'))
    v['50'] = v['20'] + v['30'] + v['40']
    v['60'] = round(opening)
    v['61'] = round(fx)
    v['70'] = v['50'] + v['60'] + v['61']
    return v


if __name__ == '__main__':
    moves = [
        ([('112', -50_000_000), ('3311', 50_000_000)], None),                     # trả nhà cung cấp
        ([('1311', 216_000_000), ('511', -200_000_000), ('33311', -16_000_000)], None),  # bán chịu: không có tiền
        ([('112', 100_000_000), ('1311', -100_000_000)], None),                   # thu tiền khách
        ([('111', 20_000_000), ('112', -20_000_000)], None),                      # rút tiền về quỹ: nội bộ
        ([('111', 50_000_000), ('711', -50_000_000)], '22'),                      # thu thanh lý TSCĐ
        ([('112', -30_000_000), ('334', 30_000_000)], None),                      # trả lương
        ([('112', -10_000_000), ('3411', 9_000_000), ('635', 1_000_000)], None),  # trả gốc và lãi vay
    ]
    v = compute(moves, opening=500_000_000)
    assert (v['01'], v['02'], v['03'], v['04'], v['22'], v['34']) == (100e6, -50e6, -30e6, -1e6, 50e6, -9e6), v
    assert v['50'] == 60_000_000 and v['70'] == 560_000_000, v
    print('ok')
