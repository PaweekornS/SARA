"""
รูปแบบวันที่ภาษาไทย (พ.ศ.)
"""

from __future__ import annotations

from datetime import date

# ── Global Variables & Constants ─────────────────────────────────────────────

THAI_MONTHS = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
]

THAI_MONTHS_SHORT = [
    "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
]

# ── Functions ────────────────────────────────────────────────────────────────

def thai_date(value: date | None, short: bool = False) -> str:
    """พ.ศ. = ค.ศ. + 543"""
    if value is None:
        return "-"
    month = THAI_MONTHS_SHORT[value.month - 1] if short else THAI_MONTHS[value.month - 1]
    return f"{value.day} {month} {value.year + 543}"
