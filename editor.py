# calculator.py
import streamlit as st
import math
import json
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum
import pytz

from common.ui import setup_page, render_resort_card, render_resort_grid
from common.data import load_data, get_resorts, get_resort_by_display_name, get_maintenance_rate
from common.utils import sort_resorts_west_to_east

# ========================== DOMAIN MODELS (unchanged) ==========================
class UserMode(Enum):
    RENTER = "Renter"
    OWNER = "Owner"

class DiscountPolicy(Enum):
    NONE = "None"
    EXECUTIVE = "within_30_days"
    PRESIDENTIAL = "within_60_days"

@dataclass
class Holiday:
    name: str
    start_date: datetime.date
    end_date: datetime.date
    room_points: Dict[str, int]

@dataclass
class DayCategory:
    days: List[str]
    room_points: Dict[str, int]

@dataclass
class SeasonPeriod:
    start: datetime.date
    end: datetime.date

@dataclass
class Season:
    name: str
    periods: List[SeasonPeriod]
    day_categories: List[DayCategory]

@dataclass
class YearData:
    holidays: List[Holiday]
    seasons: List[Season]

@dataclass
class ResortData:
    id: str
    name: str
    years: Dict[str, YearData]

@dataclass
class CalculationResult:
    breakdown_df: pd.DataFrame
    total_points: int
    financial_total: float
    discount_applied: bool
    discounted_days: List[str]
    m_cost: float = 0.0
    c_cost: float = 0.0
    d_cost: float = 0.0

# ========================== REPOSITORY (unchanged) ==========================
class MVCRepository:
    def __init__(self, raw_data: dict):
        self._raw = raw_data
        self._resort_cache: Dict[str, ResortData] = {}
        self._global_holidays = self._parse_global_holidays()

    def _parse_global_holidays(self):
        parsed = {}
        for year, hols in self._raw.get("global_holidays", {}).items():
            parsed[year] = {}
            for name, data in hols.items():
                try:
                    start = datetime.strptime(data["start_date"], "%Y-%m-%d").date()
                    end = datetime.strptime(data["end_date"], "%Y-%m-%d").date()
                    parsed[year][name] = (start, end)
                except:
                    continue
        return parsed

    def get_resort(self, resort_name: str) -> Optional[ResortData]:
        if resort_name in self._resort_cache:
            return self._resort_cache[resort_name]

        raw_r = next((r for r in self._raw["resorts"] if r["display_name"] == resort_name), None)
        if not raw_r:
            return None

        years_data = {}
        for year_str, y_content in raw_r.get("years", {}).items():
            # Holidays
            holidays = []
            for h in y_content.get("holidays", []):
                ref = h.get("global_reference")
                if ref and ref in self._global_holidays.get(year_str, {}):
                    start, end = self._global_holidays[year_str][ref]
                    holidays.append(Holiday(
                        name=h.get("name", ref),
                        start_date=start,
                        end_date=end,
                        room_points=h.get("room_points", {})
                    ))

            # Seasons
            seasons = []
            for s in y_content.get("seasons", []):
                periods = [
                    SeasonPeriod(
                        datetime.strptime(p["start"], "%Y-%m-%d").date(),
                        datetime.strptime(p["end"], "%Y-%m-%d").date()
                    ) for p in s.get("periods", [])
                ]
                day_cats = [
                    DayCategory(days=cat.get("day_pattern", []), room_points=cat.get("room_points", {}))
                    for cat in s.get("day_categories", {}).values()
                ]
                seasons.append(Season(name=s["name"], periods=periods, day_categories=day_cats))

            years_data[year_str] = YearData(holidays=holidays, seasons=seasons)

        resort_obj = ResortData(id=raw_r["id"], name=raw_r["display_name"], years=years_data)
        self._resort_cache[resort_name] = resort_obj
        return resort_obj

    def get_resort_info(self, resort_name: str) -> Dict[str, str]:
        raw_r = next((r for r in self._raw["resorts"] if r["display_name"] == resort_name), None)
        if raw_r:
            return {
                "full_name": raw_r.get("resort_name", resort_name),
                "timezone": raw_r.get("timezone", "Unknown"),
                "address": raw_r.get("address", "")
            }
        return {"full_name": resort_name, "timezone": "Unknown", "address": ""}

