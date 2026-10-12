import re


def normalize_phone(raw: str | None):
    """Return +<digits> or None. 10-digit Indian mobiles get +91."""
    s = re.sub(r"[\s\-\(\)\.]", "", raw or "")
    if s.startswith("00"):
        s = "+" + s[2:]
    if re.fullmatch(r"[6-9]\d{9}", s):
        s = "+91" + s
    elif re.fullmatch(r"91[6-9]\d{9}", s):
        s = "+" + s
    return s if re.fullmatch(r"\+\d{10,15}", s) else None


def wa_link(phone: str | None):
    digits = re.sub(r"\D", "", phone or "")
    return f"https://wa.me/{digits}" if digits else ""
