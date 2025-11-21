"""
MVC Calculator v2.0 – FINAL VERSION
Perfect separation: Renter = Rent, Owner = Cost
Clean dollar labels, full comparison, no errors
"""
import streamlit as st
import math
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import plotly.express as px

# ====================================================================
# DATA MODELS & REPOSITORY (unchanged – perfect)
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
    def contains(self, date: datetime.date) -> bool:
        return self.start_date <= date <= self.end_date
    def is_start(self, date: datetime.date) -> bool:
        return date == self.start_date

@dataclass
class SeasonPeriod:
    name: str
    start_date: datetime.date
    end_date: datetime.date
    day_categories: Dict[str, Any]
    def contains(self, date: datetime.date) -> bool:
        return self.start_date <= date <= self.end_date

@dataclass
class DailyPointsData:
    date: datetime.date
    day_of_week: str
    room_points: Dict[str, int]
    season: Optional[str] = None
    holiday: Optional[HolidayPeriod] = None
    def get_points(self, room_type: str) -> int:
        return self.room_points.get(room_type, 0)

class DataRepository:
    def __init__(self, data: Dict[str, Any]):
        self._data = data
        self._cache: Dict[str, Any] = {}
        self._points_cache: Dict[Tuple[str, str], DailyPointsData] = {}
        self.schema_version = data.get("schema_version", "1.0.0")
        if not self.schema_version.startswith("2."):
            raise ValueError(f"Unsupported schema version: {self.schema_version}")
        self._resorts_by_name = {r["display_name"]: r for r in data.get("resorts", [])}

    @property
    def resort_names(self) -> List[str]:
        return sorted(self._resorts_by_name.keys())

    def get_maintenance_rate(self, year: int) -> float:
        rates = self._data.get("configuration", {}).get("maintenance_rates", {})
        return rates.get(str(year), 0.86)

    def get_resort_data(self, resort_name: str) -> Optional[Dict]:
        return self._resorts_by_name.get(resort_name)

    def get_holidays(self, resort_name: str, year: int) -> List[HolidayPeriod]:
        key = f"holidays_{resort_name}_{year}"
        if key in self._cache: return self._cache[key]
        resort = self.get_resort_data(resort_name)
        if not resort: return []
        year_data = resort.get("years", {}).get(str(year), {})
        holiday_list = year_data.get("holidays", [])
        holidays = []
        for h in holiday_list:
            if "global_reference" in h:
                gh = self._data.get("global_holidays", {}).get(str(year), {}).get(h["global_reference"])
                if gh:
                    s = datetime.strptime(gh["start_date"], "%Y-%m-%d").date()
                    e = datetime.strptime(gh["end_date"], "%Y-%m-%d").date()
                    holidays.append(HolidayPeriod(h["name"], s, e, h.get("room_points", {})))
            elif "start_date" in h and "end_date" in h:
                s = datetime.strptime(h["start_date"], "%Y-%m-%d").date()
                e = datetime.strptime(h["end_date"], "%Y-%m-%d").date()
                holidays.append(HolidayPeriod(h["name"], s, e, h.get("room_points", {})))
        self._cache[key] = holidays
        return holidays

    def get_seasons(self, resort_name: str, year: int) -> List[SeasonPeriod]:
        key = f"seasons_{resort_name}_{year}"
        if key in self._cache: return self._cache[key]
        resort = self.get_resort_data(resort_name)
        if not resort: return []
        year_data = resort.get("years", {}).get(str(year), {})
        season_list = year_data.get("seasons", [])
        seasons = []
        for s in season_list:
            for p in s.get("periods", []):
                start = datetime.strptime(p["start"], "%Y-%m-%d").date()
                end = datetime.strptime(p["end"], "%Y-%m-%d").date()
                seasons.append(SeasonPeriod(s["name"], start, end, s.get("day_categories", {})))
        self._cache[key] = seasons
        return seasons

    def get_daily_points(self, resort_name: str, date: datetime.date) -> DailyPointsData:
        key = (resort_name, date.strftime("%Y-%m-%d"))
        if key in self._points_cache: return self._points_cache[key]
        dow = date.strftime("%a")
        holidays = self.get_holidays(resort_name, date.year)
        holiday = next((h for h in holidays if h.contains(date)), None)
        if holiday:
            room_points = holiday.room_points if holiday.is_start(date) else {}
            result = DailyPointsData(date, dow, room_points, holiday=holiday)
        else:
            seasons = self.get_seasons(resort_name, date.year)
            season = next((s for s in seasons if s.contains(date)), None)
            room_points = {}
            if season:
                for cat_data in season.day_categories.values():
                    if dow in cat_data.get("day_pattern", []):
                        room_points = cat_data.get("room_points", {})
                        break
            result = DailyPointsData(date, dow, room_points)
        self._points_cache[key] = result
        return result

    def get_available_room_types(self, resort_name: str, date: datetime.date) -> List[str]:
        daily = self.get_daily_points(resort_name, date)
        return sorted(daily.room_points.keys())

