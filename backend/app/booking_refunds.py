"""Calculate confirmed-ticket cancellation charges and passenger refunds.

This models the standard Indian Railways confirmed-ticket time bands. AC
cancellation charges include the configured 5% GST; actual payment-provider
refund execution is deliberately handled by a separate workflow.
"""
from decimal import Decimal, ROUND_HALF_UP

MONEY = Decimal("0.01")
GST_RATE = Decimal("0.05")
FLAT_CHARGES = {
    "1A": Decimal("240.00"), "EC": Decimal("240.00"),
    "2A": Decimal("200.00"), "FC": Decimal("200.00"),
    "3A": Decimal("180.00"), "3E": Decimal("180.00"),
    "CC": Decimal("180.00"),
    "SL": Decimal("120.00"),
    "2S": Decimal("60.00"),
}
AC_CLASSES = {"1A", "EC", "2A", "FC", "3A", "3E", "CC"}


def _money(value):
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def calculate_cancellation_refund(fare, class_code, hours_until_departure):
    """Return a deterministic cancellation charge/refund breakdown.

    Confirmed-ticket policy:
    - More than 48 hours: flat class charge per passenger.
    - 12 to 48 hours: 25% of fare, subject to the flat minimum.
    - 4 to less than 12 hours: 50% of fare, subject to the flat minimum.
    - Less than 4 hours: no refund.
    """
    amount = _money(fare)
    if amount < 0:
        raise ValueError("Fare cannot be negative.")
    if not isinstance(class_code, str) or class_code.strip().upper() not in FLAT_CHARGES:
        raise ValueError("Unsupported ticket class for refund calculation.")
    try:
        hours = Decimal(str(hours_until_departure))
    except Exception:
        raise ValueError("A valid departure time is required.") from None
    if not hours.is_finite():
        raise ValueError("A valid departure time is required.")

    code = class_code.strip().upper()
    flat = FLAT_CHARGES[code]
    if hours < Decimal("4"):
        charge = amount
        band = "NO_REFUND_UNDER_4_HOURS"
    elif hours < Decimal("12"):
        charge = max(amount * Decimal("0.50"), flat)
        band = "50_PERCENT_4_TO_12_HOURS"
    elif hours < Decimal("48"):
        charge = max(amount * Decimal("0.25"), flat)
        band = "25_PERCENT_12_TO_48_HOURS"
    else:
        charge = flat
        band = "FLAT_OVER_48_HOURS"

    if code in AC_CLASSES and charge < amount and hours >= Decimal("4"):
        charge *= (Decimal("1.00") + GST_RATE)
    charge = min(amount, _money(charge))
    refund = _money(amount - charge)
    return {
        "fare": amount,
        "cancellation_charge": charge,
        "refund_amount": refund,
        "policy_band": band,
        "currency_code": "INR",
    }
