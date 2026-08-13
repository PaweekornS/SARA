"""รูปแบบวันที่และตัวเลขตามระเบียบสารบรรณ — ใช้ร่วมกันระหว่างร่างวาระและไฟล์ .docx"""

from __future__ import annotations

from datetime import date

THAI_MONTHS = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
]

THAI_DIGITS = "๐๑๒๓๔๕๖๗๘๙"


def thai_date(value: date | None, short: bool = False) -> str:
    """พ.ศ. = ค.ศ. + 543"""
    if value is None:
        return "-"
    month = THAI_MONTHS[value.month - 1]
    if short:
        month = month[:3] + "."
    return f"{value.day} {month} {value.year + 543}"


def thai_numeral(value) -> str:
    return "".join(THAI_DIGITS[int(ch)] if ch.isdigit() else ch for ch in str(value))


def fiscal_year_of(value: date) -> int:
    """ปีงบประมาณไทยเริ่ม 1 ตุลาคม — ต.ค. 2026 จึงอยู่ในปีงบ 2570"""
    return value.year + 543 + (1 if value.month >= 10 else 0)
