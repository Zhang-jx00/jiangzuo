"""按汇率把金额从一种币种换算成另一种币种。

用法：
    from calc import convert
    convert(100, "USD", "CNY")
"""

import json
import os

RATES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rates.json")


def _rates():
    with open(RATES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def convert(amount, frm, to):
    """把 amount 从 frm 币种换算成 to 币种，返回四舍五入到分的数值。"""
    rates = _rates()
    rate = rates[to] / rates[frm]
    return round(amount * rate, 2)


def supported():
    """列出当前支持的币种。"""
    return sorted(_rates().keys())


if __name__ == "__main__":
    print(convert(100, "USD", "CNY"))
