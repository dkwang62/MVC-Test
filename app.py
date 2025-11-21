import streamlit as st
import math
import json
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum
from collections import defaultdict

# ==============================================================================
# CONFIG & ENUMS
# ==============================================================================

class UserMode(Enum):
    RENTER = "Renter"
    OWNER = "Owner"

class DiscountPolicy(Enum):
    NONE = "None"
    EXECUTIVE = "within_30_days"   # 25%
    PRESIDENTIAL = "within_60_days" # 30%

# ==============================================================================
# DOMAIN MODELS
# ==============================================================================

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

# ==============================================================================
# REPOSITORY
# ==============================================================================

class MVCRepository:
    def __init__(self, raw_data: dict):
        self._raw = raw_data
        self._cache: Dict[str, ResortData] = {}
        self._global_holidays = self._parse_global_holidays()

    def get_resort_list(self) -> List[str]:
        return sorted([r["display_name"] for r in self._raw.get("resorts", [])])

    def get_config_val(self, year: int) -> float:
        return self._raw.get("configuration", {}).get("maintenance_rates", {}).get(str(year), 0.86)

    def _parse_global_holidays(self):
        parsed = {}
        for year, hols in self._raw.get("global_holidays", {}).items():
            parsed[year] = {}
            for name, data in hols.items():
                try:
                    parsed[year][name] = (
                        datetime.strptime(data["start_date"], "%Y-%m-%d").date(),
                        datetime.strptime(data["end_date"], "%Y-%m-%d").date()
                    )
                except:
                    continue
        return parsed

    def get_resort(self, resort_name: str) -> Optional[ResortData]:
        if resort_name in self._cache:
            return self._cache[resort_name]

        raw_r = next((r for r in self._raw["resorts"] if r["display_name"] == resort_name), None)
        if not raw_r:
            return None

        years_data = {}
        for year_str, y_content in raw_r.get("years", {}).items():
            holidays = []
            for h in y_content.get("holidays", []):
                ref = h.get("global_reference")
                if ref and ref in self._global_holidays.get(year_str, {}):
                    s, e = self._global_holidays[year_str][ref]
                    holidays.append(Holiday(
                        name=h.get("name", ref),
                        start_date=s,
                        end_date=e,
                        room_points=h.get("room_points", {})
                    ))

            seasons = []
            for s in y_content.get("seasons", []):
                periods = [SeasonPeriod(
                    datetime.strptime(p["start"], "%Y-%m-%d").date(),
                    datetime.strptime(p["end"], "%Y-%m-%d").date()
                ) for p in s.get("periods", [])]

                day_cats = [
                    DayCategory(days=cat.get("day_pattern", []), room_points=cat.get("room_points", {}))
                    for cat in s.get("day_categories", {}).values()
                ]
                seasons.append(Season(name=s["name"], periods=periods, day_categories=day_cats))

            years_data[year_str] = YearData(holidays=holidays, seasons=seasons)

        resort = ResortData(id=raw_r["id"], name=raw_r["display_name"], years=years_data)
        self._cache[resort_name] = resort
        return resort

# ==============================================================================
# CALCULATOR SERVICE
# ==============================================================================

