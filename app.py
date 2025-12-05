# calculator_with_west_to_east.py
# Your original calculator + West → East auto-adjustment
# Fully self-contained – just put data_v2.json in the same folder

import streamlit as st
import json
import pandas as pd
import math
from datetime import date, timedelta, datetime
from dataclasses import dataclass
from enum import Enum
import pytz

# --------------------------------------------------------------
# 1. Load data_v2.json
# --------------------------------------------------------------
@st.cache_data
def load_data():
    try:
        with open("data_v2.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("data_v2.json not found in the same folder!")
        st.stop()

raw_data = load_data()

# --------------------------------------------------------------
# 2. Core classes (exactly as in your original)
# --------------------------------------------------------------
class UserMode(Enum):
    RENTER = "Renter"
    OWNER = "Owner"

@dataclass
class HolidayObj:
    name: str
    start: date
    end: date

@dataclass
class CalculationResult:
    breakdown_df: pd.DataFrame
    total_points: int
    financial_total: float
    discount_applied: bool
    m_cost: float = 0.0
    c_cost: float = 0.0
    d_cost: float = 0.0

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

        # Holiday first
        for h in yd.get("holidays", []):
            ref = h.get("global_reference")
            if ref and ref in self.repo._gh.get(y, {}):
                start, end = self.repo._gh[y][ref]
                if start <= day <= end:
                    return h.get("room_points", {}), HolidayObj(h.get("name"), start, end)

        dow_map = {0:"Mon",1:"Tue",2:"Wed",3:"Thu",4:"Fri",5:"Sat",6:"Sun"}
        dow = dow_map[day.weekday()]

        for season in yd.get("seasons", []):
            for period in season.get("periods", []):
                try:
                    ps = datetime.strptime(period["start"], "%Y-%m-%d").date()
                    pe = datetime.strptime(period["end"], "%Y-%m-%d").date()
                    if ps <= day <= pe:
                        for cat in season.get("day_categories", {}).values():
                            if dow in cat.get("day_pattern", []):
                                return cat.get("room_points", {}), None
                except:
                    continue
        return {}, None

    def calculate(self, resort_name, room, checkin, nights, rate, discount_mul):
        r_data = self.repo.get_resort_data(resort_name)
        if not r_data: return None

        rate = round(float(rate), 2)
        rows = []
        total_pts = 0
        disc_applied = False
        processed_holidays = set()

        i = 0
        while i < nights:
            d = checkin + timedelta(days=i)
            pts_map, holiday = self.get_points(r_data, d)

            if holiday and holiday.name not in processed_holidays:
                processed_holidays.add(holiday.name)
                raw = int(pts_map.get(room, 0))
                eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
                if eff < raw: disc_applied = True

                rows.append({
                    "Date": f"{holiday.name} ({holiday.start.strftime('%b %d')}–{holiday.end.strftime('%b %d')})",
                    "Pts": eff,
                    "Cost": f"${math.ceil(eff * rate):,}"
                })
                total_pts += eff
                i += (holiday.end - holiday.start).days + 1
            else:
                raw = int(pts_map.get(room, 0))
                eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
                if eff < raw: disc_applied = True

                rows.append({
                    "Date": d.strftime("%a %b %d"),
                    "Pts": eff,
                    "Cost": f"${math.ceil(eff * rate):,}"
                })
                total_pts += eff
                i += 1

        total_cost = round(total_pts * rate, 2)
        return CalculationResult(pd.DataFrame(rows), total_pts, total_cost, disc_applied)

# --------------------------------------------------------------
# 3. West → East auto-adjustment (same logic you love)
# --------------------------------------------------------------
def adjust_checkin_for_timezone(resort_tz: str, original_checkin: date) -> date:
    if resort_tz not in pytz.all_timezones:
        return original_checkin

    resort_time = datetime.combine(original_checkin, datetime.min.time()).replace(tzinfo=pytz.UTC)
    resort_local = resort_time.astimezone(pytz.timezone(resort_tz))
    return resort_local.date()

# --------------------------------------------------------------
# 4. Initialise
# --------------------------------------------------------------
repo = MVCRepository(raw_data)
calc = MVCCalculator(repo)
resorts = [r["display_name"] for r in repo.get_resort_list()]

st.set_page_config(page_title="MVC Rent Calc", layout="centered")
st.title("MVC Rent Calculator")
st.caption("Mobile-friendly • West → East auto-adjusted • Renter mode")

resort = st.selectbox("Resort", resorts)

# Get resort timezone
resort_data = repo.get_resort_data(resort)
resort_tz = resort_data.get("timezone", "America/New_York") if resort_data else "America/New_York"

# Room types
available_rooms = set()
for ydata in resort_data.get("years", {}).values():
    for s in ydata.get("seasons", []):
        for cat in s.get("day_categories", {}).values():
            available_rooms.update(cat.get("room_points", {}).keys())
rooms = sorted(list(available_rooms)) if available_rooms else []

room = st.selectbox("Room Type", rooms) if rooms else st.write("No rooms found")

col1, col2 = st.columns(2)
raw_checkin = col1.date_input("Check-in (your time)", date.today() + timedelta(days=7))
nights = col2.number_input("Nights", 1, 60, 7)

# WEST → EAST ADJUSTMENT
adjusted_checkin = adjust_checkin_for_timezone(resort_tz, raw_checkin)

if adjusted_checkin != raw_checkin:
    st.info(f"Check-in adjusted → **{adjusted_checkin.strftime('%a %b %d, %Y')}** ({resort_tz.split('/')[-1].replace('_', ' ')} time)")

checkin_to_use = adjusted_checkin

rate = st.number_input("Rent Rate ($/pt)", 0.30, 1.50, 0.55, 0.05, format="%.2f")

discount = st.selectbox("Discount", 
    ["No Discount", "Executive (25% off)", "Presidential (30% off)"])
mul = 1.0 if "No" in discount else 0.75 if "Exec" in discount else 0.70

if st.button("Calculate", type="primary", use_container_width=True):
    result = calc.calculate(resort, room, checkin_to_use, nights, rate, mul)

    if result:
        c1, c2 = st.columns(2)
        c1.metric("Total Points", f"{result.total_points:,}")
        c2.metric("Total Cost", f"${result.financial_total:,.2f}")

        if result.discount_applied:
            st.success("Discount Applied!")

        st.dataframe(result.breakdown_df, use_container_width=True, hide_index=True)

        csv = result.breakdown_df.to_csv(index=False)
        st.download_button("Download Breakdown", csv,
            f"{resort}_{checkin_to_use}_{nights}nights.csv", "text/csv")

st.caption("data_v2.json auto-loaded • West → East adjustment active")
