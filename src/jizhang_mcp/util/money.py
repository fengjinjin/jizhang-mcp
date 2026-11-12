from decimal import Decimal, ROUND_HALF_UP


def quantize_money(value: Decimal | float | str) -> Decimal:
    d = Decimal(str(value))
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def money_str(value: Decimal) -> str:
    return f"{quantize_money(value):.2f}"