class MVCCalculator:
    def __init__(self, repo: MVCRepository):
        self.repo = repo

    def _get_daily_points(self, resort: ResortData, date: datetime.date) -> Tuple[Dict[str, int], Optional[Holiday]]:
        year_str = str(date.year)
        if year_str not in resort.years:
            return {}, None
        yd = resort.years[year_str]

        for h in yd.holidays:
            if h.start_date <= date <= h.end_date:
                return h.room_points, h

        dow = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][date.weekday()]
        for s in yd.seasons:
            for p in s.periods:
                if p.start <= date <= p.end:
                    for cat in s.day_categories:
                        if dow in cat.days:
                            return cat.room_points, None
        return {}, None

    def calculate_breakdown(self, resort_name: str, room: str, checkin: datetime.date, nights: int,
                            user_mode: UserMode, rate: float,
                            discount_policy: DiscountPolicy = DiscountPolicy.NONE,
                            owner_config: dict = None) -> CalculationResult:

        resort = self.repo.get_resort(resort_name)
        if not resort:
            return CalculationResult(pd.DataFrame(), 0, 0.0, False, [], 0, 0, 0)

        rows = []
        total_points = 0
        total_cost = 0.0
        m_total = c_total = d_total = 0.0
        discount_applied = False
        discounted_days = []

        is_owner = user_mode == UserMode.OWNER
        disc_mul = owner_config.get("disc_mul", 1.0) if is_owner and owner_config else 1.0
        r_disc_mul = 0.75 if discount_policy == DiscountPolicy.EXECUTIVE else 0.70 if discount_policy == DiscountPolicy.PRESIDENTIAL else 1.0

        curr_holiday = None

        for i in range(nights):
            date = checkin + timedelta(days=i)
            pts_map, holiday = self._get_daily_points(resort, date)
            raw_pts = pts_map.get(room, 0)

            # Apply discount
            if is_owner:
                eff_pts = math.floor(raw_pts * disc_mul)
            else:
                days_ahead = (date - datetime.now().date()).days
                apply_disc = (
                    discount_policy == DiscountPolicy.EXECUTIVE and 0 < days_ahead <= 30 or
                    discount_policy == DiscountPolicy.PRESIDENTIAL and 0 < days_ahead <= 60
                )
                eff_pts = math.floor(raw_pts * r_disc_mul) if apply_disc else raw_pts
                if apply_disc:
                    discount_applied = True
                    discounted_days.append(date.strftime("%Y-%m-%d"))

            # Cost calculation
            if is_owner and owner_config:
                m = math.ceil(eff_pts * rate) if owner_config.get("inc_m") else 0
                c = math.ceil(eff_pts * owner_config.get("cap_rate", 0)) if owner_config.get("inc_c") else 0
                d = math.ceil(eff_pts * owner_config.get("dep_rate", 0)) if owner_config.get("inc_d") else 0
                day_cost = m + c + d
            else:
                day_cost = math.ceil(eff_pts * rate)

            total_points += eff_pts
            total_cost += day_cost
            m_total += m if is_owner else 0
            c_total += c if is_owner else 0
            d_total += d if is_owner else 0

            # Holiday grouping logic
            if holiday:
                if curr_holiday != holiday.name:
                    curr_holiday = holiday.name
                    row = {
                        "Date": f"{holiday.name} ({holiday.start_date.strftime('%b %d, %Y')} - {holiday.end_date.strftime('%b %d, %Y')})",
                        "Day": "",
                        "Points": eff_pts
                    }
                    if is_owner:
                        if owner_config.get("inc_m"): row["Maintenance"] = m
                        if owner_config.get("inc_c"): row["Capital Cost"] = c
                        if owner_config.get("inc_d"): row["Depreciation"] = d
                        row["Total Cost"] = day_cost
                    else:
                        row[room] = f"${day_cost:,.2f}"
                    rows.append(row)
                else:
                    last = rows[-1]
                    last["Points"] += eff_pts
                    if is_owner:
                        for col in ["Maintenance", "Capital Cost", "Depreciation", "Total Cost"]:
                            if col in last:
                                last[col] += locals()[col[0].lower()]
                        last["Total Cost"] += day_cost
                    else:
                        prev = float(last[room].replace("$", "").replace(",", ""))
                        last[room] = f"${prev + day_cost:,.2f}"
            else:
                curr_holiday = None
                row = {"Date": date.strftime("%Y-%m-%d"), "Day": date.strftime("%a"), "Points": eff_pts}
                if is_owner:
                    if owner_config.get("inc_m"): row["Maintenance"] = m
                    if owner_config.get("inc_c"): row["Capital Cost"] = c
                    if owner_config.get("inc_d"): row["Depreciation"] = d
                    row["Total Cost"] = day_cost
                else:
                    row[room] = f"${day_cost:,.2f}"
                rows.append(row)

        df = pd.DataFrame(rows)

        # Format owner columns properly
        if is_owner and not df.empty:
            for col in ["Maintenance", "Capital Cost", "Depreciation", "Total Cost"]:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: f"${x:,.2f}" if isinstance(x, (int, float)) else x)

        return CalculationResult(
            breakdown_df=df,
            total_points=total_points,
            financial_total=total_cost,
            discount_applied=discount_applied,
            discounted_days=discounted_days,
            m_cost=m_total,
            c_cost=c_total,
            d_cost=d_total
        )

    def adjust_holiday(self, resort_name: str, checkin: datetime.date, nights: int):
        resort = self.repo.get_resort(resort_name)
        if not resort or str(checkin.year) not in resort.years:
            return checkin, nights, False
        end = checkin + timedelta(days=nights - 1)
        for h in resort.years[str(checkin.year)].holidays:
            if h.start_date <= end and h.end_date >= checkin:
                new_start = min(checkin, h.start_date)
                new_end = max(end, h.end_date)
                return new_start, (new_end - new_start).days + 1, True
        return checkin, nights, False