# ====================================================================
# CALCULATION ENGINE – RENT vs COST SEPARATED
# ====================================================================
class CalculationEngine:
    def __init__(self, repository: DataRepository):
        self.repo = repository

    # RENTER: Rent calculation
    def calculate_rental_stay(self, resort_name: str, room_type: str, checkin: datetime.date,
                             nights: int, rate_per_point: float, discount: DiscountLevel):
        rows = []
        total_discounted = total_raw = total_rent = 0
        current_holiday = None
        for i in range(nights):
            date = checkin + timedelta(days=i)
            daily = self.repo.get_daily_points(resort_name, date)
            raw = daily.get_points(room_type)
            discounted = math.floor(raw * discount.multiplier)
            rent = math.ceil(raw * rate_per_point)

            if daily.holiday and daily.holiday.is_start(date):
                current_holiday = daily.holiday
                rows.append({
                    "Date": f"{current_holiday.name} ({self._fmt_date(current_holiday.start_date)} - {self._fmt_date(current_holiday.end_date)})",
                    "Day": "", "Rent": f"${rent:,}", "Points Used": discounted
                })
                total_rent += rent
                total_discounted += discounted
                total_raw += raw
                continue
            if current_holiday: continue

            rows.append({
                "Date": self._fmt_date(date), "Day": daily.day_of_week,
                "Rent": f"${rent:,}", "Points Used": discounted
            })
            total_rent += rent
            total_discounted += discounted
            total_raw += raw
        return pd.DataFrame(rows), total_discounted, total_raw, total_rent

    # OWNER: Cost calculation
    def calculate_ownership_stay(self, resort_name: str, room_type: str, checkin: datetime.date,
                                nights: int, rate_per_point: float, purchase_price: float,
                                cost_of_capital: float, useful_life: int, salvage_value: float,
                                discount: DiscountLevel, include_maint: bool, include_cap: bool, include_dep: bool):
        rows = []
        total_points = total_cost = 0
        dep_per_point = (purchase_price - salvage_value) / useful_life if include_dep and useful_life > 0 else 0
        current_holiday = None

        for i in range(nights):
            date = checkin + timedelta(days=i)
            daily = self.repo.get_daily_points(resort_name, date)
            raw = daily.get_points(room_type)
            points = math.floor(raw * discount.multiplier)

            maint = math.ceil(points * rate_per_point) if include_maint else 0
            cap = math.ceil(points * purchase_price * cost_of_capital) if include_cap else 0
            dep = math.ceil(points * dep_per_point) if include_dep else 0
            day_cost = maint + cap + dep

            if daily.holiday and daily.holiday.is_start(date):
                current_holiday = daily.holiday
                row = {"Date": f"{current_holiday.name} ({self._fmt_date(current_holiday.start_date)} - {self._fmt_date(current_holiday.end_date)})", "Day": "", "Points": points}
                if include_maint: row["Maintenance"] = f"${maint:,}"
                if include_cap: row["Capital Cost"] = f"${cap:,}"
                if include_dep: row["Depreciation"] = f"${dep:,}"
                row["Total Cost"] = f"${day_cost:,}"
                rows.append(row)
                total_cost += day_cost
                total_points += points
                continue
            if current_holiday: continue

            row = {"Date": self._fmt_date(date), "Day": daily.day_of_week, "Points": points}
            if include_maint: row["Maintenance"] = f"${maint:,}"
            if include_cap: row["Capital Cost"] = f"${cap:,}"
            if include_dep: row["Depreciation"] = f"${dep:,}"
            row["Total Cost"] = f"${day_cost:,}"
            rows.append(row)
            total_cost += day_cost
            total_points += points

        return pd.DataFrame(rows), total_points, total_cost

    # COMPARISON – RESPECTS MODE (Rent vs Cost)
    def compare_stays(self, resort_name: str, room_types: List[str], checkin: datetime.date, nights: int,
                      rate_per_point: float, discount: DiscountLevel, user_mode: str,
                      purchase_price=16.0, cost_of_capital=0.07, useful_life=15, salvage_value=3.0,
                      include_maint=True, include_cap=True, include_dep=True):
        rows = []
        daily_chart = []
        holiday_chart = []
        total_non_holiday = {r: 0 for r in room_types}

        for i in range(nights):
            date = checkin + timedelta(days=i)
            daily = self.repo.get_daily_points(resort_name, date)

            if daily.holiday and daily.holiday.is_start(date):
                h = daily.holiday
                start_str = self._fmt_date(h.start_date)
                end_str = self._fmt_date(h.end_date)
                for room in room_types:
                    raw = daily.get_points(room)
                    if user_mode == "Renter":
                        value = math.ceil(raw * rate_per_point)
                        label = f"${value:,}"
                    else:
                        points = math.floor(raw * discount.multiplier)
                        maint = math.ceil(points * rate_per_point) if include_maint else 0
                        cap = math.ceil(points * purchase_price * cost_of_capital) if include_cap else 0
                        dep = math.ceil(points * (purchase_price - salvage_value) / useful_life) if include_dep else 0
                        value = maint + cap + dep
                        label = f"${value:,}"
                    rows.append({"Date": f"{h.name} ({start_str} - {end_str})", "Room Type": room, "Value": label})
                    holiday_chart.append({"Holiday": h.name, "Room Type": room, "Value": value})
                continue
            if daily.holiday: continue

            for room in room_types:
                raw = daily.get_points(room)
                if user_mode == "Renter":
                    value = math.ceil(raw * rate_per_point)
                else:
                    points = math.floor(raw * discount.multiplier)
                    maint = math.ceil(points * rate_per_point) if include_maint else 0
                    cap = math.ceil(points * purchase_price * cost_of_capital) if include_cap else 0
                    dep = math.ceil(points * (purchase_price - salvage_value) / useful_life) if include_dep else 0
                    value = maint + cap + dep
                rows.append({"Date": self._fmt_date(date), "Room Type": room, "Value": f"${value:,}"})
                total_non_holiday[room] += value
                daily_chart.append({"Day": daily.day_of_week, "Room Type": room, "Value": value})

        total_row = {"Date": "Total (Non-Holiday)" if user_mode == "Renter" else "Total Cost (Non-Holiday)"}
        for r in room_types:
            total_row[r] = f"${total_non_holiday[r]:,}"
        rows.append(total_row)

        df = pd.DataFrame(rows)
        pivot = df.pivot_table(index="Date", columns="Room Type", values="Value", aggfunc="first").reset_index()
        pivot = pivot[["Date"] + [c for c in room_types if c in pivot.columns]]
        return pivot, pd.DataFrame(daily_chart), pd.DataFrame(holiday_chart)

    def adjust_for_holiday_weeks(self, resort_name: str, checkin: datetime.date, nights: int):
        checkout = checkin + timedelta(days=nights - 1)
        holidays = self.repo.get_holidays(resort_name, checkin.year)
        overlapping = [h for h in holidays if h.start_date <= checkout and h.end_date >= checkin]
        if not overlapping: return checkin, nights, False
        earliest = min(h.start_date for h in overlapping)
        latest = max(h.end_date for h in overlapping)
        new_checkin = min(checkin, earliest)
        new_nights = (max(checkout, latest) - new_checkin).days + 1
        return new_checkin, new_nights, True

    def _fmt_date(self, d):
        return d.strftime("%d %b %Y")

