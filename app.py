"""
MVC Calculator v2.0 – FINAL & BULLETPROOF
Perfect Renter (Rent) vs Owner (Cost) separation
No errors, clean charts, works every time
"""
import streamlit as st
import math
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import plotly.express as px

# ====================================================================
# MODELS & DATA
# ====================================================================
class DiscountLevel(Enum):
    NONE = (0, "No Discount")
    EXECUTIVE = (25, "Executive (25% off, within 30 days)")
    PRESIDENTIAL = (30, "Presidential (30% off, within 60 days)")

    def __init__(self, percentage: int, description: str):
        self.percentage = percentage
        self.description = description

    @property
    def multiplier(self) -> float:
        return 1 - (self.percentage / 100)

@dataclass
class HolidayPeriod:
    name: str
    start_date: datetime.date
    end_date: datetime.date
    room_points: Dict[str, int]
    def contains(self, date: datetime.date) -> bool: return self.start_date <= date <= self.end_date
    def is_start(self, date: datetime.date) -> bool: return date == self.start_date

@dataclass
class SeasonPeriod:
    name: str
    start_date: datetime.date
    end_date: datetime.date
    day_categories: Dict[str, Any]
    def contains(self, date: datetime.date) -> bool: return self.start_date <= date <= self.end_date

@dataclass
class DailyPointsData:
    date: datetime.date
    day_of_week: str
    room_points: Dict[str, int]
    holiday: Optional[HolidayPeriod] = None
    def get_points(self, room_type: str) -> int: return self.room_points.get(room_type, 0)

class DataRepository:
    def __init__(self, data: Dict[str, Any]):
        self._data = data
        self._cache = {}
        self._points_cache = {}
        self._resorts_by_name = {r["display_name"]: r for r in data.get("resorts", [])}

    @property
    def resort_names(self) -> List[str]: return sorted(self._resorts_by_name.keys())

    def get_maintenance_rate(self, year: int) -> float:
        return self._data.get("configuration", {}).get("maintenance_rates", {}).get(str(year), 0.86)

    def get_resort_data(self, resort_name: str): return self._resorts_by_name.get(resort_name)

    def get_holidays(self, resort_name: str, year: int) -> List[HolidayPeriod]:
        key = f"h_{resort_name}_{year}"
        if key in self._cache: return self._cache[key]
        resort = self.get_resort_data(resort_name)
        if not resort: return []
        holidays = []
        for h in resort.get("years", {}).get(str(year), {}).get("holidays", []):
            if "global_reference" in h:
                gh = self._data.get("global_holidays", {}).get(str(year), {}).get(h["global_reference"])
                if gh:
                    s = datetime.strptime(gh["start_date"], "%Y-%m-%d").date()
                    e = datetime.strptime(gh["end_date"], "%Y-%m-%d").date()
                    holidays.append(HolidayPeriod(h["name"], s, e, h.get("room_points", {})))
            else:
                s = datetime.strptime(h["start_date"], "%Y-%m-%d").date()
                e = datetime.strptime(h["end_date"], "%Y-%m-%d").date()
                holidays.append(HolidayPeriod(h["name"], s, e, h.get("room_points", {})))
        self._cache[key] = holidays
        return holidays

    def get_seasons(self, resort_name: str, year: int) -> List[SeasonPeriod]:
        key = f"s_{resort_name}_{year}"
        if key in self._cache: return self._cache[key]
        resort = self.get_resort_data(resort_name)
        if not resort: return []
        seasons = []
        for s in resort.get("years", {}).get(str(year), {}).get("seasons", []):
            for p in s.get("periods", []):
                start = datetime.strptime(p["start"], "%Y-%m-%d").date()
                end = datetime.strptime(p["end"], "%Y-%m-%d").date()
                seasons.append(SeasonPeriod(s["name"], start, end, s.get("day_categories", {})))
        self._cache[key] = seasons
        return seasons

    def get_daily_points(self, resort_name: str, date: datetime.date) -> DailyPointsData:
        key = (resort_name, date.isoformat())
        if key in self._points_cache: return self._points_cache[key]
        dow = date.strftime("%a")
        holiday = next((h for h in self.get_holidays(resort_name, date.year) if h.contains(date)), None)
        if holiday:
            points = holiday.room_points if holiday.is_start(date) else {}
            result = DailyPointsData(date, dow, points, holiday)
        else:
            season_match = next((s for s in self.get_seasons(resort_name, date.year) if s.contains(date)), None)
            points = {}
            if season_match:
                for cat in season_match.day_categories.values():
                    if dow in cat.get("day_pattern", []):
                        points = cat.get("room_points", {})
                        break
            result = DailyPointsData(date, dow, points)
        self._points_cache[key] = result
        return result

    def get_available_room_types(self, resort_name: str, date: datetime.date) -> List[str]:
        return sorted(self.get_daily_points(resort_name, date).room_points.keys())

