# ====================================================================
# OPTIMIZED MVC CALCULATOR - REFACTORED ARCHITECTURE
# ====================================================================

import streamlit as st
import math
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import plotly.express as px
from functools import lru_cache

# ====================================================================
# 1. DATA MODELS - Type-safe data structures
# ====================================================================

class DiscountLevel(Enum):
    """Enum for discount levels with built-in calculation"""
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


@dataclass
class CostBreakdown:
    """Owner cost breakdown"""
    maintenance: float = 0
    capital_cost: float = 0
    depreciation: float = 0
    
    @property
    def total(self) -> float:
        return self.maintenance + self.capital_cost + self.depreciation


@dataclass
class RentalConfig:
    """Configuration for rental calculations"""
    rate_per_point: float
    discount: DiscountLevel = DiscountLevel.NONE


@dataclass
class OwnershipConfig:
    """Configuration for ownership calculations"""
    maintenance_rate: float
    purchase_price_per_point: float
    cost_of_capital: float = 0.07
    useful_life_years: int = 15
    salvage_value_per_point: float = 3.0
    discount: DiscountLevel = DiscountLevel.NONE
    include_maintenance: bool = True
    include_capital: bool = True
    include_depreciation: bool = True
    
    @property
    def depreciation_per_point(self) -> float:
        if not self.include_depreciation or self.useful_life_years <= 0:
            return 0
        return (self.purchase_price_per_point - self.salvage_value_per_point) / self.useful_life_years


# ====================================================================
# 2. DATA ACCESS LAYER - Separate data loading from business logic
# ====================================================================

class DataRepository:
    """Centralized data access with caching"""
    
    def __init__(self, data: Dict[str, Any]):
        self._data = data
        self._cache: Dict[str, Any] = {}
        self._points_cache: Dict[Tuple[str, str], DailyPointsData] = {}
    
    @property
    def resorts(self) -> List[str]:
        return self._data.get("resorts_list", [])
    
    def get_maintenance_rate(self, year: int) -> float:
        rates = self._data.get("maintenance_rates", {})
        return rates.get(str(year), 0.86)
    
    def get_room_legend(self) -> Dict[str, str]:
        return self._data.get("room_view_legend", {})
    
    def get_holidays(self, resort: str, year: int) -> List[HolidayPeriod]:
        """Get all holiday periods for a resort/year"""
        cache_key = f"holidays_{resort}_{year}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        holidays = []
        holiday_data = self._data.get("holiday_weeks", {}).get(resort, {}).get(str(year), {})
        
        for name, date_range in holiday_data.items():
            if isinstance(date_range, str) and date_range.startswith("global:"):
                date_range = self._resolve_global(year, date_range.split(":", 1)[1])
            
            if len(date_range) >= 2:
                try:
                    start = datetime.strptime(date_range[0], "%Y-%m-%d").date()
                    end = datetime.strptime(date_range[1], "%Y-%m-%d").date()
                    holidays.append(HolidayPeriod(name, start, end))
                except:
                    continue
        
        self._cache[cache_key] = holidays
        return holidays
    
    def get_seasons(self, resort: str, year: int) -> List[SeasonPeriod]:
        """Get all season periods for a resort/year"""
        cache_key = f"seasons_{resort}_{year}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        seasons = []
        season_data = self._data.get("season_blocks", {}).get(resort, {}).get(str(year), {})
        
        for name, ranges in season_data.items():
            for start_str, end_str in ranges:
                try:
                    start = datetime.strptime(start_str, "%Y-%m-%d").date()
                    end = datetime.strptime(end_str, "%Y-%m-%d").date()
                    seasons.append(SeasonPeriod(name, start, end))
                except:
                    continue
        
        self._cache[cache_key] = seasons
        return seasons
    
    def get_daily_points(self, resort: str, date: datetime.date) -> DailyPointsData:
        """Get complete points data for a specific date"""
        cache_key = (resort, date.strftime("%Y-%m-%d"))
        if cache_key in self._points_cache:
            return self._points_cache[cache_key]
        
        # Determine holiday
        holidays = self.get_holidays(resort, date.year)
        holiday = next((h for h in holidays if h.contains(date)), None)
        
        # Determine season
        season_name = "Default Season"
        if not holiday:
            seasons = self.get_seasons(resort, date.year)
            season = next((s for s in seasons if s.contains(date)), None)
            if season:
                season_name = season.name
        
        # Get points
        ref_points = self._data.get("reference_points", {}).get(resort, {})
        room_points = {}
        
        if holiday:
            # Holiday points (only on start date)
            if holiday.is_start(date):
                points_data = ref_points.get("Holiday Week", {}).get(holiday.name, {})
                room_points = {self._display_room(k): v for k, v in points_data.items()}
        else:
            # Regular season points
            day_cat = self._get_day_category(date)
            season_points = ref_points.get(season_name, {})
            
            # Try exact day category first, then fallback
            if day_cat in season_points:
                points_data = season_points[day_cat]
            elif "Sun-Thu" in season_points and day_cat in ["Sun", "Mon-Thu"]:
                points_data = season_points["Sun-Thu"]
            else:
                points_data = {}
            
            room_points = {self._display_room(k): v for k, v in points_data.items()}
        
        result = DailyPointsData(
            date=date,
            day_of_week=date.strftime("%a"),
            room_points=room_points,
            season=season_name if not holiday else None,
            holiday=holiday
        )
        
        self._points_cache[cache_key] = result
        return result
    
    def get_available_room_types(self, resort: str, date: datetime.date) -> List[str]:
        """Get all available room types for a resort on a given date"""
        daily_data = self.get_daily_points(resort, date)
        return sorted(daily_data.room_points.keys())
    
    def _resolve_global(self, year: int, key: str) -> List[str]:
        return self._data.get("global_dates", {}).get(str(year), {}).get(key, [])
    
    def _get_day_category(self, date: datetime.date) -> str:
        dow = date.strftime("%a")
        if dow in {"Fri", "Sat"}:
            return "Fri-Sat"
        elif dow == "Sun":
            return "Sun"
        else:
            return "Mon-Thu"
    
    def _display_room(self, key: str) -> str:
        """Convert internal room key to display name"""
        legend = self.get_room_legend()
        if key in legend:
            return legend[key]
        # Add additional logic as needed
        return key
    
    def clear_cache(self):
        """Clear all caches"""
        self._cache.clear()
        self._points_cache.clear()


