import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

def get_ist_now() -> datetime.datetime:
    """Returns the current datetime in IST."""
    return datetime.datetime.now(IST)

def get_ist_date_string() -> str:
    """Returns the current IST date in YYYY-MM-DD format."""
    return get_ist_now().strftime("%Y-%m-%d")

def time_based_greeting(name: str, hour: int) -> str:
    """Returns a time-appropriate greeting."""
    import html
    name_clean = html.escape(name).upper()
    if 5 <= hour < 12:
        return f"<b>GOOD MORNING, {name_clean}!</b>\n\n"
    elif 12 <= hour < 17:
        return f"<b>GOOD AFTERNOON, {name_clean}!</b>\n\n"
    else:
        return f"<b>GOOD EVENING, {name_clean}!</b>\n\n"
