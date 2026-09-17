"""Chỉ tiêu tờ khai thuế GTGT mẫu 01/GTGT (phương pháp khấu trừ) theo Thông tư 89/2026/TT-BTC, áp dụng từ kỳ 7/2026.

So với Thông tư 80/2021: bỏ [11b]; thêm [32b] (bán ra không tính vào giá tính thuế GTGT) và [34a] (bán ra không thuộc
phạm vi điều chỉnh của pháp luật thuế GTGT); [27] = [29] + [30] + [32] + [32a] - [32b]; [34] = [26] + [27] + [34a].
Hàng hóa, dịch vụ được giảm thuế suất 10% xuống 8% khai vào dòng thuế suất 10% ([32], [33]) theo số thuế đã giảm,
kèm Phụ lục giảm thuế GTGT theo Nghị định 174/2025/NĐ-CP."""

LABELS = [
    ('21', 'Không phát sinh hoạt động mua, bán trong kỳ'),
    ('22', 'Thuế GTGT còn được khấu trừ kỳ trước chuyển sang'),
    ('23', 'Giá trị hàng hóa, dịch vụ mua vào'), ('24', 'Thuế GTGT của hàng hóa, dịch vụ mua vào'),
    ('23a', '   Trong đó: giá trị hàng hóa nhập khẩu'), ('24a', '   Trong đó: thuế GTGT hàng hóa nhập khẩu'),
    ('25', 'Thuế GTGT của hàng hóa, dịch vụ mua vào được khấu trừ kỳ này'),
    ('26', 'Hàng hóa, dịch vụ bán ra không chịu thuế GTGT'),
    ('27', 'Hàng hóa, dịch vụ bán ra chịu thuế GTGT: giá trị ([27] = [29] + [30] + [32] + [32a] - [32b])'),
    ('28', 'Hàng hóa, dịch vụ bán ra chịu thuế GTGT: thuế ([28] = [31] + [33])'),
    ('29', 'Thuế suất 0%: giá trị'), ('30', 'Thuế suất 5%: giá trị'), ('31', 'Thuế suất 5%: thuế'),
    ('32', 'Thuế suất 10% (gồm hàng giảm còn 8%): giá trị'), ('33', 'Thuế suất 10% (gồm hàng giảm còn 8%): thuế'),
    ('32a', 'Hàng hóa, dịch vụ bán ra không phải kê khai, tính nộp thuế GTGT'),
    ('32b', 'Hàng hóa, dịch vụ bán ra không tính vào giá tính thuế GTGT'),
    ('34a', 'Hàng hóa, dịch vụ bán ra không thuộc phạm vi điều chỉnh của pháp luật thuế GTGT'),
    ('34', 'Tổng doanh thu hàng hóa, dịch vụ bán ra ([34] = [26] + [27] + [34a])'),
    ('35', 'Tổng thuế GTGT của hàng hóa, dịch vụ bán ra ([35] = [28])'),
    ('36', 'Thuế GTGT phát sinh trong kỳ ([36] = [35] - [25])'),
    ('37', 'Điều chỉnh giảm thuế GTGT còn được khấu trừ của các kỳ trước'),
    ('38', 'Điều chỉnh tăng thuế GTGT còn được khấu trừ của các kỳ trước'),
    ('39a', 'Thuế GTGT nhận bàn giao được khấu trừ'),
    ('40a', 'Thuế GTGT phải nộp của hoạt động sản xuất kinh doanh trong kỳ'),
    ('40b', 'Thuế GTGT mua vào của dự án đầu tư được bù trừ với thuế GTGT còn phải nộp'),
    ('40', 'Thuế GTGT còn phải nộp trong kỳ ([40] = [40a] - [40b])'),
    ('41', 'Thuế GTGT chưa khấu trừ hết kỳ này'),
    ('42', 'Tổng số thuế GTGT đề nghị hoàn'),
    ('43', 'Thuế GTGT còn được khấu trừ chuyển kỳ sau ([43] = [41] - [42])'),
]


def compute(purchases, sales, carry=0, adjust=None):
    """purchases: [(giá trị, thuế, được khấu trừ, là hàng nhập khẩu)];
    sales: [(giá trị, thuế, nhóm)] với nhóm: 'none' không chịu thuế, '0', '5', '10' (gồm 8%), '32a', '32b', '34a'.
    adjust: số nhập tay cho [37], [38], [39a], [40b], [42]."""
    a = dict.fromkeys(['37', '38', '39a', '40b', '42'], 0)
    a.update(adjust or {})
    v = {'22': carry}
    v['23'] = sum(p[0] for p in purchases)
    v['24'] = sum(p[1] for p in purchases)
    v['23a'] = sum(p[0] for p in purchases if p[3])
    v['24a'] = sum(p[1] for p in purchases if p[3])
    v['25'] = sum(p[1] for p in purchases if p[2])
    by = lambda g, i: sum(s[i] for s in sales if s[2] == g)
    v['26'], v['29'] = by('none', 0), by('0', 0)
    v['30'], v['31'] = by('5', 0), by('5', 1)
    v['32'], v['33'] = by('10', 0), by('10', 1)
    v['32a'], v['32b'], v['34a'] = by('32a', 0), by('32b', 0), by('34a', 0)
    v['27'] = v['29'] + v['30'] + v['32'] + v['32a'] - v['32b']
    v['28'] = v['31'] + v['33']
    v['34'] = v['26'] + v['27'] + v['34a']
    v['35'] = v['28']
    v['36'] = v['35'] - v['25']
    v.update({k: a[k] for k in ('37', '38', '39a', '40b', '42')})
    net = v['36'] - v['22'] + v['37'] - v['38'] - v['39a']
    v['40a'] = max(net, 0)
    v['40'] = max(v['40a'] - v['40b'], 0)
    v['41'] = max(-net, 0)
    v['43'] = v['41'] - v['42']
    v['21'] = 0 if purchases or sales else 1
    return {k: round(x) for k, x in v.items()}


if __name__ == '__main__':
    # mua 100 triệu thuế 8 triệu (được khấu trừ) + 20 triệu thuế 2 triệu (không đủ điều kiện); bán 200 triệu thuế 16 triệu
    v = compute([(100e6, 8e6, True, False), (20e6, 2e6, False, False)], [(200e6, 16e6, '10'), (30e6, 0, 'none')], carry=1e6)
    assert (v['23'], v['24'], v['25']) == (120e6, 10e6, 8e6), v
    assert (v['26'], v['27'], v['28'], v['34'], v['35']) == (30e6, 200e6, 16e6, 230e6, 16e6), v
    assert (v['36'], v['40a'], v['40'], v['41'], v['43']) == (8e6, 7e6, 7e6, 0, 0), v
    # kỳ chưa khấu trừ hết: mua thuế 20 triệu, bán thuế 5 triệu, kỳ trước chuyển 1 triệu
    v = compute([(250e6, 20e6, True, False)], [(50e6, 5e6, '10')], carry=1e6)
    assert (v['36'], v['40'], v['41'], v['43']) == (-15e6, 0, 16e6, 16e6), v
    # công thức mới của Thông tư 89: [32b] trừ khỏi [27], [34a] cộng vào [34]
    v = compute([], [(100, 10, '10'), (7, 0, '32b'), (5, 0, '34a')])
    assert v['27'] == 93 and v['34'] == 98, v
    print('ok')