# ==============================================================================
# UI
# ==============================================================================

def fmt_date(d):
    return d.strftime("%b %d, %Y")

st.set_page_config(page_title="MVC Calculator", layout="wide")

# Session state
if "data" not in st.session_state:
    st.session_state.data = None
if "current_resort" not in st.session_state:
    st.session_state.current_resort = None

# Load data
if st.session_state.data is None:
    try:
        with open("data_v2.json", "r") as f:
            st.session_state.data = json.load(f)
    except:
        pass

with st.sidebar:
    uploaded = st.file_uploader("Upload data_v2.json", type="json")
    if uploaded:
        st.session_state.data = json.load(uploaded)
        st.rerun()

if not st.session_state.data:
    st.warning("Please upload `data_v2.json` or place it in the app folder.")
    st.stop()

repo = MVCRepository(st.session_state.data)
calc = MVCCalculator(repo)
resorts = repo.get_resort_list()

# Sidebar controls
with st.sidebar:
    st.header("Settings")
    mode = UserMode(st.selectbox("Mode", [m.value for m in UserMode]))
    year = datetime.now().year
    default_rate = repo.get_config_val(year)

    owner_config = None
    discount_policy = DiscountPolicy.NONE
    rate = default_rate

    if mode == UserMode.OWNER:
        col1, col2 = st.columns(2)
        with col1:
            purchase_price = st.number_input("Purchase $/pt", value=16.0, step=0.1)
        with col2:
            discount_pct = st.selectbox("Discount", [0, 25, 30], format_func=lambda x: f"{x}%")
        inc_m = st.checkbox("Include Maintenance", True)
        inc_c = st.checkbox("Include Capital Cost", True)
        inc_d = st.checkbox("Include Depreciation", True)

        rate = st.number_input("Maint Rate $/pt", value=default_rate, step=0.01) if inc_m else 0.0
        coc = st.number_input("Cost of Capital %", value=7.0, step=0.1) / 100 if inc_c else 0.0
        life = st.number_input("Useful Life (yrs)", value=15) if inc_d else 1
        salvage = st.number_input("Salvage $/pt", value=3.0, step=0.1) if inc_d else 0.0

        owner_config = {
            "disc_mul": 1 - discount_pct / 100,
            "inc_m": inc_m, "inc_c": inc_c, "inc_d": inc_d,
            "cap_rate": purchase_price * coc / 365,
            "dep_rate": (purchase_price - salvage) / (life * 365)
        }
    else:
        adv = st.checkbox("Advanced Options")
        if adv:
            opt = st.radio("Rate", ["Maintenance Rate", "Custom Rate", "Within 30 days", "Within 60 days"])
            if opt == "Custom Rate":
                rate = st.number_input("Custom $/pt", value=default_rate)
            elif "30" in opt:
                discount_policy = DiscountPolicy.EXECUTIVE
            elif "60" in opt:
                discount_policy = DiscountPolicy.PRESIDENTIAL

# Resort selection grid
st.subheader("Select Resort")
cols = st.columns(6)
if st.session_state.current_resort not in resorts:
    st.session_state.current_resort = resorts[0]

for i, name in enumerate(resorts):
    with cols[i % 6]:
        if st.button(name, key=f"resort_{i}", type="primary" if name == st.session_state.current_resort else "secondary"):
            st.session_state.current_resort = name
            st.rerun()

resort_name = st.session_state.current_resort

st.title(f"Marriott Vacation Club • {mode.value} Calculator | {resort_name}")

