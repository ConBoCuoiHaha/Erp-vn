"""Báo cáo tình hình tài chính (Mẫu B01-DN, Phụ lục IV Thông tư 99/2025/TT-BTC), doanh nghiệp hoạt động liên tục.

Mỗi chỉ tiêu chi tiết lấy số dư theo quy tắc: (tiền tố tài khoản, cách lấy, kỳ hạn)
  'dr'  : tổng số dư Nợ chi tiết (theo từng tài khoản chi tiết và từng đối tượng)
  'cr'  : tổng số dư Có chi tiết, trình bày số dương
  'ncr' : số dư Có trừ số dư Nợ, âm thì ghi trong ngoặc đơn (412, 413, 421...)
  'neg' : số dư Có chi tiết ghi số âm (dự phòng, hao mòn)
  'ndr' : số dư Nợ ghi số âm (419 cổ phiếu mua lại)
Kỳ hạn lấy theo thuộc tính Ngắn hạn / Dài hạn / Tương đương tiền của tài khoản chi tiết."""

S, L, E, A = 'short', 'long', 'equivalent', None
RECEIVABLE_OTHER = ['1388', '334', '338', '141', '244']
PAYABLE_OTHER = ['3381', '3382', '3383', '3384', '3386', '3388', '138', '344']

LEAF = {
    '111': [(['111', '112', '113'], 'dr', A)],
    '112': [(['1281', '1288'], 'dr', E)],
    '121': [(['121'], 'dr', A)], '122': [(['2291'], 'neg', A)],
    '123': [(['1281', '1282', '1283', '1288'], 'dr', S)],
    '125': [(['2281'], 'dr', S)], '126': [(['2292'], 'neg', S)],
    '131': [(['131'], 'dr', S)], '132': [(['331'], 'dr', S)], '133': [(['1362', '1363', '1368'], 'dr', S)],
    '134': [(['337'], 'dr', A)], '135': [(RECEIVABLE_OTHER, 'dr', S)], '136': [(['2293'], 'neg', S)],
    '137': [(['1381'], 'dr', A)],
    '141': [(['151', '152', '153', '155', '156', '157', '158'], 'dr', A), (['154'], 'dr', S)],
    '142': [(['2294'], 'neg', A)],
    '151': [(['2152'], 'dr', S)], '152': [(['2153'], 'dr', S)], '153': [(['2295'], 'neg', S)],
    '161': [(['242'], 'dr', S)], '162': [(['133'], 'dr', A)], '163': [(['1383', '333'], 'dr', A)],
    '164': [(['171'], 'dr', A)], '165': [(['2288'], 'dr', S)],
    '211': [(['131'], 'dr', L)], '212': [(['331'], 'dr', L)], '213': [(['1361'], 'dr', A)],
    '214': [(['1362', '1363', '1368'], 'dr', L)], '215': [(RECEIVABLE_OTHER, 'dr', L)], '216': [(['2293'], 'neg', L)],
    '222': [(['211'], 'dr', A)], '223': [(['2141'], 'neg', A)],
    '225': [(['212'], 'dr', A)], '226': [(['2142'], 'neg', A)],
    '228': [(['213'], 'dr', A)], '229': [(['2143'], 'neg', A)],
    '232': [(['21511'], 'dr', A)], '233': [(['21512'], 'dr', A)],
    '236': [(['2152'], 'dr', L)], '237': [(['2153'], 'dr', L)], '238': [(['2295'], 'neg', L)],
    '241': [(['217'], 'dr', A)], '242': [(['2147'], 'neg', A)],
    '251': [(['154'], 'dr', L)], '252': [(['241'], 'dr', A)],
    '261': [(['221'], 'dr', A)], '262': [(['222'], 'dr', A)], '263': [(['2281'], 'dr', L)], '264': [(['2292'], 'neg', L)],
    '265': [(['1281', '1282', '1283', '1288'], 'dr', L)],
    '271': [(['242'], 'dr', L)], '272': [(['243'], 'dr', A)],
    '311': [(['331'], 'cr', S)], '312': [(['131'], 'cr', S)], '313': [(['332'], 'cr', A)], '314': [(['333'], 'cr', S)],
    '315': [(['334'], 'cr', A)], '316': [(['335'], 'cr', S)], '317': [(['3362', '3363', '3368'], 'cr', S)],
    '318': [(['337'], 'cr', A)], '319': [(['3387'], 'cr', S)], '320': [(PAYABLE_OTHER, 'cr', S)],
    '321': [(['341', '3431'], 'cr', S)], '322': [(['352'], 'cr', S)], '323': [(['353'], 'cr', A)],
    '324': [(['357'], 'cr', A)], '325': [(['171'], 'cr', A)],
    '331': [(['331'], 'cr', L)], '332': [(['131'], 'cr', L)], '333': [(['333'], 'cr', L)], '334': [(['335'], 'cr', L)],
    '335': [(['3361'], 'cr', A)], '336': [(['3362', '3363', '3368'], 'cr', L)], '337': [(['3387'], 'cr', L)],
    '338': [(PAYABLE_OTHER, 'cr', L)], '339': [(['341', '3431'], 'cr', L)], '340': [(['3432'], 'cr', A)],
    '342': [(['347'], 'cr', A)], '343': [(['352'], 'cr', L)], '344': [(['356'], 'cr', A)],
    '411': [(['4111'], 'ncr', A)], '412': [(['4112'], 'ncr', A)], '413': [(['4113'], 'ncr', A)], '414': [(['4118'], 'ncr', A)],
    '415': [(['419'], 'ndr', A)], '416': [(['412'], 'ncr', A)], '417': [(['413'], 'ncr', A)], '418': [(['414'], 'ncr', A)],
    '419': [(['418'], 'ncr', A)], '420a': [(['4211'], 'ncr', A)], '420b': [(['4212'], 'ncr', A)],
}