# ====================================================================
# ENGINE – RENT vs COST
# ====================================================================
class CalculationEngine:
    def __init__(self, repo: DataRepository):
        self.repo = repo

    def calculate_rental_stay(self, resort, room, checkin, nights, rate_per_point, discount):
        rows = []
        total_rent = total_points = 0
        for i in range(nights):
            date = checkin + timedelta(days=i)
            daily = self.repo.get_daily_points(resort, date)
            raw = daily.get_points(room)
            points = math.floor(raw * discount.multiplier)
            rent = math.ceil(raw * rate_per_point)
            if daily.holiday and daily.holiday.is_start(date):
                rows.append({"Date": f"{daily.holiday.name} (Holiday Week)", "Rent": f"${rent:,}", "Points Used": points})
            else:
                rows.append({"Date": date.strftime("%d %b %Y"), "Day": date.strftime("%a"), "Rent": f"${rent:,}", "Points Used": points})
            total_rent += rent
            total_points += points
        return pd.DataFrame(rows), total_points, total_rent

    def calculate_ownership_cost(self, resort, room, checkin, nights, maint_rate, purchase_price,
                                 coc_rate, useful_life, salvage, discount,
                                 inc_maint=True, inc_cap=True, inc_dep=True):
        rows = []
        total_cost = total_points = 0
        dep_per_point = (purchase_price - salvage) / useful_life if inc_dep and useful_life > 0 else 0
        for i in range(nights):
            date = checkin + timedelta(days=i)
            daily = self.repo.get_daily_points(resort, date)
            raw = daily.get_points(room)
            points = math.floor(raw * discount.multiplier)

            maint = math.ceil(points * maint_rate) if inc_maint else 0
            cap = math.ceil(points * purchase_price * coc_rate) if inc_cap else 0
            dep = math.ceil(points * dep_per_point) if inc_dep else 0
            cost = maint + cap + dep

            row = {"Date": date.strftime("%d %b %Y"), "Day": date.strftime("%a"), "Points": points}
            if inc_maint: row["Maint"] = f"${maint:,}"
            if inc_cap: row["Cap"] = f"${cap:,}"
            if inc_dep: row["Dep"] = f"${dep:,}"
            row["Total Cost"] = f"${cost:,}"
            rows.append(row)

            total_cost += cost
            total_points += points
        return pd.DataFrame(rows), total_points, total_cost

    def compare(self, resort, rooms, checkin, nights, rate_per_point, discount, mode,
                purchase_price=16.0, coc=0.07, life=15, salvage=3.0,
                inc_maint=True, inc_cap=True, inc_dep=True):
        rows = []; daily = []; holiday = []; total_non_hol = {r: 0 for r in rooms}
        dep_per_point = (purchase_price - salvage) / life if inc_dep else 0

        for i in range(nights):
            date = checkin + timedelta(days=i)
            daily_data = self.repo.get_daily_points(resort, date)

            if daily_data.holiday and daily_data.holiday.is_start(date):
                for room in rooms:
                    raw = daily_data.get_points(room)
                    if mode == "Renter":
                        val = math.ceil(raw * rate_per_point)
                    else:
                        pts = math.floor(raw * discount.multiplier)
                        val = (math.ceil(pts * rate_per_point) if inc_maint else 0) + \
                              (math.ceil(pts * purchase_price * coc) if inc_cap else 0) + \
                              (math.ceil(pts * dep_per_point) if inc_dep else 0)
                    rows.append({"Date": f"{daily_data.holiday.name} (Holiday)", "Room Type": room, "Value": f"${val:,}"})
                    holiday.append({"Holiday": daily_data.holiday.name, "Room Type": room, "Value": val})
                continue
            if daily_data.holiday: continue

            for room in rooms:
                raw = daily_data.get_points(room)
                if mode == "Renter":
                    val = math.ceil(raw * rate_per_point)
                else:
                    pts = math.floor(raw * discount.multiplier)
                    val = (math.ceil(pts * rate_per_point) if inc_maint else 0) + \
                          (math.ceil(pts * purchase_price * coc) if inc_cap else 0) + \
                          (math.ceil(pts * dep_per_point) if inc_dep else 0)
                rows.append({"Date": date.strftime("%d %b %Y"), "Room Type": room, "Value": f"${val:,}"})
                total_non_hol[room] += val
                daily.append({"Day": date.strftime("%a"), "Room Type": room, "Value": val})

        total_row = {"Date": "Total (Non-Holiday)"}
        for r in rooms: total_row[r] = f"${total_non_hol[r]:,}"
        rows.append(total_row)

        df = pd.DataFrame(rows)
        pivot = df.pivot_table(index="Date", columns="Room Type", values="Value", aggfunc="first").reset_index()
        pivot = pivot[["Date"] + [c for c in rooms if c in pivot.columns]]
        return pivot, pd.DataFrame(daily), pd.DataFrame(holiday)

    def adjust_for_holiday_weeks(self, resort, checkin, nights):
        checkout = checkin + timedelta(days=nights-1)
        holidays = self.repo.get_holidays(resort, checkin.year)
        overlapping = [h for h in holidays if h.start_date <= checkout and h.end_date >= checkin]
        if not overlapping: return checkin, nights, False
        earliest = min(h.start_date for h in overlapping)
        latest = max(h.end_date for h in overlapping)
        return min(checkin, earliest), (max(checkout, latest) - min(checkin, earliest)).days + 1, True

    def _fmt(self, d): return d.strftime("%d %b %Y")

