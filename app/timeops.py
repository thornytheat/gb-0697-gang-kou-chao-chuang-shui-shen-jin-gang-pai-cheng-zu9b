from datetime import datetime,timezone
from decimal import Decimal
from app.errors import BusinessError

def instant(text):
    try:d=datetime.fromisoformat(text.replace("Z","+00:00"))
    except ValueError:raise BusinessError("TIME","时间格式无效")
    if d.tzinfo is None:raise BusinessError("TIMEZONE","时间须带时区")
    return Decimal(str(d.timestamp()))

def display(seconds):return datetime.fromtimestamp(float(seconds),timezone.utc).strftime("%m-%d %H:%M UTC")

def display_full(seconds):
    if seconds is None:return "—"
    return datetime.fromtimestamp(float(seconds),timezone.utc).strftime("%Y-%m-%d %H:%M")
