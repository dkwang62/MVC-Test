# app.py
# Simple Mobile MVC Rent Calculator – loads data_v2.json automatically
# Works perfectly on phones – no extra files, no saving/loading profiles

import streamlit as st
import json
import pandas as pd
import math
from datetime import date, timedelta, datetime
from dataclasses import dataclass
from enum import Enum

# --------------------------------------------------------------
# 1. AUTO-LOAD data_v2.json
# --------------------------------------------------------------
@st.cache_data
def load_data():
    try:
        with open("data_v2.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("data_v2.json not found! Place it in the same folder as this app.")
        st.stop()
    except json.JSONDecodeError:
        st.error("data_v2.json is corrupted or invalid JSON.")
        st.stop()

raw_data = load_data()

# --------------------------------------------------------------
# 2. Minimal required classes (exact copies from your original code)
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
 Rc   total_points: int
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
        if y not in resort_data.get("years", {}):
            return {}, None
        yd = resort_data["years"][y]

        # Holiday first
        for h in yd.get("holidays", []):
            ref = h.get("global_reference")
            if ref and ref in self.repo._gh.get(y, {}):
                start, end = self.repo._gh[y][ref]
                if start <= day <= end:
                    return h.get("room_points", {}), HolidayObj(h.get("name"), start, end)

        # Regular season
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
        if not r_data:
            return None

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
                if eff < raw:
                    disc_applied = True

                rows.append({
                    "Date": f"{holiday.name} ({holiday.start.strftime('%b %d')}–{holiday.end.strftime('%b %d')})",
                    "Pts": eff,
                    "Cost": f"${math.ceil(eff * rate):,}"
                })
                total_pts += eff

                # skip the whole block
                i += (holiday.end - holiday.start).days + 1
            else:
                raw = int(pts_map.get(room, 0))
                eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
                if eff < raw:
                    disc_applied = True

                rows.append({
                    "Date": d.strftime("%a %b %d"),
                    "Pts": eff,
                    "Cost": f"${math.ceil(eff * rate):,}"
                })
                total_pts += eff
                i += 1

        total_cost = round(total_pts * rate, 2)
        df = pd.DataFrame(rows)

        return CalculationResult(df, total_pts, total_cost, disc_applied)

# --------------------------------------------------------------
# 3. Initialise calculator
# --------------------------------------------------------------
repo = MVCRepository(raw_data)
calc = MVCCalculator(repo)
resorts = [r["display_name"] for r in repo.get_resort_list()]

# --------------------------------------------------------------
# 4. Streamlit UI – mobile friendly
# --------------------------------------------------------------
st.set_page_config(page_title="MVC Rent Calc", layout="centered")
st.title("MVC Rent Calculator")
st.caption("Mobile-friendly • Renter mode • Auto-loads data_v2.json")

# Resort
resort = st.selectbox("Resort", options=resorts, index=0)

# Get available rooms for the selected resort (any year that has data)
r_data = repo.get_resort_data(resort)
available_rooms = set()
for year_data in r_data.get("years", {}).values():
    for season in year_data.get("seasons", []):
        for cat in season.get("day_categories", {}).values():
            available_rooms.update(cat.get("room_points", {}).keys())
rooms = sorted(list(available_rooms))

if not rooms:
    st.error("No room data found for this resort.")
    st.stop()

room = st.selectbox("Room Type", rooms)

col1, col2 = st.columns(2)
checkin = col1.date_input("Check-in", date.today() + timedelta(days=7))
nights  = col2.number_input("Nights", 1, 60, 7, step=1)

rate = st.number_input("Rent Rate ($ per point)", 0.30, 1.50, 0.55, 0.05, format="%.2f")

discount = st.selectbox("Discount Tier", 
    ["No Discount", "Executive (25% off)", "Presidential (30% off)"])
mul = 1.0
if "Executive" in discount:
    mul = 0.75
elif "Presidential" in discount:
    mul = 0.70

if st.button("Calculate", type="primary", use_container_width=True):
    result = calc.calculate(resort, room, checkin, nights, rate, mul)
    
    if result:
        c1, c2 = st.columns(2)
        c1.metric("Total Points", f"{result.total_points:,}")
        c2.metric("Total Rent", f"${result.financial_total:,.2f}")
        
        if result.discount_applied:
            st.success("Discount Applied!")
        
        st.dataframe(result.breakdown_df, use_container_width=True, hide_index=True)
        
        st.download_button(
            "Download Result",
            data=result.breakdown_df.to_csv(index=False),
            file_name=f"{resort.replace(' ', '_')}_{checkin}_{nights}nights.csv",
            mime="text/csv"
        )

st.markdown("---")
st.caption("Place data_v2.json in the same folder • Works on iPhone & Android")