TOTALS = [
    ('110', ['111', '112']), ('120', ['121', '122', '123', '124', '125', '126']),
    ('130', ['131', '132', '133', '134', '135', '136', '137']), ('140', ['141', '142']), ('150', ['151', '152', '153']),
    ('160', ['161', '162', '163', '164', '165']), ('100', ['110', '120', '130', '140', '150', '160']),
    ('210', ['211', '212', '213', '214', '215', '216']),
    ('221', ['222', '223']), ('224', ['225', '226']), ('227', ['228', '229']), ('220', ['221', '224', '227']),
    ('231', ['232', '233']), ('230', ['231', '236', '237', '238']), ('240', ['241', '242']), ('250', ['251', '252']),
    ('260', ['261', '262', '263', '264', '265', '266']), ('270', ['271', '272', '273', '274']),
    ('200', ['210', '220', '230', '240', '250', '260', '270']), ('280', ['100', '200']),
    ('310', ['311', '312', '313', '314', '315', '316', '317', '318', '319', '320', '321', '322', '323', '324', '325']),
    ('330', ['331', '332', '333', '334', '335', '336', '337', '338', '339', '340', '341', '342', '343', '344']),
    ('300', ['310', '330']), ('420', ['420a', '420b']),
    ('400', ['411', '412', '413', '414', '415', '416', '417', '418', '419', '420']), ('440', ['300', '400']),
]

