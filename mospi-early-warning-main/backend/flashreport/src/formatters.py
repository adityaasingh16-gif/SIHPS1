"""Deterministic number / date formatting used across the whole report.

* KPI cards / prose:  Indian digit grouping with a space after the rupee sign
  -> "₹ 33,70,138".
* Tables:             international grouping, two decimals -> "3,370,138.22".
* Chart axes/labels:  one decimal, expressed in ₹ lakh crore or ₹ thousand crore.
* Dates: MM/YYYY.     Percentages: up to two decimals.
"""
from __future__ import annotations

import re

_RUPPEE = "\u20b9"

# --------------------------------------------------------------------------
# Indian digit grouping
# --------------------------------------------------------------------------


def _indian_groups(digits: str) -> str:
    if len(digits) <= 3:
        return digits
    head = digits[:-3]
    tail = digits[-3:]
    groups: list[str] = [tail]
    while head:
        groups.append(head[-2:] if len(head) > 2 else head)
        head = head[:-2]
    return ",".join(reversed(groups))


def inr(value: float, decimals: int = 0, prefix: str | None = None) -> str:
    """Indian grouped currency, e.g. ``format_inr(3370138.0) -> '₹ 33,70,138'``."""
    if value is None:
        value = 0.0
    neg = value < 0
    whole, sep, frac = f"{abs(value):.{decimals}f}".partition(".")
    text = _indian_groups(whole)
    if frac:
        text = f"{text}.{frac}"
    sign = "-" if neg else ""
    prefix = _RUPPEE if prefix is None else prefix
    return f"{sign}{prefix} {text}"


def intl(value: float, decimals: int = 2) -> str:
    """International digit grouping with fixed decimals: ``336,914.20``."""
    if value is None:
        value = 0.0
    return f"{value:,.{decimals}f}"


def pct(value: float, force_sign: bool = False) -> str:
    text = f"{value:.{2}f}" if abs(value) >= 0.005 else "0.00"
    text = text.rstrip("0").rstrip(".")
    if "." not in text:
        text += ".00"
    if force_sign and value > 0:
        return f"+{text}%"
    return f"{text}%"


def signed(value: float) -> str:
    """Signed integer delta with '+' for positive numbers."""
    if value > 0:
        return f"+{int(value):,}"
    return f"{int(value):,}"


# --------------------------------------------------------------------------
# Large-number units
# --------------------------------------------------------------------------


def lakh_crore(value: float, decimals: int = 1) -> str:
    """₹ crore value expressed in lakh crore (1 lakh crore = 100 000 crore)."""
    return f"{value / 100_000:,.{decimals}f}"


def thousand_crore(value: float, decimals: int = 1) -> str:
    """₹ crore value expressed in thousand crore (1 TCr = 1000 crore)."""
    return f"{value / 1_000:,.{decimals}f}"


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

_MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}
_MONTH_SHORT = {k: v[:3].upper() for k, v in _MONTHS.items()}


def mm_yyyy(value: str) -> str:
    """Normalise any 'MM/YYYY' / 'MM-YYYY' / 'MMYYYY' / 'YYYY-MM' to 'MM/YYYY'.

    Empty / missing values render as '-'.
    """
    if not value:
        return "-"
    v = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", v):          # YYYY-MM / YYYY-MM-DD
        return f"{v[5:7]}/{v[0:4]}"
    m = re.search(r"(\d{1,2})[/\-.](\d{4})", v)
    if m:
        return f"{m.group(1).zfill(2)}/{m.group(2)}"
    m = re.search(r"(\d{4})(\d{2})", v)
    if m:
        return f"{m.group(2)}/{m.group(1)}"
    if re.fullmatch(r"\d{2}/\d{4}", v):
        return v
    return v if v else "-"


def _month_val(m: str) -> int:
    try:
        return int(m)
    except (TypeError, ValueError):
        return 0


def ordinal(value: int) -> str:
    """1 -> '1st', 2 -> '2nd', 3 -> '3rd', 11-13 -> 'Nth', else 'Nth'."""
    n = int(value)
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def month_label(value: str) -> str:
    m = mm_yyyy(value)
    if m == "-":
        return m
    mm, yyyy = m.split("/")
    return _MONTHS.get(mm, mm).upper() + " " + yyyy


def month_short(value: str) -> str:
    m = mm_yyyy(value)
    if m == "-":
        return m
    return m


def state_group(state: str) -> str:
    ne = {
        "Arunachal Pradesh", "Assam", "Manipur", "Meghalaya",
        "Mizoram", "Nagaland", "Sikkim", "Tripura",
    }
    return "North East" if state.strip() in ne else "Other"