# ====================================================================
# 3. BUSINESS LOGIC LAYER - Pure calculation functions
# ====================================================================

class CalculationEngine:
    """Core calculation logic separated from UI"""
    
    def __init__(self, repository: DataRepository):
        self.repo = repository
    
    def calculate_rental_stay(
        self, 
        resort: str, 
        room_type: str,
        checkin: datetime.date,
        nights: int,
        config: RentalConfig
    ) -> Tuple[pd.DataFrame, int, int, float]:
        """
        Calculate rental breakdown for a stay
        Returns: (breakdown_df, discounted_points, raw_points, total_rent)
        """
        rows = []
        total_discounted_points = 0
        total_raw_points = 0
        total_rent = 0
        
        current_holiday = None
        
        for i in range(nights):
            date = checkin + timedelta(days=i)
            daily_data = self.repo.get_daily_points(resort, date)
            raw_points = daily_data.get_points(room_type)
            
            # Apply discount to points
            discounted_points = math.floor(raw_points * config.discount.multiplier)
            
            # Rent is ALWAYS based on raw points (no discount affects rent)
            rent = math.ceil(raw_points * config.rate_per_point)
            
            # Handle holiday consolidation
            if daily_data.holiday:
                if daily_data.holiday.is_start(date):
                    current_holiday = daily_data.holiday
                    rows.append({
                        "Date": f"{current_holiday.name} ({self._fmt_date(current_holiday.start_date)} - {self._fmt_date(current_holiday.end_date)})",
                        "Day": "",
                        "Rent": f"${rent}",
                        "Undiscounted Points": raw_points,
                        "Discount": config.discount.description.split("(")[0].strip(),
                        "Points Used": discounted_points
                    })
                    total_discounted_points += discounted_points
                    total_raw_points += raw_points
                    total_rent += rent
                # Skip subsequent holiday days
                continue
            
            current_holiday = None
            rows.append({
                "Date": self._fmt_date(date),
                "Day": daily_data.day_of_week,
                "Rent": f"${rent}",
                "Undiscounted Points": raw_points,
                "Discount": config.discount.description.split("(")[0].strip() if config.discount != DiscountLevel.NONE else "None",
                "Points Used": discounted_points
            })
            total_discounted_points += discounted_points
            total_raw_points += raw_points
            total_rent += rent
        
        df = pd.DataFrame(rows)
        return df, total_discounted_points, total_raw_points, total_rent
    
    def calculate_ownership_stay(
        self,
        resort: str,
        room_type: str,
        checkin: datetime.date,
        nights: int,
        config: OwnershipConfig
    ) -> Tuple[pd.DataFrame, int, CostBreakdown]:
        """
        Calculate ownership cost breakdown
        Returns: (breakdown_df, total_points, cost_breakdown)
        """
        rows = []
        total_points = 0
        total_costs = CostBreakdown()
        current_holiday = None
        
        for i in range(nights):
            date = checkin + timedelta(days=i)
            daily_data = self.repo.get_daily_points(resort, date)
            raw_points = daily_data.get_points(room_type)
            
            # Apply discount to points
            discounted_points = math.floor(raw_points * config.discount.multiplier)
            
            # Calculate costs based on discounted points
            daily_costs = CostBreakdown()
            if config.include_maintenance:
                daily_costs.maintenance = math.ceil(discounted_points * config.maintenance_rate)
            if config.include_capital:
                daily_costs.capital_cost = math.ceil(
                    discounted_points * config.purchase_price_per_point * config.cost_of_capital
                )
            if config.include_depreciation:
                daily_costs.depreciation = math.ceil(
                    discounted_points * config.depreciation_per_point
                )
            
            # Handle holiday consolidation
            if daily_data.holiday:
                if daily_data.holiday.is_start(date):
                    current_holiday = daily_data.holiday
                    row = {
                        "Date": f"{current_holiday.name} ({self._fmt_date(current_holiday.start_date)} - {self._fmt_date(current_holiday.end_date)})",
                        "Day": "",
                        "Points": discounted_points
                    }
                    if config.include_maintenance:
                        row["Maintenance"] = f"${daily_costs.maintenance}"
                    if config.include_capital:
                        row["Capital Cost"] = f"${daily_costs.capital_cost}"
                    if config.include_depreciation:
                        row["Depreciation"] = f"${daily_costs.depreciation}"
                    row["Total Cost"] = f"${daily_costs.total}"
                    
                    rows.append(row)
                    total_points += discounted_points
                    total_costs.maintenance += daily_costs.maintenance
                    total_costs.capital_cost += daily_costs.capital_cost
                    total_costs.depreciation += daily_costs.depreciation
                continue
            
            current_holiday = None
            row = {
                "Date": self._fmt_date(date),
                "Day": daily_data.day_of_week,
                "Points": discounted_points
            }
            if config.include_maintenance:
                row["Maintenance"] = f"${daily_costs.maintenance}"
            if config.include_capital:
                row["Capital Cost"] = f"${daily_costs.capital_cost}"
            if config.include_depreciation:
                row["Depreciation"] = f"${daily_costs.depreciation}"
            row["Total Cost"] = f"${daily_costs.total}"
            
            rows.append(row)
            total_points += discounted_points
            total_costs.maintenance += daily_costs.maintenance
            total_costs.capital_cost += daily_costs.capital_cost
            total_costs.depreciation += daily_costs.depreciation
        
        df = pd.DataFrame(rows)
        return df, total_points, total_costs
    
    def adjust_for_holiday_weeks(
        self,
        resort: str,
        checkin: datetime.date,
        nights: int
    ) -> Tuple[datetime.date, int, bool]:
        """
        Adjust date range to include full holiday weeks
        Returns: (adjusted_checkin, adjusted_nights, was_adjusted)
        """
        checkout = checkin + timedelta(days=nights - 1)
        holidays = self.repo.get_holidays(resort, checkin.year)
        
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
# 4. UI LAYER - Streamlit components (simplified example)
# ====================================================================

