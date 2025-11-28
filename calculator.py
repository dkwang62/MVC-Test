import math
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from enum import Enum
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict
import pandas as pd
import plotly.express as px
import streamlit as st
from common.ui import render_resort_card, render_resort_grid, render_page_header
from common.charts import create_gantt_chart_from_resort_data
from common.data import ensure_data_in_session

# ==============================================================================
# LAYER 1: DOMAIN MODELS (Type-Safe Data Structures)
# ==============================================================================
class UserMode(Enum):
    RENTER = "Renter"
    OWNER = "Owner"

class DiscountPolicy(Enum):
    NONE = "None"
    EXECUTIVE = "within_30_days"  # 25%
    PRESIDENTIAL = "within_60_days"  # 30%

@dataclass
class Holiday:
    name: str
    start_date: date
    end_date: date
    room_points: Dict[str, int]

@dataclass
class DayCategory:
    days: List[str]
    room_points: Dict[str, int]

@dataclass
class SeasonPeriod:
    start: date
    end: date

@dataclass
class Season:
    name: str
    periods: List[SeasonPeriod]
    day_categories: List[DayCategory]

@dataclass
class ResortData:
    id: str
    name: str
    years: Dict[str, "YearData"]

@dataclass
class YearData:
    holidays: List[Holiday]
    seasons: List[Season]

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

@dataclass
class ComparisonResult:
    pivot_df: pd.DataFrame
    daily_chart_df: pd.DataFrame
    holiday_chart_df: pd.DataFrame

# ==============================================================================
# LAYER 2: REPOSITORY (Data Access Layer)
# ==============================================================================
class MVCRepository:
    def __init__(self, raw_data: dict):
        self._raw = raw_data
        self._resort_cache: Dict[str, ResortData] = {}
        self._global_holidays = self._parse_global_holidays()

    def get_resort_list(self) -> List[str]:
        return sorted([r["display_name"] for r in self._raw.get("resorts", [])])

    def get_resort_list_full(self) -> List[Dict[str, Any]]:
        """Return raw resort dictionaries (used for grid rendering)."""
        return self._raw.get("resorts", [])

    def _parse_global_holidays(
        self,
    ) -> Dict[str, Dict[str, Tuple[date, date]]]:
        parsed: Dict[str, Dict[str, Tuple[date, date]]] = {}
        for year, hols in self._raw.get("global_holidays", {}).items():
            parsed[year] = {}
            for name, data in hols.items():
                try:
                    parsed[year][name] = (
                        datetime.strptime(data["start_date"], "%Y-%m-%d").date(),
                        datetime.strptime(data["end_date"], "%Y-%m-%d").date(),
                    )
                except Exception:
                    continue
        return parsed

    def get_resort(self, resort_name: str) -> Optional[ResortData]:
        if resort_name in self._resort_cache:
            return self._resort_cache[resort_name]
        raw_r = next(
            (r for r in self._raw.get("resorts", []) if r["display_name"] == resort_name),
            None,
        )
        if not raw_r:
            return None
        years_data: Dict[str, YearData] = {}
        for year_str, y_content in raw_r.get("years", {}).items():
            holidays: List[Holiday] = []
            for h in y_content.get("holidays", []):
                ref = h.get("global_reference")
                if ref and ref in self._global_holidays.get(year_str, {}):
                    g_dates = self._global_holidays[year_str][ref]
                    holidays.append(
                        Holiday(
                            name=h.get("name", ref),
                            start_date=g_dates[0],
                            end_date=g_dates[1],
                            room_points=h.get("room_points", {}),
                        )
                    )
            seasons: List[Season] = []
            for s in y_content.get("seasons", []):
                periods: List[SeasonPeriod] = []
                for p in s.get("periods", []):
                    try:
                        periods.append(
                            SeasonPeriod(
                                start=datetime.strptime(p["start"], "%Y-%m-%d").date(),
                                end=datetime.strptime(p["end"], "%Y-%m-%d").date(),
                            )
                        )
                    except Exception:
                        continue
                day_cats: List[DayCategory] = []
                for cat in s.get("day_categories", {}).values():
                    day_cats.append(
                        DayCategory(
                            days=cat.get("day_pattern", []),
                            room_points=cat.get("room_points", {}),
                        )
                    )
                seasons.append(Season(name=s["name"], periods=periods, day_categories=day_cats))
            years_data[year_str] = YearData(holidays=holidays, seasons=seasons)
        resort_obj = ResortData(
            id=raw_r["id"], name=raw_r["display_name"], years=years_data
        )
        self._resort_cache[resort_name] = resort_obj
        return resort_obj

    def get_resort_info(self, resort_name: str) -> Dict[str, str]:
        """Get additional resort information for card display."""
        raw_r = next(
            (r for r in self._raw.get("resorts", []) if r["display_name"] == resort_name),
            None,
        )
        if raw_r:
            return {
                "full_name": raw_r.get("resort_name", resort_name),
                "timezone": raw_r.get("timezone", "Unknown"),
                "address": raw_r.get("address", "Address not available"),
            }
        return {
            "full_name": resort_name,
            "timezone": "Unknown",
            "address": "Address not available",
        }

