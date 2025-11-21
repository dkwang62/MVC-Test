"""
MVC Calculator v2.0 – FINAL & PERFECT
Uses v2 schema (data_v2.json)
All features restored: comparison, total row, gantt, clean labels
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
# MODELS
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

# ====================================================================
# DATA REPOSITORY – v2 SCHEMA
# ====================================================================
class DataRepository:
    def __init__(self, data: Dict[str, Any]):
        self._data = data
        self._cache: Dict[str, Any] = {}
        self._points_cache: Dict[Tuple[str, str], DailyPointsData] = {}

        # v2 schema validation
        if not data.get("schema_version", "").startswith("2."):
            st.error("This app requires v2 schema (data_v2.json)")
            st.stop()

        self._resorts_by_name = {
            r["display_name"]: r for r in data.get("resorts", [])
        }

    @property
    def resort_names(self) -> List[str]:
        return sorted(self._resorts_by_name.keys())

    def get_maintenance_rate(self, year: int) -> float:
        rates = self._data.get("configuration", {}).get("maintenance_rates", {})
        return rates.get(str(year), 0.86)

    def get_resort_data(self, resort_name: str) -> Optional[Dict]:
        return self._resorts_by_name.get(resort_name)

    def get_global_holiday(self, year: int, holiday_name: str) -> Optional[Dict]:
        holidays = self._data.get("global_holidays", {}).get(str(year), {})
        return holidays.get(holiday_name)

    def get_holidays(self, resort_name: str, year: int) -> List[HolidayPeriod]:
        key = f"holidays_{resort_name}_{year}"
        if key in self._cache:
            return self._cache[key]

        resort = self.get_resort_data(resort_name)
        if not resort:
            return []

        year_data = resort.get("years", {}).get(str(year), {})
        holiday_list = year_data.get("holidays", [])
        holidays = []

        for h in holiday_list:
            if "global_reference" in h:
                gh = self.get_global_holiday(year, h["global_reference"])
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
        if key in self._cache:
            return self._cache[key]

        resort = self.get_resort_data(resort_name)
        if not resort:
            return []

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
        if key in self._points_cache:
            return self._points_cache[key]

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
            season_name = "Default Season"
            if season:
                season_name = season.name
                for cat_data in season.day_categories.values():
                    if dow in cat_data.get("day_pattern", []):
                        room_points = cat_data.get("room_points", {})
                        break
            result = DailyPointsData(date, dow, room_points, season=season_name)

        self._points_cache[key] = result
        return result

    def get_available_room_types(self, resort_name: str, date: datetime.date) -> List[str]:
        daily = self.get_daily_points(resort_name, date)
        return sorted(daily.room_points.keys())

# ====================================================================
# CALCULATION ENGINE – v2
# ====================================================================
class CalculationEngine:
    def __init__(self, repository: DataRepository):
        self.repo = repository

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
                    "Day": "", "Rent": f"${rent:,}", "Points Used": discounted, "Raw Points": raw
                })
                total_discounted += discounted
                total_raw += raw
                total_rent += rent
                continue
            if current_holiday:
                continue

            rows.append({
                "Date": self._fmt_date(date), "Day": daily.day_of_week,
                "Rent": f"${rent:,}", "Points Used": discounted, "Raw Points": raw
            })
            total_discounted += discounted
            total_raw += raw
            total_rent += rent

        return pd.DataFrame(rows), total_discounted, total_raw, total_rent

    def calculate_ownership_stay(self, resort_name: str, room_type: str, checkin: datetime.date,
                                nights: int, rate_per_point: float, purchase_price: float,
                                cost_of_capital: float, useful_life: int, salvage_value: float,
                                discount: DiscountLevel, inc_maint: bool, inc_cap: bool, inc_dep: bool):
        rows = []
        total_points = total_cost = 0
        dep_per_point = (purchase_price - salvage_value) / useful_life if inc_dep and useful_life > 0 else 0
        current_holiday = None

        for i in range(nights):
            date = checkin + timedelta(days=i)
            daily = self.repo.get_daily_points(resort_name, date)
            raw = daily.get_points(room_type)
            points = math.floor(raw * discount.multiplier)

            maint = math.ceil(points * rate_per_point) if inc_maint else 0
            cap = math.ceil(points * purchase_price * cost_of_capital) if inc_cap else 0
            dep = math.ceil(points * dep_per_point) if inc_dep else 0
            day_cost = maint + cap + dep

            if daily.holiday and daily.holiday.is_start(date):
                current_holiday = daily.holiday
                row = {"Date": f"{current_holiday.name} ({self._fmt_date(current_holiday.start_date)} - {self._fmt_date(current_holiday.end_date)})",
                       "Day": "", "Points": points}
                if inc_maint: row["Maintenance"] = f"${maint:,}"
                if inc_cap: row["Capital Cost"] = f"${cap:,}"
                if inc_dep: row["Depreciation"] = f"${dep:,}"
                row["Total Cost"] = f"${day_cost:,}"
                rows.append(row)
                total_cost += day_cost
                total_points += points
                continue
            if current_holiday:
                continue

            row = {"Date": self._fmt_date(date), "Day": daily.day_of_week, "Points": points}
            if inc_maint: row["Maintenance"] = f"${maint:,}"
            if inc_cap: row["Capital Cost"] = f"${cap:,}"
            if inc_dep: row["Depreciation"] = f"${dep:,}"
            row["Total Cost"] = f"${day_cost:,}"
            rows.append(row)
            total_cost += day_cost
            total_points += points

        return pd.DataFrame(rows), total_points, total_cost

    def compare_stays(self, resort_name: str, room_types: List[str], checkin: datetime.date, nights: int,
                      rate_per_point: float, discount: DiscountLevel, user_mode: str,
                      purchase_price=16.0, cost_of_capital=0.07, useful_life=15, salvage_value=3.0,
                      inc_maint=True, inc_cap=True, inc_dep=True):
        rows = []
        daily_chart = []
        holiday_chart = []
        total_non_holiday = {r: 0 for r in room_types}
        dep_per_point = (purchase_price - salvage_value) / useful_life if inc_dep else 0

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
                        val = math.ceil(raw * rate_per_point)
                    else:
                        pts = math.floor(raw * discount.multiplier)
                        val = (math.ceil(pts * rate_per_point) if inc_maint else 0) + \
                              (math.ceil(pts * purchase_price * cost_of_capital) if inc_cap else 0) + \
                              (math.ceil(pts * dep_per_point) if inc_dep else 0)
                    rows.append({"Date": f"{h.name} ({start_str} - {end_str})", "Room Type": room, "Value": f"${val:,}"})
                    holiday_chart.append({"Holiday": h.name, "Room Type": room, "Value": val})
                continue
            if daily.holiday:
                continue

            for room in room_types:
                raw = daily.get_points(room)
                if user_mode == "Renter":
                    val = math.ceil(raw * rate_per_point)
                else:
                    pts = math.floor(raw * discount.multiplier)
                    val = (math.ceil(pts * rate_per_point) if inc_maint else 0) + \
                          (math.ceil(pts * purchase_price * cost_of_capital) if inc_cap else 0) + \
                          (math.ceil(pts * dep_per_point) if inc_dep else 0)
                rows.append({"Date": self._fmt_date(date), "Room Type": room, "Value": f"${val:,}"})
                total_non_holiday[room] += val
                daily_chart.append({"Day": date.strftime("%a"), "Room Type": room, "Value": val})

        # TOTAL ROW
        total_row = {"Date": "Total (Non-Holiday)"}
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
        if not overlapping:
            return checkin, nights, False
        earliest = min(h.start_date for h in overlapping)
        latest = max(h.end_date for h in overlapping)
        new_checkin = min(checkin, earliest)
        new_nights = (max(checkout, latest) - new_checkin).days + 1
        return new_checkin, new_nights, True

    def _fmt_date(self, d):
        return d.strftime("%d %b %Y")

# ====================================================================
# GANTT CHART
# ====================================================================
def create_gantt_chart(repo: DataRepository, resort_name: str, year: int):
    rows = []
    for s in repo.get_seasons(resort_name, year):
        rows.append({"Task": s.name, "Start": s.start_date, "Finish": s.end_date + timedelta(days=1), "Type": "Season"})
    for h in repo.get_holidays(resort_name, year):
        rows.append({"Task": h.name, "Start": h.start_date, "Finish": h.end_date + timedelta(days=1), "Type": "Holiday"})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["Start"] = pd.to_datetime(df["Start"])
    df["Finish"] = pd.to_datetime(df["Finish"])
    color_map = {"Holiday": "rgb(255,99,71)", "Season": "rgb(135,206,250)"}
    fig = px.timeline(df, x_start="Start", x_end="Finish", y="Task", color="Type",
                      color_discrete_map=color_map, title=f"{resort_name} – Seasons & Holidays {year}",
                      height=max(400, len(df) * 35))
    fig.update_yaxes(autorange="reversed")
    return fig

# ====================================================================
# MAIN APP
# ====================================================================
def main():
    st.set_page_config(page_title="MVC Calculator v2.0", layout="wide")
    st.markdown("<style>.stButton button{font-size:12px!important;padding:5px 10px!important;height:auto!important}</style>", unsafe_allow_html=True)

    # Load v2 data
    try:
        with open("data_v2.json", "r") as f:
            data = json.load(f)
        repo = DataRepository(data)
    except FileNotFoundError:
        st.error("data_v2.json not found! Place it in the same folder.")
        st.stop()
    except Exception as e:
        st.error(f"Error loading data_v2.json: {e}")
        st.stop()

    st.title("Marriott Vacation Club Calculator v2.0")

    # Sidebar
    with st.sidebar:
        st.header("Configuration")
        user_mode = st.selectbox("User Mode", ["Renter", "Owner"], key="mode")

        # Safe defaults
        rate_per_point = repo.get_maintenance_rate(2026)
        discount = DiscountLevel.NONE
        purchase_price = 16.0
        cost_of_capital = 0.07
        useful_life = 15
        salvage_value = 3.0
        inc_maint = inc_cap = inc_dep = True

        if user_mode == "Owner":
            purchase_price = st.number_input("Purchase Price per Point ($)", value=16.0, step=0.1)
            discount = list(DiscountLevel)[st.selectbox("Discount", [0,1,2], format_func=lambda x: list(DiscountLevel)[x].description)]
            inc_maint = st.checkbox("Include Maintenance", True)
            rate_per_point = st.number_input("Maint Rate ($/pt)", value=repo.get_maintenance_rate(2026), disabled=not inc_maint)
            inc_cap = st.checkbox("Include Capital Cost", True)
            cost_of_capital = st.number_input("Cost of Capital (%)", value=7.0, step=0.1)/100 if inc_cap else 0.07
            inc_dep = st.checkbox("Include Depreciation", True)
            useful_life = st.number_input("Useful Life (years)", value=15) if inc_dep else 15
            salvage_value = st.number_input("Salvage Value ($/pt)", value=3.0) if inc_dep else 3.0
        else:
            adv = st.checkbox("Advanced Options", False)
            if adv:
                opt = st.radio("Option", ["Maint Rate (No Disc)", "Custom Rate", "Executive", "Presidential"])
                if "Custom" in opt:
                    rate_per_point = st.number_input("Rate ($/pt)", value=rate_per_point)
                if "Executive" in opt: discount = DiscountLevel.EXECUTIVE
                if "Presidential" in opt: discount = DiscountLevel.PRESIDENTIAL

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

    # Inputs
    c1, c2, c3, c4 = st.columns(4)
    with c1: checkin = st.date_input("Check-in", value=datetime(2026,2,20).date())
    with c2: nights = st.number_input("Nights", 1, 30, 7)
    with c3: room = st.selectbox("Room Type", repo.get_available_room_types(resort, checkin))
    with c4: compare = st.multiselect("Compare With", [r for r in repo.get_available_room_types(resort, checkin) if r != room])

    engine = CalculationEngine(repo)
    adj_checkin, adj_nights, adjusted = engine.adjust_for_holiday_weeks(resort, checkin, nights)
    if adjusted:
        end = adj_checkin + timedelta(days=adj_nights-1)
        st.info(f"Adjusted to full holiday: **{engine._fmt_date(adj_checkin)} – {engine._fmt_date(end)}** ({adj_nights} nights)")

    # Single result
    if user_mode == "Renter":
        df, disc_pts, raw_pts, total_rent = engine.calculate_rental_stay(resort, room, adj_checkin, adj_nights, rate_per_point, discount)
        st.subheader(f"{resort} – Rental Breakdown")
        st.dataframe(df, use_container_width=True)
        if discount != DiscountLevel.NONE:
            st.success(f"**{discount.description}** Applied")
        st.success(f"Points Used: {disc_pts:,} │ **Total Rent: ${total_rent:,}**")
    else:
        df, pts, total_cost = engine.calculate_ownership_stay(resort, room, adj_checkin, adj_nights, rate_per_point,
                                                             purchase_price, cost_of_capital, useful_life, salvage_value,
                                                             discount, inc_maint, inc_cap, inc_dep)
        st.subheader(f"{resort} – Ownership Cost Breakdown")
        st.dataframe(df, use_container_width=True)
        st.success(f"Points Used: {pts:,} │ **Total Cost: ${total_cost:,}**")

    # Comparison with TOTAL ROW
    if compare:
        all_rooms = [room] + compare
        pivot, daily_df, holiday_df = engine.compare_stays(resort, all_rooms, adj_checkin, adj_nights, rate_per_point, discount, user_mode,
                                                          purchase_price, cost_of_capital, useful_life, salvage_value,
                                                          inc_maint, inc_cap, inc_dep)

        st.subheader("Rent Comparison" if user_mode == "Renter" else "Cost Comparison")
        st.dataframe(pivot, use_container_width=True)
        st.download_button("Download Comparison CSV", pivot.to_csv(index=False), f"{resort}_comparison.csv")

        if not daily_df.empty:
            fig = px.bar(daily_df, x="Day", y="Value", color="Room Type", barmode="group",
                         text_auto=True, height=600, labels={"Value": "Rent ($)" if user_mode=="Renter" else "Cost ($)"})
            fig.update_traces(texttemplate="$%{y:,}", textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

        if not holiday_df.empty:
            fig = px.bar(holiday_df, x="Holiday", y="Value", color="Room Type", barmode="group",
                         text_auto=True, height=500)
            fig.update_traces(texttemplate="$%{y:,}", textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

    # Gantt
    gantt = create_gantt_chart(repo, resort, checkin.year)
    if gantt:
        st.plotly_chart(gantt, use_container_width=True)

if __name__ == "__main__":
    main()