class MVCCalculatorUI:
    """UI layer - handles all Streamlit interactions"""
    
    def __init__(self, repository: DataRepository, engine: CalculationEngine):
        self.repo = repository
        self.engine = engine
        self._setup_page()
    
    def _setup_page(self):
        st.set_page_config(page_title="MVC Calculator", layout="wide")
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
    
    def render(self):
        """Main render method"""
        st.title("Marriott Vacation Club Calculator")
        
        # Sidebar configuration
        with st.sidebar:
            mode, config = self._render_sidebar()
        
        # Resort selection
        resort = self._render_resort_selection()
        if not resort:
            st.warning("Please select a resort")
            return
        
        # Main inputs
        checkin, nights, room_type = self._render_main_inputs(resort)
        
        # Adjust for holidays
        adj_checkin, adj_nights, adjusted = self.engine.adjust_for_holiday_weeks(
            resort, checkin, nights
        )
        
        if adjusted:
            st.info(f"Adjusted to full holiday week: {adj_checkin} to {adj_checkin + timedelta(days=adj_nights-1)}")
        
        # Calculate and display results
        if mode == "Renter":
            self._render_rental_results(resort, room_type, adj_checkin, adj_nights, config)
        else:
            self._render_ownership_results(resort, room_type, adj_checkin, adj_nights, config)
    
    def _render_sidebar(self) -> Tuple[str, Any]:
        """Render sidebar and return mode and config"""
        st.header("Configuration")
        mode = st.selectbox("User Mode", ["Renter", "Owner"])
        
        if mode == "Renter":
            rate = st.number_input("Rate per Point", value=0.86, step=0.01)
            discount_idx = st.selectbox("Discount Level", [0, 1, 2], format_func=lambda x: list(DiscountLevel)[x].description)
            discount = list(DiscountLevel)[discount_idx]
            config = RentalConfig(rate_per_point=rate, discount=discount)
        else:
            # Owner configuration inputs
            config = OwnershipConfig(
                maintenance_rate=st.number_input("Maintenance Rate", value=0.86, step=0.01),
                purchase_price_per_point=st.number_input("Purchase Price/Point", value=16.0, step=0.1)
                # Add more inputs as needed
            )
        
        return mode, config
    
    def _render_resort_selection(self) -> Optional[str]:
        """Render resort selection buttons"""
        resorts = self.repo.resorts
        cols = st.columns(6)
        
        for i, resort in enumerate(resorts):
            with cols[i % 6]:
                if st.button(resort, key=f"resort_{resort}"):
                    return resort
        
        return st.session_state.get('selected_resort')
    
    def _render_main_inputs(self, resort: str) -> Tuple[datetime.date, int, str]:
        """Render main input fields"""
        col1, col2, col3 = st.columns(3)
        
        with col1:
            checkin = st.date_input("Check-in", value=datetime(2026, 2, 20).date())
        with col2:
            nights = st.number_input("Nights", min_value=1, max_value=30, value=7)
        with col3:
            room_types = self.repo.get_available_room_types(resort, checkin)
            room_type = st.selectbox("Room Type", room_types)
        
        return checkin, nights, room_type
    
    def _render_rental_results(self, resort, room_type, checkin, nights, config):
        """Render rental calculation results"""
        df, disc_pts, raw_pts, total_rent = self.engine.calculate_rental_stay(
            resort, room_type, checkin, nights, config
        )
        
        st.subheader("Rental Breakdown")
        st.dataframe(df, use_container_width=True)
        st.success(f"Total Points: {disc_pts:,} | Total Rent: ${total_rent:,.0f}")
    
    def _render_ownership_results(self, resort, room_type, checkin, nights, config):
        """Render ownership calculation results"""
        df, total_pts, costs = self.engine.calculate_ownership_stay(
            resort, room_type, checkin, nights, config
        )
        
        st.subheader("Ownership Cost Breakdown")
        st.dataframe(df, use_container_width=True)
        st.success(f"Total Points: {total_pts:,} | Total Cost: ${costs.total:,.0f}")


# ====================================================================
# 5. APPLICATION BOOTSTRAP
# ====================================================================

def load_data() -> Optional[Dict]:
    """Load data from file or session state"""
    if 'data' in st.session_state and st.session_state.data:
        return st.session_state.data
    
    try:
        with open("data.json", "r") as f:
            data = json.load(f)
            st.session_state.data = data
            return data
    except FileNotFoundError:
        st.error("No data.json found")
        return None


def main():
    """Application entry point"""
    data = load_data()
    if not data:
        return
    
    # Initialize layers
    repository = DataRepository(data)
    engine = CalculationEngine(repository)
    ui = MVCCalculatorUI(repository, engine)
    
    # Render application
    ui.render()


if __name__ == "__main__":
    main()
