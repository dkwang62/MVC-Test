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

        dow = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][day.weekday()]
        for season in yd.get("seasons", []):
            for period in season.get("periods", []):
                try:
                    ps = datetime.strptime(period["start"], "%Y-%m-%d").date()
                    pe = datetime.strptime(period["end"], "%Y-%m-%d").date()
                    if ps <= day <= pe:
                        for cat in season.get("day_categories", {}).values():
                            if dow in cat.get("day_pattern", []):
                                return cat.get("room_points", {}), None
                except: continue
        return {}, None

    def calculate(self, resort_name, room, checkin, nights, rate, discount_mul):
        r_data = self.repo.get_resort_data(resort_name)
        if not r_data: return None

        rate = round(float(rate), 2)
        rows = []
        total_pts = 0
        disc_applied = False
        processed = set()

        i = 0
        while i < nights:
            d = checkin + timedelta(days=i)
            pts_map, holiday = self.get_points(r_data, d)

            if holiday and holiday.name not in processed:
                processed.add(holiday.name)
                raw = int(pts_map.get(room, 0))
                eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
                if eff < raw: disc_applied = True
                rows.append({"Date": f"{holiday.name} ({holiday.start.strftime('%b %d')}–{holiday.end.strftime('%b %d')})", "Pts": eff})
                total_pts += eff
                i += (holiday.end - holiday.start).days + 1
            else:
                raw = int(pts_map.get(room, 0))
                eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
                if eff < raw: disc_applied = True
                rows.append({"Date": d.strftime("%a %b %d"), "Pts": eff})
                total_pts += eff
                i += 1

        total_cost = round(total_pts * rate, 2)
        return type('Result', (), {
            'breakdown_df': pd.DataFrame(rows),
            'total_points': total_pts,
            'financial_total': total_cost,
            'discount_applied': disc_applied
        })()

# =============================================
# 4. Initialize
# =============================================
repo = MVCRepository(raw_data)
calc = MVCCalculator(repo)
all_resorts = repo.get_resort_list()
sorted_resorts = sort_resorts_west_to_east(all_resorts)
resort_options = [r["display_name"] for r in sorted_resorts]

# =============================================
# 5. Mobile UI – Auto Calculate
# =============================================
st.set_page_config(page_title="MVC Rent", layout="centered")
st.title("MVC Rent Calculator")
st.caption("Auto-calculate • West to East • Mobile friendly")

# Resort dropdown (West to East)
resort = st.selectbox("Resort (West to East)", resort_options)

# Get resort data
resort_data = repo.get_resort_data(resort)
timezone = resort_data.get("timezone", "America/New_York") if resort_data else "America/New_York"

# Room types
rooms = set()
for y in resort_data.get("years", {}).values():
    for s in y.get("seasons", []):
        for c in s.get("day_categories", {}).values():
            rooms.update(c.get("room_points", {}).keys())
room = st.selectbox("Room Type", sorted(rooms))

col1, col2 = st.columns(2)
checkin_input = col1.date_input("Check-in (your time)", date.today() + timedelta(days=7))
nights = col2.number_input("Nights", 1, 60, 7, step=1)

# West to East adjustment
def adjust_to_resort_time(user_date: date, tz_str: str) -> date:
    try:
        utc_dt = datetime.combine(user_date, datetime.min.time()).replace(tzinfo=pytz.UTC)
        local_dt = utc_dt.astimezone(pytz.timezone(tz_str))
        return local_dt.date()
    except:
        return user_date

checkin = adjust_to_resort_time(checkin_input, timezone)

if checkin != checkin_input:
    st.info(f"Adjusted to resort time: **{checkin.strftime('%a %b %d, %Y')}**")

rate = st.number_input("Rent Rate ($/pt)", 0.30, 1.50, 0.55, 0.05, format="%.2f")

discount = st.selectbox("Discount", 
    ["No Discount", "Executive (25% off)", "Presidential (30% off)"])
mul = 1.0 if "No" in discount else 0.75 if "Exec" in discount else 0.70

# Auto-calculate on any change
if resort and room and nights >= 1:
    result = calc.calculate(resort, room, checkin, nights, rate, mul)
    if result:
        c1, c2 = st.columns(2)
        c1.metric("Total Points", f"{result.total_points:,}")
        c2.metric("Total Cost", f"${result.financial_total:,.2f}")

        if result.discount_applied:
            st.success("Discount Applied!")

        st.dataframe(result.breakdown_df, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("data_v2.json auto-loaded • Real-time calculation • West to East")