LINES = [
    ('', 'TÀI SẢN'), ('100', 'A. TÀI SẢN NGẮN HẠN'),
    ('110', 'I. Tiền và các khoản tương đương tiền'), ('111', '1. Tiền'), ('112', '2. Các khoản tương đương tiền'),
    ('120', 'II. Đầu tư tài chính ngắn hạn'), ('121', '1. Chứng khoán kinh doanh'), ('122', '2. Dự phòng giảm giá chứng khoán kinh doanh (*)'),
    ('123', '3. Đầu tư nắm giữ đến ngày đáo hạn ngắn hạn'), ('124', '4. Dự phòng đầu tư nắm giữ đến ngày đáo hạn ngắn hạn (*)'),
    ('125', '5. Đầu tư ngắn hạn khác'), ('126', '6. Dự phòng tổn thất các khoản đầu tư ngắn hạn khác (*)'),
    ('130', 'III. Các khoản phải thu ngắn hạn'), ('131', '1. Phải thu ngắn hạn của khách hàng'), ('132', '2. Trả trước cho người bán ngắn hạn'),
    ('133', '3. Phải thu nội bộ ngắn hạn'), ('134', '4. Phải thu theo tiến độ hợp đồng xây dựng'), ('135', '5. Phải thu ngắn hạn khác'),
    ('136', '6. Dự phòng phải thu ngắn hạn khó đòi (*)'), ('137', '7. Tài sản thiếu chờ xử lý'),
    ('140', 'IV. Hàng tồn kho'), ('141', '1. Hàng tồn kho'), ('142', '2. Dự phòng giảm giá hàng tồn kho (*)'),
    ('150', 'V. Tài sản sinh học ngắn hạn'), ('151', '1. Súc vật nuôi lấy sản phẩm một lần ngắn hạn'),
    ('152', '2. Cây trồng theo mùa vụ hoặc lấy sản phẩm một lần ngắn hạn'), ('153', '3. Dự phòng tổn thất tài sản sinh học ngắn hạn (*)'),
    ('160', 'VI. Tài sản ngắn hạn khác'), ('161', '1. Chi phí chờ phân bổ ngắn hạn'), ('162', '2. Thuế giá trị gia tăng được khấu trừ'),
    ('163', '3. Thuế và các khoản khác phải thu Nhà nước'), ('164', '4. Giao dịch mua bán lại trái phiếu Chính phủ'), ('165', '5. Tài sản ngắn hạn khác'),
    ('200', 'B. TÀI SẢN DÀI HẠN'),
    ('210', 'I. Các khoản phải thu dài hạn'), ('211', '1. Phải thu dài hạn của khách hàng'), ('212', '2. Trả trước cho người bán dài hạn'),
    ('213', '3. Vốn kinh doanh ở đơn vị trực thuộc'), ('214', '4. Phải thu nội bộ dài hạn'), ('215', '5. Phải thu dài hạn khác'),
    ('216', '6. Dự phòng phải thu dài hạn khó đòi (*)'),
    ('220', 'II. Tài sản cố định'), ('221', '1. Tài sản cố định hữu hình'), ('222', '- Nguyên giá'), ('223', '- Giá trị hao mòn lũy kế (*)'),
    ('224', '2. Tài sản cố định thuê tài chính'), ('225', '- Nguyên giá'), ('226', '- Giá trị hao mòn lũy kế (*)'),
    ('227', '3. Tài sản cố định vô hình'), ('228', '- Nguyên giá'), ('229', '- Giá trị hao mòn lũy kế (*)'),
    ('230', 'III. Tài sản sinh học dài hạn'), ('231', '1. Súc vật nuôi cho sản phẩm định kỳ dài hạn'),
    ('232', '- Chưa đến giai đoạn trưởng thành'), ('233', '- Đạt đến giai đoạn trưởng thành'),
    ('236', '2. Súc vật nuôi lấy sản phẩm một lần dài hạn'), ('237', '3. Cây trồng theo mùa vụ hoặc lấy sản phẩm một lần dài hạn'),
    ('238', '4. Dự phòng tổn thất tài sản sinh học dài hạn (*)'),
    ('240', 'IV. Bất động sản đầu tư'), ('241', '- Nguyên giá'), ('242', '- Giá trị hao mòn lũy kế (*)'),
    ('250', 'V. Tài sản dở dang dài hạn'), ('251', '1. Chi phí sản xuất, kinh doanh dở dang dài hạn'), ('252', '2. Chi phí xây dựng cơ bản dở dang'),
    ('260', 'VI. Đầu tư tài chính dài hạn'), ('261', '1. Đầu tư vào công ty con'), ('262', '2. Đầu tư vào công ty liên doanh, liên kết'),
    ('263', '3. Đầu tư góp vốn vào đơn vị khác'), ('264', '4. Dự phòng tổn thất đầu tư vào đơn vị khác dài hạn (*)'),
    ('265', '5. Đầu tư nắm giữ đến ngày đáo hạn dài hạn'), ('266', '6. Dự phòng đầu tư nắm giữ đến ngày đáo hạn dài hạn (*)'),
    ('270', 'VII. Tài sản dài hạn khác'), ('271', '1. Chi phí chờ phân bổ dài hạn'), ('272', '2. Tài sản thuế thu nhập hoãn lại'),
    ('273', '3. Thiết bị, vật tư, phụ tùng thay thế dài hạn'), ('274', '4. Tài sản dài hạn khác'),
    ('280', 'TỔNG CỘNG TÀI SẢN (280 = 100 + 200)'),
    ('', 'NGUỒN VỐN'), ('300', 'C. NỢ PHẢI TRẢ'), ('310', 'I. Nợ ngắn hạn'),
    ('311', '1. Phải trả người bán ngắn hạn'), ('312', '2. Người mua trả tiền trước ngắn hạn'), ('313', '3. Phải trả cổ tức, lợi nhuận'),
    ('314', '4. Thuế và các khoản phải nộp Nhà nước ngắn hạn'), ('315', '5. Phải trả người lao động'), ('316', '6. Chi phí phải trả ngắn hạn'),
    ('317', '7. Phải trả nội bộ ngắn hạn'), ('318', '8. Phải trả theo tiến độ hợp đồng xây dựng'), ('319', '9. Doanh thu chờ phân bổ ngắn hạn'),
    ('320', '10. Phải trả ngắn hạn khác'), ('321', '11. Vay và nợ thuê tài chính ngắn hạn'), ('322', '12. Dự phòng phải trả ngắn hạn'),
    ('323', '13. Quỹ khen thưởng, phúc lợi'), ('324', '14. Quỹ bình ổn giá'), ('325', '15. Giao dịch mua bán lại trái phiếu Chính phủ'),
    ('330', 'II. Nợ dài hạn'), ('331', '1. Phải trả người bán dài hạn'), ('332', '2. Người mua trả tiền trước dài hạn'),
    ('333', '3. Thuế và các khoản phải nộp Nhà nước dài hạn'), ('334', '4. Chi phí phải trả dài hạn'), ('335', '5. Phải trả nội bộ về vốn kinh doanh'),
    ('336', '6. Phải trả nội bộ dài hạn'), ('337', '7. Doanh thu chờ phân bổ dài hạn'), ('338', '8. Phải trả dài hạn khác'),
    ('339', '9. Vay và nợ thuê tài chính dài hạn'), ('340', '10. Trái phiếu chuyển đổi'), ('341', '11. Cổ phiếu ưu đãi'),
    ('342', '12. Thuế thu nhập hoãn lại phải trả'), ('343', '13. Dự phòng phải trả dài hạn'), ('344', '14. Quỹ phát triển khoa học và công nghệ'),
    ('400', 'D. VỐN CHỦ SỞ HỮU'),
    ('411', '1. Vốn góp của chủ sở hữu'), ('412', '2. Thặng dư vốn'), ('413', '3. Quyền chọn chuyển đổi trái phiếu'),
    ('414', '4. Vốn khác của chủ sở hữu'), ('415', '5. Cổ phiếu mua lại của chính mình (*)'), ('416', '6. Chênh lệch đánh giá lại tài sản'),
    ('417', '7. Chênh lệch tỷ giá hối đoái'), ('418', '8. Quỹ đầu tư phát triển'), ('419', '9. Quỹ khác thuộc vốn chủ sở hữu'),
    ('420', '10. Lợi nhuận sau thuế chưa phân phối'), ('420a', '- LNST chưa phân phối lũy kế đến cuối kỳ trước'), ('420b', '- LNST chưa phân phối kỳ này'),
    ('440', 'TỔNG CỘNG NGUỒN VỐN (440 = 300 + 400)'),
]
BOLD = {'100', '200', '280', '300', '400', '440', '110', '120', '130', '140', '150', '160', '210', '220', '230', '240', '250',
        '260', '270', '310', '330'}


