# common/utils.py
import pytz
from datetime import datetime
from typing import List, Dict, Any

COMMON_TZ_ORDER = [
    "Pacific/Honolulu", "America/Anchorage", "America/Los_Angeles", "America/Denver",
    "America/Chicago", "America/New_York", "America/Vancouver", "America/Edmonton",
    "America/Winnipeg", "America/Toronto", "America/Halifax", "America/St_Johns",
    "US/Hawaii", "US/Alaska", "US/Pacific", "US/Mountain", "US/Central", "US/Eastern",
    "America/Aruba", "America/St_Thomas", "Asia/Denpasar",
]

def get_timezone_offset(tz_name: str) -> float:
    try:
        tz = pytz.timezone(tz_name)
        return tz.utcoffset(datetime(2025, 1, 1)).total_seconds() / 3600
    except:
        return 0

def sort_resorts_west_to_east(resorts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(r):
        tz = r.get("timezone", "UTC")
        priority = COMMON_TZ_ORDER.index(tz) if tz in COMMON_TZ_ORDER else 9999
        return (priority, get_timezone_offset(tz), (r.get("address") or r.get("display_name", "")).lower())
    return sorted(resorts, key=key)