# ==============================================================================
# LAYER 3: SERVICE (Pure Business Logic Engine)
# ==============================================================================
class MVCCalculator:
    def __init__(self, repo: MVCRepository):
        self.repo = repo

    def _get_daily_points(
        self,
        resort: ResortData,
        day: date
    ) -> Tuple[Dict[str, int], Optional[Holiday]]:
        year_str = str(day.year)
        if year_str not in resort.years:
            return {}, None
        yd = resort.years[year_str]
        # Check holiday first
        for h in yd.holidays:
            if h.start_date <= day <= h.end_date:
                return h.room_points, h
        # Then regular seasons
        dow_map = {
            0: "Mon",
            1: "Tue",
            2: "Wed",
            3: "Thu",
            4: "Fri",
            5: "Sat",
            6: "Sun",
        }
        dow = dow_map[day.weekday()]
        for s in yd.seasons:
            for p in s.periods:
                if p.start <= day <= p.end:
                    for cat in s.day_categories:
                        if dow in cat.days:
                            return cat.room_points, None
        return {}, None

    def calculate_breakdown(
        self,
        resort_name: str,
        room: str,
        checkin: date,
        nights: int,
        user_mode: UserMode,
        rate: float,
        discount_policy: DiscountPolicy = DiscountPolicy.NONE,
        owner_config: Optional[dict] = None,
    ) -> CalculationResult:
        resort = self.repo.get_resort(resort_name)
        if not resort:
            return CalculationResult(
                breakdown_df=pd.DataFrame(),
                total_points=0,
                financial_total=0.0,
                discount_applied=False,
                discounted_days=[],
            )
        rows: List[Dict[str, Any]] = []
        tot_eff_pts = 0
        tot_financial = 0.0
        tot_m = tot_c = tot_d = 0.0
        disc_applied = False
        disc_days: List[str] = []
        is_owner = user_mode == UserMode.OWNER
        processed_holidays: set[str] = set()
        i = 0
        today = datetime.now().date()
        while i < nights:
            d = checkin + timedelta(days=i)
            d_str = d.strftime("%Y-%m-%d")
            day_str = d.strftime("%a")
            pts_map, holiday = self._get_daily_points(resort, d)
            # Holiday block (full-period pricing once)
            if holiday and holiday.name not in processed_holidays:
                processed_holidays.add(holiday.name)
                raw = pts_map.get(room, 0)
                eff = raw
                holiday_days = (holiday.end_date - holiday.start_date).days + 1
                is_disc_holiday = False
                days_out = (holiday.start_date - today).days
                if is_owner:
                    disc_mul = owner_config.get("disc_mul", 1.0)
                    disc_pct = (1 - disc_mul) * 100
                    thresh = 30 if disc_pct == 25 else 60 if disc_pct == 30 else 0
                    if disc_pct > 0 and days_out <= thresh:
                        eff = math.floor(raw * disc_mul)
                        is_disc_holiday = True
                else:
                    renter_disc_mul = 1.0
                    if discount_policy == DiscountPolicy.PRESIDENTIAL:
                        renter_disc_mul = 0.7
                    elif discount_policy == DiscountPolicy.EXECUTIVE:
                        renter_disc_mul = 0.75
                    if (
                        discount_policy == DiscountPolicy.PRESIDENTIAL
                        and days_out <= 60
                    ) or (
                        discount_policy == DiscountPolicy.EXECUTIVE and days_out <= 30
                    ):
                        eff = math.floor(raw * renter_disc_mul)
                        is_disc_holiday = True
                if is_disc_holiday:
                    disc_applied = True
                    for j in range(holiday_days):
                        disc_date = holiday.start_date + timedelta(days=j)
                        disc_days.append(disc_date.strftime("%Y-%m-%d"))
                # Cost computation
                holiday_cost = 0.0
                m = c = dp = 0.0
                if is_owner and owner_config:
                    if owner_config.get("inc_m", False):
                        m = math.ceil(eff * rate)
                    if owner_config.get("inc_c", False):
                        c = math.ceil(eff * owner_config.get("cap_rate", 0.0))
                    if owner_config.get("inc_d", False):
                        dp = math.ceil(eff * owner_config.get("dep_rate", 0.0))
                    holiday_cost = m + c + dp
                else:
                    holiday_cost = math.ceil(eff * rate)
                row: Dict[str, Any] = {
                    "Date": f"{holiday.name} ({holiday.start_date.strftime('%b %d, %Y')} - "
                    f"{holiday.end_date.strftime('%b %d, %Y')})",
                    "Day": "",
                    "Points": eff,
                }
                if is_owner:
                    if owner_config and owner_config.get("inc_m", False):
                        row["Maintenance"] = m
                    if owner_config and owner_config.get("inc_c", False):
                        row["Capital Cost"] = c
                    if owner_config and owner_config.get("inc_d", False):
                        row["Depreciation"] = dp
                    row["Total Cost"] = holiday_cost
                else:
                    row[room] = holiday_cost
                rows.append(row)
                tot_eff_pts += eff
                tot_financial += holiday_cost
                tot_m += m
                tot_c += c
                tot_d += dp
                i += holiday_days
            # Regular day
            elif not holiday:
                raw = pts_map.get(room, 0)
                eff = raw
                is_disc_day = False
                days_out = (d - today).days
                if is_owner:
                    disc_mul = owner_config.get("disc_mul", 1.0)
                    disc_pct = (1 - disc_mul) * 100
                    thresh = 30 if disc_pct == 25 else 60 if disc_pct == 30 else 0
                    if disc_pct > 0 and days_out <= thresh:
                        eff = math.floor(raw * disc_mul)
                        is_disc_day = True
                else:
                    renter_disc_mul = 1.0
                    if discount_policy == DiscountPolicy.PRESIDENTIAL:
                        renter_disc_mul = 0.7
                    elif discount_policy == DiscountPolicy.EXECUTIVE:
                        renter_disc_mul = 0.75
                    if (
                        discount_policy == DiscountPolicy.PRESIDENTIAL
                        and days_out <= 60
                    ) or (
                        discount_policy == DiscountPolicy.EXECUTIVE and days_out <= 30
                    ):
                        eff = math.floor(raw * renter_disc_mul)
                        is_disc_day = True
                if is_disc_day:
                    disc_applied = True
                    disc_days.append(d_str)
                day_cost = 0.0
                m = c = dp = 0.0
                if is_owner and owner_config:
                    if owner_config.get("inc_m", False):
                        m = math.ceil(eff * rate)
                    if owner_config.get("inc_c", False):
                        c = math.ceil(eff * owner_config.get("cap_rate", 0.0))
                    if owner_config.get("inc_d", False):
                        dp = math.ceil(eff * owner_config.get("dep_rate", 0.0))
                    day_cost = m + c + dp
                else:
                    day_cost = math.ceil(eff * rate)
                row = {
                    "Date": d_str,
                    "Day": day_str,
                    "Points": eff,
                }
                if is_owner:
                    if owner_config and owner_config.get("inc_m", False):
                        row["Maintenance"] = m
                    if owner_config and owner_config.get("inc_c", False):
                        row["Capital Cost"] = c
                    if owner_config and owner_config.get("inc_d", False):
                        row["Depreciation"] = dp
                    row["Total Cost"] = day_cost
                else:
                    row[room] = day_cost
                rows.append(row)
                tot_eff_pts += eff
                tot_financial += day_cost
                tot_m += m
                tot_c += c
                tot_d += dp
                i += 1
            else:
                # Should not be hit, but keep safety
                i += 1
        df = pd.DataFrame(rows)
        # Format currency columns
        if is_owner and not df.empty:
            for col in ["Maintenance", "Capital Cost", "Depreciation", "Total Cost"]:
                if col in df.columns:
                    df[col] = df[col].apply(
                        lambda x: f"${x:,.0f}" if isinstance(x, (int, float)) else x
                    )
        else:
            for col in df.columns:
                if col not in ["Date", "Day", "Points"]:
                    df[col] = df[col].apply(
                        lambda x: f"${x:,.0f}" if isinstance(x, (int, float)) else x
                    )
        return CalculationResult(
            breakdown_df=df,
            total_points=tot_eff_pts,
            financial_total=tot_financial,
            discount_applied=disc_applied,
            discounted_days=list(set(disc_days)),
            m_cost=tot_m,
            c_cost=tot_c,
            d_cost=tot_d,
        )

    def compare_stays(
        self,
        resort_name: str,
        rooms: List[str],
        checkin: date,
        nights: int,
        user_mode: UserMode,
        rate: float,
        policy: DiscountPolicy,
        owner_config: Optional[dict],
    ) -> ComparisonResult:
        daily_data: List[Dict[str, Any]] = []
        holiday_data: Dict[str, Dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        is_owner = user_mode == UserMode.OWNER
        disc_mul = owner_config["disc_mul"] if owner_config else 1.0
        renter_mul = 1.0
        if not is_owner:
            if policy == DiscountPolicy.PRESIDENTIAL:
                renter_mul = 0.7
            elif policy == DiscountPolicy.EXECUTIVE:
                renter_mul = 0.75
        val_key = "TotalCostValue" if is_owner else "RentValue"
        resort = self.repo.get_resort(resort_name)
        if not resort:
            return ComparisonResult(
                pivot_df=pd.DataFrame(),
                daily_chart_df=pd.DataFrame(),
                holiday_chart_df=pd.DataFrame(),
            )
        processed_holidays: Dict[str, set[str]] = {room: set() for room in rooms}
        today
