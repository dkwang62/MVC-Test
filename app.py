# app.py
# Mobile MVC Rent Calculator – Auto-calculate + West to East sorted dropdown
import streamlit as st
import json
import pandas as pd
import math
from datetime import date, timedelta, datetime
from dataclasses import dataclass
import pytz

# =============================================
# 1. Load data_v2.json
# =============================================
@st.cache_data
def load_data():
    try:
        with open("data_v2.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("data_v2.json not found! Place it next to this app.")
        st.stop()

raw_data = load_data()

# =============================================
# 2. West → East sorting (from your utils.py)
# =============================================
COMMON_TZ_ORDER = [
    "Pacific/Honolulu", "America/Anchorage", "America/Los_Angeles", "America/Denver",
    "America/Chicago", "America/New_York", "America/Vancouver", "America/Toronto",
    "America/Aruba", "America/St_Thomas", "Asia/Denpasar", "Europe/Paris", "Asia/Bangkok"
]

def get_timezone_offset(tz_name: str) -> float:
    try:
        tz = pytz.timezone(tz_name)
        dt = datetime(2025, 1, 1)
        offset = tz.utcoffset(dt)
        return offset.total_seconds() / 3600 if offset else 0
    except:
        return 0

def sort_resorts_west_to_east(resorts):
    def key(r):
        tz = r.get("timezone", "UTC")
        priority = COMMON_TZ_ORDER.index(tz) if tz in COMMON_TZ_ORDER else 999
        return (priority, get_timezone_offset(tz), r.get("display_name", ""))
    return sorted(resorts, key=key)

# =============================================
# 3. Core Calculator Classes (your original logic)
# =============================================
@dataclass
class HolidayObj:
    name: str
    start: date
    end: date

class MVCRepository:
    def __init__(self, raw_data: dict):
        self._raw = raw_data
        self._gh = self._parse_global_holidays()

    def get_resort_list(self):
        return self._raw.get("resorts", [])

    def _parse_global_holidays(self):
        parsed = {}
        for y, holidays in self._raw.get("global_holidays", {}).items():
            parsed[y] = {}
            for name, info in holidays.items():
                parsed[y][name] = (
                    datetime.strptime(info["start_date"], "%Y-%m-%d").date(),
                    datetime.strptime(info["end_date"], "%Y-%m-%d").date(),
                )
        return parsed

    def get_resort_data(self, display_name: str):
        for r in self._raw.get("resorts", []):
            if r.get("display_name") == display_name:
                return r
        return None

class MVCCalculator:
    def __init__(self, repo):
        self.repo = repo

    def get_points(self, resort_data, day):
        y = str(day.year)
        if y not in resort_data.get("years", {}): return {}, None
        yd = resort_data["years"][y]

        for h in yd.get("holidays", []):
            ref = h.get("global_reference")
            if ref and ref in self.repo._gh.get(y, {}):
                start, end = self.repo._gh[y][ref]
                if start <= day <= end:
                    return h.get("room_points", {}), HolidayObj(h.get("name"), start, end)

        dow =