# ====================================================================
# MAIN APP – BULLETPROOF
# ====================================================================
def main():
    st.set_page_config(page_title="MVC Calculator v2.0", layout="wide")
    st.markdown("<style>.stButton button{font-size:12px!important;padding:5px 10px!important;height:auto!important}</style>", unsafe_allow_html=True)

    # Load data
    try:
        with open("data_v2.json") as f: data = json.load(f)
        repo = DataRepository(data)
    except:
        st.error("data_v2.json not found!"); st.stop()

    st.title("Marriott Vacation Club Calculator v2.0")

    # Sidebar – always define everything safely
    with st.sidebar:
        st.header("Configuration")
        user_mode = st.selectbox("Mode", ["Renter", "Owner"], key="mode")

        # === Always define these with defaults ===
        rate_per_point = repo.get_maintenance_rate(2026)
        discount = DiscountLevel.NONE
        purchase_price = 16.0
        cost_of_capital = 0.07
        useful_life = 15
        salvage_value = 3.0
        include_maint = include_cap = include_dep = True

        if user_mode == "Owner":
            purchase_price = st.number_input("Purchase Price per Point ($)", value=16.0, step=0.1)
            discount = list(DiscountLevel)[st.selectbox("Discount", [0,1,2], format_func=lambda x: list(DiscountLevel)[x].description)]
            include_maint = st.checkbox("Include Maintenance", True)
            rate_per_point = st.number_input("Maint Rate ($/pt)", value=repo.get_maintenance_rate(2026), disabled=not include_maint)
            include_cap = st.checkbox("Include Capital Cost", True)
            cost_of_capital = st.number_input("Cost of Capital (%)", value=7.0, step=0.1)/100 if include_cap else 0.07
            include_dep = st.checkbox("Include Depreciation", True)
            useful_life = st.number_input("Useful Life (years)", value=15, min_value=1) if include_dep else 15
            salvage_value = st.number_input("Salvage Value ($/pt)", value=3.0) if include_dep else 3.0
        else:
            adv = st.checkbox("Advanced Options", False)
            if adv:
                opt = st.radio("Option", ["Maint Rate (No Disc)", "Custom Rate", "Executive", "Presidential"])
                if "Custom" in opt:
                    rate_per_point = st.number_input("Custom Rate ($/pt)", value=rate_per_point)
                    discount = DiscountLevel.NONE
                elif "Executive" in opt: discount = DiscountLevel.EXECUTIVE
                elif "Presidential" in opt: discount = DiscountLevel.PRESIDENTIAL
            # else defaults stay as-is

    # Resort selection
    cols = st.columns(6)
    for i, name in enumerate(repo.resort_names):
        with cols[i % 6]:
            if st.button(name, key=f"r{i}", type="primary" if st.session_state.get("res")==name else "secondary"):
                st.session_state.res = name; st.rerun()
    resort = st.session_state.get("res")
    if not resort: st.warning("Select a resort"); st.stop()

    # Main inputs
    c1, c2, c3, c4 = st.columns(4)
    with c1: checkin = st.date_input("Check-in", datetime(2026,2,20).date())
    with c2: nights = st.number_input("Nights", 1, 30, 7)
    with c3: room = st.selectbox("Room Type", repo.get_available_room_types(resort, checkin))
    with c4: compare = st.multiselect("Compare", [r for r in repo.get_available_room_types(resort, checkin) if r != room])

    engine = CalculationEngine(repo)
    adj_checkin, adj_nights, adjusted = engine.adjust_for_holiday_weeks(resort, checkin, nights)
    if adjusted:
        st.info(f"Adjusted to full holiday week: {engine._fmt(adj_checkin)} – {engine._fmt(adj_checkin + timedelta(adj_nights-1))} ({adj_nights} nights)")

    # Single stay result
    if user_mode == "Renter":
        df, pts, total = engine.calculate_rental_stay(resort, room, adj_checkin, adj_nights, rate_per_point, discount)
        st.subheader(f"{resort} – Rental Breakdown")
        st.dataframe(df, use_container_width=True)
        st.success(f"Points Used: {pts:,} │ **Total Rent: ${total:,}**")
    else:
        df, pts, total = engine.calculate_ownership_cost(resort, room, adj_checkin, adj_nights, rate_per_point,
                                                         purchase_price, cost_of_capital, useful_life, salvage_value,
                                                         discount, include_maint, include_cap, include_dep)
        st.subheader(f"{resort} – Ownership Cost Breakdown")
        st.dataframe(df, use_container_width=True)
        st.success(f"Points Used: {pts:,} │ **Total Cost: ${total:,}**")

    # Comparison
    if compare:
        all_rooms = [room] + compare
        pivot, daily_df, hol_df = engine.compare(resort, all_rooms, adj_checkin, adj_nights, rate_per_point, discount, user_mode,
                                                purchase_price, cost_of_capital, useful_life, salvage_value,
                                                include_maint, include_cap, include_dep)

        st.subheader("Rent Comparison" if user_mode=="Renter" else "Cost Comparison")
        st.dataframe(pivot, use_container_width=True)

        if not daily_df.empty:
            fig = px.bar(daily_df, x="Day", y="Value", color="Room Type", barmode="group",
                         labels={"Value": "Rent ($)" if user_mode=="Renter" else "Cost ($)"},
                         text_auto=True, height=600)
            fig.update_traces(texttemplate="$%{y:,}", textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

        if not hol_df.empty:
            fig = px.bar(hol_df, x="Holiday", y="Value", color="Room Type", barmode="group",
                         text_auto=True, height=500)
            fig.update_traces(texttemplate="$%{y:,}", textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
