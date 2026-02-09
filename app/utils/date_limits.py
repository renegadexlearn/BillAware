from datetime import date, timedelta
from flask import current_app


def allowed_date_range():
    """
    Allowed range:
    - min = today - MAX_BACKDATE_DAYS
    - max = today
    """
    days = current_app.config["MAX_BACKDATE_DAYS"]
    today = date.today()
    return today - timedelta(days=days), today
