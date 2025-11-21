"""
MVC Calculator v2.0 - Optimized Architecture
Uses new v2.0 data schema with layered design
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
# DATA MODELS
# ====================================================================

class DiscountLevel(Enum):
    """Discount levels with built-in calculations"""
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
    """Represents a holiday period"""
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
    """Represents a season period"""
    name: str
    start_date: datetime.date
    end_date: datetime.date
    day_categories: Dict[str, Any]
    
    def contains(self, date: datetime.date) -> bool:
        return self.start_date <= date <= self.end_date


@dataclass
class DailyPointsData:
    """Complete data for a single day"""
    date: datetime.date
    day_of_week: str
    room_points: Dict[str, int]
    season: Optional[str] = None
    holiday: Optional[HolidayPeriod] = None
    
    def get_points(self, room_type: str) -> int:
        return self.room_points.get(room_type, 0)


# ====================================================================
# DATA REPOSITORY
# ====================================================================

class DataRepository:
    """Centralized data access with caching"""
    
    def __init__(self, data: Dict[str, Any]):
        self._data = data
        self._cache: Dict[str, Any] = {}
        self._points_cache: Dict[Tuple[str, str], DailyPointsData] = {}
        
        # Validate schema version
        self.schema_version = data.get("schema_version", "1.0.0")
        if not self.schema_version.startswith("2."):
            raise ValueError(f"Unsupported schema version: {self.schema_version}")
        
        # Index resorts by display name for easy lookup
        self._resorts_by_name = {
            r["display_name"]: r for r in data.get("resorts", [])
        }
    
    @property
    def resort_names(self) -> List[str]:
        """Get list of all resort display names"""
        return sorted(self._resorts_by_name.keys())
    
    def get_maintenance_rate(self, year: int) -> float:
        """Get maintenance rate for a year"""
        rates = self._data.get("configuration", {}).get("maintenance_rates", {})
        return rates.get(str(year), 0.86)
    
    def get_discount_policy(self, level: DiscountLevel) -> Dict:
        """Get discount policy details"""
        policies = self._data.get("configuration", {}).get("discount_policies", {})
        if level == DiscountLevel.EXECUTIVE:
            return policies.get("executive", {})
        elif level == DiscountLevel.PRESIDENTIAL:
            return policies.get("presidential", {})
        return {}
    
    def get_room_display_name(self, code: str) -> str:
        """Get display name for room code"""
        catalog = self._data.get("room_type_catalog", {})
        return catalog.get(code, {}).get("display_name", code)
    
    def get_resort_data(self, resort_name: str) -> Optional[Dict]:
        """Get complete resort data"""
        return self._resorts_by_name.get(resort_name)
    
    def get_global_holiday(self, year: int, holiday_name: str) -> Optional[Dict]:
        """Get global holiday definition"""
        holidays = self._data.get("global_holidays", {}).get(str(year), {})
        return holidays.get(holiday_name)
    
    def get_holidays(self, resort_name: str, year: int) -> List[HolidayPeriod]:
        """Get all holiday periods for a resort/year"""
        cache_key = f"holidays_{resort_name}_{year}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        resort = self.get_resort_data(resort_name)
        if not resort:
            return []
        
        year_data = resort.get("years", {}).get(str(year), {})
        holiday_list = year_data.get("holidays", [])
        
        holidays = []
        for holiday in holiday_list:
            # Resolve global reference if present
            if "global_reference" in holiday:
                global_holiday = self.get_global_holiday(year, holiday["global_reference"])
                if global_holiday:
                    start = datetime.strptime(global_holiday["start_date"], "%Y-%m-%d").date()
                    end = datetime.strptime(global_holiday["end_date"], "%Y-%m-%d").date()
                    holidays.append(HolidayPeriod(
                        name=holiday["name"],
                        start_date=start,
                        end_date=end,
                        room_points=holiday.get("room_points", {})
                    ))
            elif "start_date" in holiday and "end_date" in holiday:
                start = datetime.strptime(holiday["start_date"], "%Y-%m-%d").date()
                end = datetime.strptime(holiday["end_date"], "%Y-%m-%d").date()
                holidays.append(HolidayPeriod(
                    name=holiday["name"],
                    start_date=start,
                    end_date=end,
                    room_points=holiday.get("room_points", {})
                ))
        
        self._cache[cache_key] = holidays
        return holidays
    
    def get_seasons(self, resort_name: str, year: int) -> List[SeasonPeriod]:
        """Get all season periods for a resort/year"""
        cache_key = f"seasons_{resort_name}_{year}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        resort = self.get_resort_data(resort_name)
        if not resort:
            return []
        
        year_data = resort.get("years", {}).get(str(year), {})
        season_list = year_data.get("seasons", [])
        
        seasons = []
        for season in season_list:
            for period in season.get("periods", []):
                start = datetime.strptime(period["start"], "%Y-%m-%d").date()
                end = datetime.strptime(period["end"], "%Y-%m-%d").date()
                seasons.append(SeasonPeriod(
                    name=season["name"],
                    start_date=start,
                    end_date=end,
                    day_categories=season.get("day_categories", {})
                ))
        
        self._cache[cache_key] = seasons
        return seasons
    
    def get_daily_points(self, resort_name: str, date: datetime.date) -> DailyPointsData:
        """Get complete points data for a specific date"""
        cache_key = (resort_name, date.strftime("%Y-%m-%d"))
        if cache_key in self._points_cache:
            return self._points_cache[cache_key]
        
        day_of_week = date.strftime("%a")
        
        # Check for holiday first
        holidays = self.get_holidays(resort_name, date.year)
        holiday = next((h for h in holidays if h.contains(date)), None)
        
        if holiday:
            # Holiday points only on start date
            room_points = holiday.room_points if holiday.is_start(date) else {}
            result = DailyPointsData(
                date=date,
                day_of_week=day_of_week,
                room_points=room_points,
                season=None,
                holiday=holiday
            )
        else:
            # Regular season points
            seasons = self.get_seasons(resort_name, date.year)
            season = next((s for s in seasons if s.contains(date)), None)
            
            room_points = {}
            season_name = "Default Season"
            
            if season:
                season_name = season.name
                # Find matching day category
                for cat_name, cat_data in season.day_categories.items():
                    day_pattern = cat_data.get("day_pattern", [])
                    if day_of_week in day_pattern:
                        room_points = cat_data.get("room_points", {})
                        break
            
            result = DailyPointsData(
                date=date,
                day_of_week=day_of_week,
                room_points=room_points,
                season=season_name,
                holiday=None
            )
        
        self._points_cache[cache_key] = result
        return result
    
    def get_available_room_types(self, resort_name: str, date: datetime.date) -> List[str]:
        """Get all available room types for a resort on a given date"""
        daily_data = self.get_daily_points(resort_name, date)
        return sorted(daily_data.room_points.keys())
    
    def clear_cache(self):
        """Clear all caches"""
        self._cache.clear()
        self._points_cache.clear()


# ====================================================================
# CALCULATION ENGINE
# ====================================================================

class CalculationEngine:
    """Core calculation logic"""
    
    def __init__(self, repository: DataRepository):
        self.repo = repository
    
    def calculate_rental_stay(
        self,
        resort_name: str,
        room_type: str,
        checkin: datetime.date,
        nights: int,
        rate_per_point: float,
        discount: DiscountLevel
    ) -> Tuple[pd.DataFrame, int, int, float]:
        """
        Calculate rental breakdown
        Returns: (breakdown_df, discounted_points, raw_points, total_rent)
        """
        rows = []
        total_discounted = 0
        total_raw = 0
        total_rent = 0
        current_holiday = None
        
        for i in range(nights):
            date = checkin + timedelta(days=i)
            daily_data = self.repo.get_daily_points(resort_name, date)
            raw_points = daily_data.get_points(room_type)
            
            # Apply discount to points
            discounted_points = math.floor(raw_points * discount.multiplier)
            
            # Rent based on RAW points
            rent = math.ceil(raw_points * rate_per_point)
            
            # Handle holiday consolidation
            if daily_data.holiday:
                if daily_data.holiday.is_start(date):
                    current_holiday = daily_data.holiday
                    rows.append({
                        "Date": f"{current_holiday.name} ({self._fmt_date(current_holiday.start_date)} - {self._fmt_date(current_holiday.end_date)})",
                        "Day": "",
                        "Rent": f"${rent}",
                        "Undiscounted Points": raw_points,
                        "Discount": discount.description.split("(")[0].strip(),
                        "Points Used": discounted_points
                    })
                    total_discounted += discounted_points
                    total_raw += raw_points
                    total_rent += rent
                continue
            
            current_holiday = None
            rows.append({
                "Date": self._fmt_date(date),
                "Day": daily_data.day_of_week,
                "Rent": f"${rent}",
                "Undiscounted Points": raw_points,
                "Discount": discount.description.split("(")[0].strip() if discount != DiscountLevel.NONE else "None",
                "Points Used": discounted_points
            })
            total_discounted += discounted_points
            total_raw += raw_points
            total_rent += rent
        
        df = pd.DataFrame(rows)
        return df, total_discounted, total_raw, total_rent
    
    def calculate_ownership_stay(
        self,
        resort_name: str,
        room_type: str,
        checkin: datetime.date,
        nights: int,
        rate_per_point: float,
        purchase_price: float,
        cost_of_capital: float,
        useful_life: int,
        salvage_value: float,
        discount: DiscountLevel,
        include_maint: bool,
        include_cap: bool,
        include_dep: bool
    ) -> Tuple[pd.DataFrame, int, float, float, float, float]:
        """
        Calculate ownership cost breakdown
        Returns: (df, total_points, total_cost, maint_cost, cap_cost, dep_cost)
        """
        rows = []
        total_points = 0
        total_maint = 0
        total_cap = 0
        total_dep = 0
        current_holiday = None
        
        dep_per_point = (purchase_price - salvage_value) / useful_life if include_dep and useful_life > 0 else 0
        
        for i in range(nights):
            date = checkin + timedelta(days=i)
            daily_data = self.repo.get_daily_points(resort_name, date)
            raw_points = daily_data.get_points(room_type)
            
            # Apply discount
            points = math.floor(raw_points * discount.multiplier)
            
            # Calculate costs
            maint = math.ceil(points * rate_per_point) if include_maint else 0
            cap = math.ceil(points * purchase_price * cost_of_capital) if include_cap else 0
            dep = math.ceil(points * dep_per_point) if include_dep else 0
            day_cost = maint + cap + dep
            
            # Handle holiday consolidation
            if daily_data.holiday:
                if daily_data.holiday.is_start(date):
                    current_holiday = daily_data.holiday
                    row = {
                        "Date": f"{current_holiday.name} ({self._fmt_date(current_holiday.start_date)} - {self._fmt_date(current_holiday.end_date)})",
                        "Day": "",
                        "Points": points
                    }
                    if include_maint:
                        row["Maintenance"] = f"${maint}"
                    if include_cap:
                        row["Capital Cost"] = f"${cap}"
                    if include_dep:
                        row["Depreciation"] = f"${dep}"
                    row["Total Cost"] = f"${day_cost}"
                    
                    rows.append(row)
                    total_points += points
                    total_maint += maint
                    total_cap += cap
                    total_dep += dep
                continue
            
            current_holiday = None
            row = {
                "Date": self._fmt_date(date),
                "Day": daily_data.day_of_week,
                "Points": points
            }
            if include_maint:
                row["Maintenance"] = f"${maint}"
            if include_cap:
                row["Capital Cost"] = f"${cap}"
            if include_dep:
                row["Depreciation"] = f"${dep}"
            row["Total Cost"] = f"${day_cost}"
            
            rows.append(row)
            total_points += points
            total_maint += maint
            total_cap += cap
            total_dep += dep
        
        df = pd.DataFrame(rows)
        total_cost = total_maint + total_cap + total_dep
        return df, total_points, total_cost, total_maint, total_cap, total_dep
    
    def adjust_for_holiday_weeks(
        self,
        resort_name: str,
        checkin: datetime.date,
        nights: int
    ) -> Tuple[datetime.date, int, bool]:
        """
        Adjust date range to include full holiday weeks
        Returns: (adjusted_checkin, adjusted_nights, was_adjusted)
        """
        checkout = checkin + timedelta(days=nights - 1)
        holidays = self.repo.get_holidays(resort_name, checkin.year)
        
        overlapping = [h for h in holidays if h.start_date <= checkout and h.end_date >= checkin]
        
        if not overlapping:
            return checkin, nights, False
        
        earliest_start = min(h.start_date for h in overlapping)
        latest_end = max(h.end_date for h in overlapping)
        
        adjusted_checkin = min(checkin, earliest_start)
        adjusted_nights = (max(checkout, latest_end) - adjusted_checkin).days + 1
        
        return adjusted_checkin, adjusted_nights, True
    
    def _fmt_date(self, date: datetime.date) -> str:
        return date.strftime("%d %b %Y")


# ====================================================================
# UI LAYER
# ====================================================================

def setup_page():
    st.set_page_config(page_title="MVC Calculator v2.0", layout="wide")
    st.markdown("""
    <style>
        .stButton button {
            font-size: 12px !important;
            padding: 5px 10px !important;
            height: auto !important;
        }
        .block-container {
            padding-top: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)