def compute(rows):
    """rows: [(mã TK, kỳ hạn, tính chất, số dư Nợ trừ Có theo từng TK chi tiết và đối tượng)] -> {mã chỉ tiêu: số}.

    Tài khoản lưỡng tính (131, 331, 138, 338...) tách dư Nợ, dư Có theo từng đối tượng sang hai chỉ tiêu.
    Tài khoản một tính chất mà số dư ngược chiều (ví dụ 112 dư Có) là sai sót: vẫn ghi số âm vào chỉ tiêu
    để báo cáo không che mất số liệu, và được liệt kê ở cảnh báo."""
    values = {}
    for code, rules in LEAF.items():
        total = 0
        for prefixes, how, term in rules:
            for acc, acc_term, nature, bal in rows:
                if not any(acc.startswith(p) for p in prefixes):
                    continue
                if term and acc_term != term:
                    continue
                if how == 'dr':
                    total += max(bal, 0) if nature == 'both' else bal
                elif how == 'cr':
                    total += max(-bal, 0) if nature == 'both' else -bal
                elif how == 'neg':
                    total -= max(-bal, 0)
                elif how == 'ndr':
                    total -= max(bal, 0)
                elif how == 'ncr':
                    total -= bal
        values[code] = round(total)
    for code, parts in TOTALS:
        values[code] = sum(values.get(p, 0) for p in parts)
    return values


if __name__ == '__main__':
    rows = [('111', 'short', 'debit', 500), ('3311', 'short', 'both', -300), ('3311', 'short', 'both', 40),
            ('2112', 'short', 'debit', 1000), ('2141', 'short', 'credit', -100), ('4111', 'short', 'credit', -1140),
            ('33112', 'long', 'both', -200), ('4212', 'short', 'both', 200)]
    v = compute(rows)
    assert v['111'] == 500 and v['132'] == 40 and v['311'] == 300 and v['331'] == 200
    assert v['222'] == 1000 and v['223'] == -100 and v['221'] == 900
    assert v['420'] == -200 and v['411'] == 1140
    assert v['280'] == 1440 and v['440'] == 1440, (v['280'], v['440'])
    # 112 dư Có 50 (chi quá số dư) vẫn cân và ghi âm
    v = compute(rows + [('112', 'short', 'debit', -50), ('3311', 'short', 'both', 50)])
    assert v['111'] == 450 and v['280'] == v['440'], (v['111'], v['280'], v['440'])
    print('ok')
