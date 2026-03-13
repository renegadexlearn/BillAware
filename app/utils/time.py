# app/utils/time.py

from datetime import date, datetime, timezone
import pytz

PH_TZ = pytz.timezone("Asia/Manila")


def _to_ph_datetime(value):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time()).replace(tzinfo=PH_TZ)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(PH_TZ)


def format_date_ph(value):
    """Format date/datetime as 13-Mar-2026 in PH time."""
    if value is None:
        return ""

    if isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime("%d-%b-%Y")

    value_ph = _to_ph_datetime(value)
    return value_ph.strftime("%d-%b-%Y")


def format_datetime_ph(value):
    """Format date/datetime as 13-Mar-2026 12:30:42 PM in PH time."""
    if value is None:
        return ""
    value_ph = _to_ph_datetime(value)
    return value_ph.strftime("%d-%b-%Y %I:%M:%S %p")


def format_ph_value(value):
    if isinstance(value, datetime):
        return format_datetime_ph(value)
    if isinstance(value, date):
        return format_date_ph(value)
    return value