# ========================== CALCULATOR SERVICE (unchanged) ==========================
class MVCCalculator:
    def __init__(self, repo: MVCRepository):
        self.repo = repo

    def _find_season_and_points(self, date: datetime.date, year_data: YearData, room_type: str) -> Tuple[str, int]:
        # Holiday override first
        for h in year_data.holidays:
            if h.start_date <= date <= h.end_date:
                return h.name, h.room_points.get(room_type, 0)

        # Then season logic
        for season in year_data.seasons:
            for period in season.periods:
                if period.start <= date <= period.end:
                    weekday = date.strftime("%A")
                    for cat in season.day_categories:
                        if weekday in cat.days:
                            return season.name, cat.room_points.get(room_type, 0)
        return "Unknown", 0

    def calculate_breakdown(self, resort_name: str, year: int, start_date: datetime.date, room_type: str,
                           mode: UserMode, discount: DiscountPolicy, booking_date: datetime.date) -> CalculationResult:
        resort = self.repo.get_resort(resort_name)
        if not resort or str(year) not in resort.years:
            return CalculationResult(pd.DataFrame(), 0, 0.0, False, [], 0, 0, 0)

        year_data = resort.years[str(year)]
        dates = [start_date + timedelta(days=i) for i in range(7)]
        rows = []

        total_points = 0
        discounted_days = []
        for d in dates:
            season_name, points = self._find_season_and_points(d, year_data, room_type)
            is_discounted = False
            if discount != DiscountPolicy.NONE:
                days_until_checkin = (d - booking_date.date()).days
                if ((discount == DiscountPolicy.EXECUTIVE and days_until_checkin <= 30) or
                    (discount == DiscountPolicy.PRESIDENTIAL and days_until_checkin <= 60)):
                    points = math.ceil(points * 0.5)
                    is_discounted = True
                    discounted_days.append(d.strftime("%Y-%m-%d"))

            total_points += points
            rows.append({
                "Date": d.strftime("%a %b %d"),
                "Season/Holiday": season_name,
                "Points": points,
                "Discounted": "Yes" if is_discounted else ""
            })

        df = pd.DataFrame(rows)
        m_rate = get_maintenance_rate(load_data(), year)
        m_cost = round(total_points * m_rate, 2)
        c_cost = round(total_points * 0.005, 2)
        d_cost = round(m_cost + c_cost, 2)

        return CalculationResult(
            breakdown_df=df,
            total_points=total_points,
            financial_total=d_cost,
            discount_applied=len(discounted_days) > 0,
            discounted_days=discounted_days,
            m_cost=m_cost,
            c_cost=c_cost,
            d_cost=d_cost
        )

# ========================== MAIN RUN FUNCTION ==========================
def run():
    setup_page()
    data = load_data()
    if not data:
        st.error("data_v2.json not found. Place it in the app folder.")
        st.stop()

    repo = MVCRepository(data)
    calc = MVCCalculator(repo)
    resorts_raw = get_resorts(data)

    if not resorts_raw:
        st.error("No resorts in data file.")
        st.stop()

    if "current_resort" not in st.session_state:
        st.session_state.current_resort = resorts_raw[0]["display_name"]

    st.markdown("<h1 style='text-align:center; color:#008080;'>Points & Rent Calculator</h1>", unsafe_allow_html=True)

    render_resort_grid(resorts_raw, st.session_state.current_resort)

    current_resort_name = st.session_state.current_resort
    resort_info = repo.get_resort_info(current_resort_name)
    render_resort_card(resort_info["full_name"], resort_info["timezone"], resort_info["address"])

    col1, col2 = st.columns([1, 1])
    with col1:
        year = st.selectbox("Year", options=sorted([int(y) for y in repo.get_resort(current_resort_name).years.keys()], reverse=True))
        start_date = st.date_input("Check-in Date (Friday/Saturday/Sunday)", value=datetime(year, 3, 1))
    with col2:
        room_type = st.selectbox("Room Type", ["Studio", "1 Bedroom", "2 Bedroom", "3 Bedroom"])
        mode_str = st.radio("You are", ["Renter", "Owner"], horizontal=True)
        mode = UserMode.RENTER if mode_str == "Renter" else UserMode.OWNER

    discount = st.selectbox("Discount Policy", [p.value for p in DiscountPolicy], format_func=lambda x: x.replace("_", " ").title())
    discount_policy = DiscountPolicy(discount)
    booking_date = st.date_input("Booking Date (for discount)", value=datetime.today())

    if st.button("Calculate", type="primary", use_container_width=True):
        result = calc.calculate_breakdown(
            current_resort_name, year, start_date, room_type, mode, discount_policy, booking_date
        )

        st.markdown("<div class='section-header'>Results</div>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Points", f"{result.total_points:,}")
        c2.metric("Maintenance + Cleaning", f"${result.d_cost:,}")
        c3.metric("Discount Applied", "Yes" if result.discount_applied else "No")
        c4.metric("Discounted Days", len(result.discounted_days))

        st.markdown("<div class='section-header'>7-Night Breakdown</div>", unsafe_allow_html=True)
        st.dataframe(result.breakdown_df, use_container_width=True, hide_index=True)