def initialize_session_state():
    defaults = {
        "current_resort": None,
        "data_loaded": False
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def load_data() -> Optional[DataRepository]:
    """Load data and create repository"""
    try:
        with open("data_v2.json", "r") as f:
            data = json.load(f)
        return DataRepository(data)
    except FileNotFoundError:
        st.error("data_v2.json not found. Please ensure the v2.0 data file exists.")
        return None
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None


def create_gantt_chart(repo: DataRepository, resort_name: str, year: int):
    """Create Gantt chart for seasons and holidays"""
    rows = []
    
    # Add seasons
    seasons = repo.get_seasons(resort_name, year)
    for i, season in enumerate(seasons, 1):
        rows.append({
            "Task": f"{season.name} #{i}",
            "Start": season.start_date,
            "Finish": season.end_date,
            "Type": season.name
        })
    
    # Add holidays
    holidays = repo.get_holidays(resort_name, year)
    for holiday in holidays:
        rows.append({
            "Task": holiday.name,
            "Start": holiday.start_date,
            "Finish": holiday.end_date,
            "Type": "Holiday"
        })
    
    if not rows:
        return None
    
    df = pd.DataFrame(rows)
    df["Start"] = pd.to_datetime(df["Start"])
    df["Finish"] = pd.to_datetime(df["Finish"])
    
    # Color mapping
    color_map = {
        "Holiday": "rgb(255,99,71)",
        "Low Season": "rgb(135,206,250)",
        "High Season": "rgb(255,69,0)",
        "Peak Season": "rgb(255,215,0)",
        "Mid Season": "rgb(60,179,113)"
    }
    colors = {t: color_map.get(t, "rgb(169,169,169)") for t in df["Type"].unique()}
    
    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="Type",
        color_discrete_map=colors,
        title=f"{resort_name} Seasons & Holidays ({year})",
        height=max(400, len(df) * 35)
    )
    
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickformat="%d %b %Y")
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>Start: %{base|%d %b %Y}<br>End: %{x|%d %b %Y}<extra></extra>"
    )
    fig.update_layout(showlegend=True, xaxis_title="Date", yaxis_title="Period")
    
    return fig


