"""Tính toán thuần cho khuyến mại, không phụ thuộc Odoo."""
def gift_ratio(buy_qty, buy_price, gift_qty, gift_price):
    """Giá trị hàng tặng tính trên một đơn vị hàng được khuyến mại, theo % giá bán của đơn vị đó."""
    if not buy_qty or not buy_price:
        return 0.0
    return round(gift_qty * gift_price / buy_qty / buy_price * 100, 2)


def gift_quantity(ordered, buy_qty, gift_qty):
    """Mua đủ bội số của buy_qty thì được tặng tương ứng."""
    if not buy_qty:
        return 0
    return int(ordered // buy_qty) * gift_qty


if __name__ == '__main__':
    from datetime import date
    assert gift_ratio(2, 30000, 1, 30000) == 50
    assert gift_ratio(3, 30000, 1, 30000) == 33.33
    assert gift_quantity(7, 3, 1) == 2 and gift_quantity(2, 3, 1) == 0
    print('ok')
