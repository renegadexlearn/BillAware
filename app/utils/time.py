# app/utils/time.py

from datetime import date, datetime, time, timezone
import pytz

PH_TZ = pytz.timezone("Asia/Manila")

def format_date_ph(value):
    """Format date/datetime as 04-JAN-26 in PH time."""
    if value is None:
        return ""

    # If it's a date (but not a datetime), format directly (no timezone to convert)
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime("%d-%b-%y").upper()

    # Now it's a datetime
    if value.tzinfo is None:
        # assume UTC for naive datetimes
        value = value.replace(tzinfo=timezone.utc)

    value_ph = value.astimezone(PH_TZ)
    return value_ph.strftime("%d-%b-%y").upper()
