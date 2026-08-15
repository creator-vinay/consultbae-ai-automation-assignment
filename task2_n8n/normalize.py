"""
normalize.py
Small helper functions to clean up the messy fields we saw across the
3 source files (phones in 3 different formats, cities with casing/whitespace
issues, dates in 4 different formats, CTC mixing rupees and lakhs, rate
mixing per-hour and per-month).

Kept as plain functions (no classes) so it's easy to unit-test / explain
each one on its own in the video.
"""
import re
from dateutil import parser as dateparser

# Known aliases for the same real-world city written differently
CITY_ALIASES = {
    "gurgaon": "gurugram",
    "gurugram": "gurugram",
    "bangalore": "bengaluru",
    "bengaluru": "bengaluru",
    "new delhi": "delhi",
    "delhi ncr": "delhi",
    "delhi": "delhi",
    "noida": "noida",
    "pune": "pune",
}


def normalize_email(raw):
    if raw is None:
        return None
    e = str(raw).strip().lower()
    return e if e else None


def normalize_phone(raw):
    """Strip +91 / 91 / 0 prefixes and any punctuation, keep last 10 digits."""
    if raw is None:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) < 10:
        return None
    return digits[-10:]


def normalize_city(raw):
    if raw is None:
        return None
    c = str(raw).strip().lower()
    c = re.sub(r"\s+", " ", c)
    if not c:
        return None
    return CITY_ALIASES.get(c, c)


def normalize_name(raw):
    if raw is None:
        return None
    n = str(raw).strip()
    n = re.sub(r"\s+", " ", n)
    return n.title()


def name_key(raw):
    """A loose key used ONLY to flag possible duplicates for manual review,
    never to auto-merge (too risky - see data issues report)."""
    if raw is None:
        return None
    n = re.sub(r"[.\s]+", " ", str(raw).strip().lower())
    return n.strip()


def normalize_date(raw):
    if raw is None or str(raw).strip() == "":
        return None
    try:
        dt = dateparser.parse(str(raw), dayfirst=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def normalize_ctc(raw):
    """Source1 CTC column mixes full annual rupee figures (e.g. 417964)
    with what look like lakhs written as a bare decimal (e.g. 4.2).
    Heuristic: anything under 100 is treated as lakhs and scaled up."""
    if raw is None or str(raw).strip() == "":
        return None
    try:
        val = float(raw)
    except ValueError:
        return None
    if val < 100:
        return round(val * 100000, 2)
    return round(val, 2)


def normalize_rate_to_hourly(raw):
    """Source2 rate mixes '<num>/hr' and '<num>k/month'.
    Assumption (documented): 160 working hours/month to convert monthly -> hourly."""
    if raw is None:
        return None, None
    s = str(raw).strip().lower()
    m = re.match(r"([\d.]+)\s*/\s*hr", s)
    if m:
        return round(float(m.group(1)), 2), "hr"
    m = re.match(r"([\d.]+)\s*k\s*/\s*month", s)
    if m:
        monthly = float(m.group(1)) * 1000
        return round(monthly / 160, 2), "month"
    return None, None


def normalize_status(raw):
    if raw is None:
        return None
    return str(raw).strip().lower()


def normalize_verified(raw):
    if raw is None:
        return None
    v = str(raw).strip().lower()
    if v in ("y", "yes"):
        return 1
    if v in ("n", "no"):
        return 0
    return None