# Main inputs - ON THE SAME LINE
col1, col2, col3, col4 = st.columns([2, 1.5, 2, 3])
with col1:
    checkin = st.date_input("Check-in", value=datetime(2025, 11, 22))
with col2:
    nights = st.number_input("Nights", 1, 60, 7)
with col3:
    room_type = st.selectbox("Room Type", ["1-BDRM", "2-BDRM", "3-BDRM"])  # will be replaced dynamically
with col4:
    compare = st.multiselect("Compare With", ["1-BDRM", "2-BDRM", "3-BDRM"])

# Auto-adjust to full holiday week
adj_checkin, adj_nights, adjusted = calc.adjust_holiday(resort_name, checkin, nights)
if adjusted:
    end = adj_checkin + timedelta(days=adj_nights - 1)
    st.info(f"Adjusted to full holiday: **{fmt_date(adj_checkin)} – {fmt_date(end)}** ({adj_nights} nights)")

# Load actual room types from data
pts, _ = calc._get_daily_points(repo.get_resort(resort_name), adj_checkin or checkin)
room_types = sorted(pts.keys()) if pts else []
if not room_types:
    st.error("No room data for this date.")
    st.stop()

# Rebuild selectors with real room names
room_type = st.selectbox("Select Room Type", room_types, key="room_main")
compare_rooms = st.multiselect("Compare With", [r for r in room_types if r != room_type], key="compare")

# Calculation
result = calc.calculate_breakdown(
    resort_name, room_type, adj_checkin, adj_nights,
    mode, rate, discount_policy, owner_config
)

# Display breakdown
st.subheader(f"{resort_name} {mode.value} Breakdown")
st.dataframe(result.breakdown_df, use_container_width=True)

if result.discount_applied:
    pct = "25" if discount_policy == DiscountPolicy.EXECUTIVE else "30"
    st.success(f"{pct}% Last-Minute Discount Applied on {len(result.discounted_days)} night(s)")

st.success(f"**Total Points:** {result.total_points:,} | **Total {mode.value}:** ${result.financial_total:,.2f}")

if mode == UserMode.OWNER and owner_config:
    if owner_config.get("inc_m"):
        st.info(f"Maintenance: ${result.m_cost:,.2f}")
    if owner_config.get("inc_c"):
        st.info(f"Capital Cost: ${result.c_cost:,.2f}")
    if owner_config.get("inc_d"):
        st.info(f"Depreciation: ${result.d_cost:,.2f}")

st.download_button("Download CSV", result.breakdown_df.to_csv(index=False), f"{resort_name}_{mode.value.lower()}.csv")

# Help Expander (exactly like old app)
with st.expander("How is the cost calculated?"):
    st.markdown("""
    **Renter Mode**  
    - Base cost = effective points × maintenance rate  
    - Last-minute discount reduces points required (25% ≤30 days, 30% ≤60 days)  
    - You pay on **effective** (discounted) points  

    **Owner Mode**  
    - Points used = raw points × (1 − discount %)  
    - Maintenance = points × current year rate (rounded up)  
    - Capital Cost = purchase price × cost of capital % / 365 × points  
    - Depreciation = (purchase price − salvage) / (life × 365) × points  
    - All costs rounded up per day
    """)

# Gantt Chart
year_str = str((adj_checkin or checkin).year)
resort_data = repo.get_resort(resort_name)
gantt_data = []

if resort_data and year_str in resort_data.years:
    yd = resort_data.years[year_str]
    for h in yd.holidays:
        gantt_data.append({"Task": h.name, "Start": h.start_date, "Finish": h.end_date + timedelta(1), "Type": "Holiday"})
    for s in yd.seasons:
        for i, p in enumerate(s.periods, 1):
            gantt_data.append({"Task": f"{s.name} #{i}", "Start": p.start, "Finish": p.end + timedelta(1), "Type": s.name})

if gantt_data:
    df_gantt = pd.DataFrame(gantt_data)
    color_map = {"Holiday": "#FF4444", "Low Season": "#90EE90", "High Season": "#FFA500", "Peak Season": "#FFD700"}
    fig = px.timeline(df_gantt, x_start="Start", x_end="Finish", y="Task", color="Type",
                      color_discrete_map=color_map, title=f"{resort_name} Season Calendar")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