def main():
    """Main application"""
    setup_page()
    initialize_session_state()
    
    # Load data
    repo = load_data()
    if not repo:
        st.stop()
    
    st.title("🏖️ Marriott Vacation Club Calculator v2.0")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")
        user_mode = st.selectbox("User Mode", ["Renter", "Owner"], key="mode")
        
        if user_mode == "Owner":
            config = repo._data.get("configuration", {}).get("default_values", {})
            
            purchase_price = st.number_input(
                "Purchase Price per Point ($)",
                min_value=0.0,
                value=float(config.get("purchase_price_per_point", 16.0)),
                step=0.1
            )
            
            discount_idx = st.selectbox(
                "Last-Minute Discount",
                [0, 1, 2],
                format_func=lambda x: list(DiscountLevel)[x].description
            )
            discount = list(DiscountLevel)[discount_idx]
            
            inc_maint = st.checkbox("Include Maintenance Cost", True)
            maint_rate = st.number_input(
                "Maintenance Rate per Point ($)",
                min_value=0.0,
                value=repo.get_maintenance_rate(2026),
                step=0.01,
                disabled=not inc_maint
            )
            
            inc_cap = st.checkbox("Include Capital Cost", True)
            coc = st.number_input(
                "Cost of Capital (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(config.get("cost_of_capital", 0.07) * 100),
                step=0.1
            ) / 100 if inc_cap else 0.07
            
            inc_dep = st.checkbox("Include Depreciation Cost", True)
            useful_life = st.number_input(
                "Useful Life (Years)",
                min_value=1,
                value=int(config.get("useful_life_years", 15))
            ) if inc_dep else 15
            salvage = st.number_input(
                "Salvage Value per Point ($)",
                min_value=0.0,
                value=float(config.get("salvage_value_per_point", 3.0)),
                step=0.1
            ) if inc_dep else 3.0
        else:  # Renter
            allow_mod = st.checkbox("More Options", key="allow_renter_mod")
            
            if allow_mod:
                opt = st.radio("Rate/Discount Option", [
                    "Based on Maintenance Rate (No Discount)",
                    "Custom Rate (No Discount)",
                    "Executive: 25% Points Discount (within 30 days)",
                    "Presidential: 30% Points Discount (within 60 days)"
                ])
                
                if opt == "Custom Rate (No Discount)":
                    rate_per_point = st.number_input(
                        "Custom Rate per Point ($)",
                        min_value=0.0,
                        value=repo.get_maintenance_rate(2026),
                        step=0.01
                    )
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
    resort_names = repo.resort_names
    current_resort = st.session_state.current_resort
    
    for i, resort_name in enumerate(resort_names):
        with cols[i % 6]:
            if st.button(
                resort_name,
                key=f"resort_{i}",
                type="primary" if current_resort == resort_name else "secondary"
            ):
                st.session_state.current_resort = resort_name
                st.rerun()
    
    resort = st.session_state.current_resort
    if not resort:
        st.warning("Please select a resort to continue.")
        st.stop()
    
    # Main inputs
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        checkin = st.date_input(
            "Check-in Date",
            value=datetime(2026, 2, 20).date(),
            min_value=datetime(2025, 1, 3).date(),
            max_value=datetime(2026, 12, 31).date()
        )
    
    with col2:
        nights = st.number_input("Number of Nights", min_value=1, max_value=30, value=7)
    
    # Get available room types
    room_types = repo.get_available_room_types(resort, checkin)
    
    with col3:
        room = st.selectbox("Select Room Type", room_types)
    
    with col4:
        compare = st.multiselect("Compare With", [r for r in room_types if r != room])
    
    # Create calculation engine
    engine = CalculationEngine(repo)
    
    # Adjust for holiday weeks
    adj_checkin, adj_nights, adjusted = engine.adjust_for_holiday_weeks(resort, checkin, nights)
    
    if adjusted:
        end_date = adj_checkin + timedelta(days=adj_nights - 1)
        st.info(
            f"Adjusted to full holiday week: **{engine._fmt_date(adj_checkin)} – "
            f"{engine._fmt_date(end_date)}** ({adj_nights} nights)"
        )
    
    # Calculate results
    if user_mode == "Renter":
        df, disc_pts, raw_pts, total_rent = engine.calculate_rental_stay(
            resort, room, adj_checkin, adj_nights, rate_per_point, discount
        )
        
        st.subheader(f"{resort} Rental Breakdown")
        st.dataframe(df, use_container_width=True)
        
        if discount != DiscountLevel.NONE:
            st.success(f"**{discount.description}** Applied")
        
        st.success(
            f"Total Undiscounted Points: {raw_pts:,} | "
            f"Total Points Used: {disc_pts:,} | "
            f"Final Total Rent: **${total_rent:,}**"
        )
        
        st.download_button(
            "Download Breakdown CSV",
            df.to_csv(index=False),
            f"{resort}_{adj_checkin}_rental.csv",
            "text/csv"
        )
    else:  # Owner
        df, pts, total_cost, m_cost, c_cost, d_cost = engine.calculate_ownership_stay(
            resort, room, adj_checkin, adj_nights,
            maint_rate, purchase_price, coc, useful_life, salvage,
            discount, inc_maint, inc_cap, inc_dep
        )
        
        st.subheader(f"{resort} Ownership Cost Breakdown")
        st.dataframe(df, use_container_width=True)
        
        st.success(f"Total Points Used: {pts:,} | Total Cost: **${total_cost:,}**")
        
        if inc_maint and m_cost:
            st.info(f"Maintenance Cost: ${m_cost:,}")
        if inc_cap and c_cost:
            st.info(f"Capital Cost: ${c_cost:,}")
        if inc_dep and d_cost:
            st.info(f"Depreciation Cost: ${d_cost:,}")
        
        st.download_button(
            "Download Breakdown CSV",
            df.to_csv(index=False),
            f"{resort}_{adj_checkin}_owner.csv",
            "text/csv"
        )
    
    # Gantt chart
    gantt = create_gantt_chart(repo, resort, checkin.year)
    if gantt:
        st.plotly_chart(gantt, use_container_width=True)


if __name__ == "__main__":
    main()