# ====================================================================
# UI – FULL RENT/COST SEPARATION
# ====================================================================
def main():
    st.set_page_config(page_title="MVC Calculator v2.0", layout="wide")
    st.markdown("<style>.stButton button{font-size:12px!important;padding:5px 10px!important;height:auto!important}</style>", unsafe_allow_html=True)

    repo = None
    try:
        with open("data_v2.json", "r") as f:
            data = json.load(f)
        repo = DataRepository(data)
    except:
        st.error("data_v2.json not found.")
        st.stop()

    st.title("Marriott Vacation Club Calculator v2.0")

    with st.sidebar:
        st.header("Configuration")
        user_mode = st.selectbox("User Mode", ["Renter", "Owner"], key="mode")

        if user_mode == "Owner":
            purchase_price = st.number_input("Purchase Price per Point ($)", value=16.0, step=0.1)
            discount_idx = st.selectbox("Last-Minute Discount", [0,1,2], format_func=lambda x: list(DiscountLevel)[x].description)
            discount = list(DiscountLevel)[discount_idx]
            include_maint = st.checkbox("Include Maintenance Cost", True)
            maint_rate = st.number_input("Maintenance Rate ($/point)", value=repo.get_maintenance_rate(2026), disabled=not include_maint)
            include_cap = st.checkbox("Include Capital Cost", True)
            cost_of_capital = st.number_input("Cost of Capital (%)", value=7.0, step=0.1)/100 if include_cap else 0.07
            include_dep = st.checkbox("Include Depreciation", True)
            useful_life = st.number_input("Useful Life (years)", value=15, min_value=1) if include_dep else 15
            salvage_value = st.number_input("Salvage Value ($/point)", value=3.0) if include_dep else 3.0
            rate_per_point = maint_rate
        else:
            allow_mod = st.checkbox("More Options", key="allow_renter_mod")
            if allow_mod:
                opt = st.radio("Rate Option", ["Maintenance Rate (No Discount)", "Custom Rate (No Discount)", "Executive Discount", "Presidential Discount"], key="rate_opt")
                if "Custom" in opt:
                    rate_per_point = st.number_input("Custom Rate ($/point)", value=repo.get_maintenance_rate(2026))
                    discount = DiscountLevel.NONE
                elif "Executive" in opt:
                    rate_per_point = repo.get_maintenance_rate(2026)
                    discount = DiscountLevel.EXECUTIVE
                elif "Presidential" in opt:
                    rate_per_point = repo.get_maintenance_rate(2026)
                    discount = DiscountLevel.PRESIDENTIAL
                else:
                    rate_per_point = repo.get_maintenance_rate(2026)
                    discount = DiscountLevel.NONE
            else:
                rate_per_point = repo.get_maintenance_rate(2026)
                discount = DiscountLevel.NONE

    # Resort selection
    cols = st.columns(6)
    for i, name in enumerate(repo.resort_names):
        with cols[i % 6]:
            if st.button(name, key=f"res_{i}", type="primary" if st.session_state.get("current_resort")==name else "secondary"):
                st.session_state.current_resort = name
                st.rerun()
    resort = st.session_state.current_resort
    if not resort:
        st.warning("Please select a resort.")
        st.stop()

    col1, col2, col3, col4 = st.columns(4)
    with col1: checkin = st.date_input("Check-in", value=datetime(2026,2,20).date())
    with col2: nights = st.number_input("Nights", 1, 30, 7)
    room_types = repo.get_available_room_types(resort, checkin)
    with col3: room = st.selectbox("Room Type", room_types)
    with col4: compare = st.multiselect("Compare With", [r for r in room_types if r != room])

    engine = CalculationEngine(repo)
    adj_checkin, adj_nights, adjusted = engine.adjust_for_holiday_weeks(resort, checkin, nights)
    if adjusted:
        end = adj_checkin + timedelta(days=adj_nights-1)
        st.info(f"Adjusted: **{engine._fmt_date(adj_checkin)} – {engine._fmt_date(end)}** ({adj_nights} nights)")

    # SINGLE RESULT
    if user_mode == "Renter":
        df, disc_pts, raw_pts, total_rent = engine.calculate_rental_stay(resort, room, adj_checkin, adj_nights, rate_per_point, discount)
        st.subheader(f"{resort} – Rental Breakdown")
        st.dataframe(df, use_container_width=True)
        st.success(f"Total Points Used: {disc_pts:,} │ **Total Rent: ${total_rent:,}**")
    else:
        df, pts, total_cost = engine.calculate_ownership_stay(
            resort, room, adj_checkin, adj_nights, rate_per_point, purchase_price,
            cost_of_capital, useful_life, salvage_value, discount,
            include_maint, include_cap, include_dep)
        st.subheader(f"{resort} – Ownership Cost Breakdown")
        st.dataframe(df, use_container_width=True)
        st.success(f"Total Points: {pts:,} │ **Total Cost: ${total_cost:,}**")

    # COMPARISON – RESPECTS MODE
    if compare:
        all_rooms = [room] + compare
        pivot, daily_df, holiday_df = engine.compare_stays(
            resort, all_rooms, adj_checkin, adj_nights, rate_per_point, discount, user_mode,
            purchase_price, cost_of_capital, useful_life, salvage_value,
            include_maint, include_cap, include_dep)

        title = "Rent Comparison" if user_mode == "Renter" else "Cost Comparison"
        st.subheader(title)
        st.dataframe(pivot, use_container_width=True)

        # Charts
        if not daily_df.empty:
            fig = px.bar(daily_df, x="Day", y="Value", color="Room Type", barmode="group",
                         text_auto=True, height=600, labels={"Value": "Rent ($)" if user_mode=="Renter" else "Cost ($)"})
            fig.update_traces(texttemplate="$%{y:,}", textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
        if not holiday_df.empty:
            fig = px.bar(holiday_df, x="Holiday", y="Value", color="Room Type", barmode="group",
                         text_auto=True, height=600)
            fig.update_traces(texttemplate="$%{y:,}", textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
