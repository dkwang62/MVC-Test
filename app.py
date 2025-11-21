import streamlit as st
import math
import json
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Union
from enum import Enum

# ==============================================================================
# LAYER 1: DOMAIN MODELS
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
    start_date: datetime.date
    end_date: datetime.date
    room_points: Dict[str, int]

@dataclass
class SeasonPeriod:
    start: datetime.date
    end: datetime.date

@dataclass
class DayCategory:
    days: List[str]
    room_points: Dict[str, int]

@dataclass
class Season:
    name: str
    periods: List[SeasonPeriod]
    day_categories: List[DayCategory]

@dataclass
class ResortData:
    id: str
    name: str
    years: Dict[str, 'YearData']

@dataclass
class YearData:
    holidays: List[Holiday]
    seasons: List[Season]

@dataclass
class SingleCalculationResult:
    breakdown_df: pd.DataFrame
    total_points: int
    financial_total: float
    discount_applied: bool
    discounted_days: List[str]
    # Owner details
    maintenance_cost: float = 0.0
    capital_cost: float = 0.0
    depreciation_cost: float = 0.0

@dataclass
class ComparisonResult:
    pivot_df: pd.DataFrame
    daily_chart_df: pd.DataFrame
    holiday_chart_df: pd.DataFrame

# ==============================================================================
# LAYER 2: REPOSITORY (Data Access)
# ==============================================================================

class MVCRepository:
    def __init__(self, raw_data: dict):
        self._raw = raw_data
        self._resort_cache = {}
        self._global_holidays = self._parse_global_holidays()

    def get_resort_list(self) -> List[str]:
        return [r["display_name"] for r in self._raw.get("resorts", [])]

    def get_config_value(self, path: List[str], default=None):
        data = self._raw.get("configuration", {})
        for key in path:
            data = data.get(key, {})
        return data if data else default

    def _parse_global_holidays(self):
        parsed = {}
        for year, hols in self._raw.get("global_holidays", {}).items():
            parsed[year] = {}
            for name, data in hols.items():
                parsed[year][name] = (
                    datetime.strptime(data["start_date"], "%Y-%m-%d").date(),
                    datetime.strptime(data["end_date"], "%Y-%m-%d").date()
                )
        return parsed

    def get_resort(self, resort_name: str) -> Optional[ResortData]:
        if resort_name in self._resort_cache:
            return self._resort_cache[resort_name]

        raw_resort = next((r for r in self._raw["resorts"] if r["display_name"] == resort_name), None)
        if not raw_resort: return None

        years_data = {}
        for year_str, y_content in raw_resort.get("years", {}).items():
            # Parse Holidays
            holidays = []
            for h in y_content.get("holidays", []):
                ref = h.get("global_reference")
                if ref and ref in self._global_holidays.get(year_str, {}):
                    g_dates = self._global_holidays[year_str][ref]
                    holidays.append(Holiday(
                        name=h.get("name", ref),
                        start_date=g_dates[0],
                        end_date=g_dates[1],
                        room_points=h.get("room_points", {})
                    ))

            # Parse Seasons
            seasons = []
            for s in y_content.get("seasons", []):
                periods = [
                    SeasonPeriod(
                        datetime.strptime(p["start"], "%Y-%m-%d").date(),
                        datetime.strptime(p["end"], "%Y-%m-%d").date()
                    ) for p in s.get("periods", [])
                ]
                day_cats = [
                    DayCategory(days=dc["day_pattern"], room_points=dc["room_points"])
                    for dc in s.get("day_categories", {}).values()
                ]
                seasons.append(Season(s["name"], periods, day_cats))
            
            years_data[year_str] = YearData(holidays, seasons)

        obj = ResortData(raw_resort["id"], raw_resort["display_name"], years_data)
        self._resort_cache[resort_name] = obj
        return obj

# ==============================================================================
# LAYER 3: BUSINESS LOGIC ENGINE
# ==============================================================================

class MVCCalculator:
    def __init__(self, repo: MVCRepository):
        self.repo = repo

    def _get_points_map(self, resort: ResortData, date: datetime.date) -> Tuple[Dict[str, int], Optional[Holiday]]:
        year_str = str(date.year)
        if year_str not in resort.years: return {}, None
        
        y_data = resort.years[year_str]

        # 1. Check Holidays
        for h in y_data.holidays:
            if h.start_date <= date <= h.end_date:
                return h.room_points, h
        
        # 2. Check Seasons
        dow_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
        dow = dow_map[date.weekday()]
        
        for s in y_data.seasons:
            for p in s.periods:
                if p.start <= date <= p.end:
                    for cat in s.day_categories:
                        if dow in cat.days:
                            return cat.room_points, None
        return {}, None

    def calculate_single_stay(self, resort_name: str, room: str, checkin: datetime.date, nights: int, 
                            rate: float, discount_policy: DiscountPolicy = DiscountPolicy.NONE,
                            owner_params: dict = None) -> SingleCalculationResult:
        
        resort = self.repo.get_resort(resort_name)
        if not resort: return self._empty_result()

        rows = []
        totals = {"pts": 0, "cost": 0, "m": 0, "c": 0, "d": 0}
        is_owner = owner_params is not None
        disc_applied = False
        disc_days = []

        # Holiday Grouping State
        curr_h, h_start, h_end, h_pts, h_cost, h_m, h_c, h_d = None, None, None, 0, 0, 0, 0, 0

        for i in range(nights):
            date = checkin + timedelta(days=i)
            pts_map, holiday = self._get_points_map(resort, date)
            raw_pts = pts_map.get(room, 0)
            
            # Apply Discounts
            eff_pts = raw_pts
            if is_owner:
                eff_pts = math.floor(raw_pts * owner_params['disc_mul'])
                if owner_params['disc_mul'] < 1.0: disc_applied = True
            else:
                # Renter Logic
                days_until = (date - datetime.now().date()).days
                if discount_policy == DiscountPolicy.PRESIDENTIAL and days_until <= 60:
                    eff_pts = math.floor(raw_pts * 0.7); disc_applied = True; disc_days.append(str(date))
                elif discount_policy == DiscountPolicy.EXECUTIVE and days_until <= 30:
                    eff_pts = math.floor(raw_pts * 0.75); disc_applied = True; disc_days.append(str(date))

            # Calculate Financials
            m_cost = c_cost = d_cost = day_total = 0
            
            if is_owner:
                if owner_params['inc_m']: m_cost = math.ceil(eff_pts * rate)
                if owner_params['inc_c']: c_cost = math.ceil(eff_pts * owner_params['cap_rate'])
                if owner_params['inc_d']: d_cost = math.ceil(eff_pts * owner_params['dep_rate'])
                day_total = m_cost + c_cost + d_cost
            else:
                # Renter: Rent pays for RAW points usually, unless defined otherwise
                day_total = math.ceil(raw_pts * rate) 

            # Holiday Handling
            if holiday:
                if curr_h != holiday.name:
                    # Flush previous if exists
                    if curr_h:
                        self._append_row(rows, f"{curr_h} ({h_start:%b %d}-{h_end:%b %d})", "", h_pts, h_cost, h_m, h_c, h_d, is_owner)
                    curr_h, h_start, h_end = holiday.name, holiday.start_date, holiday.end_date
                    h_pts, h_cost, h_m, h_c, h_d = 0, 0, 0, 0, 0
                
                h_pts += eff_pts; h_cost += day_total; h_m += m_cost; h_c += c_cost; h_d += d_cost
            else:
                # Flush holiday if needed
                if curr_h:
                    self._append_row(rows, f"{curr_h} ({h_start:%b %d}-{h_end:%b %d})", "", h_pts, h_cost, h_m, h_c, h_d, is_owner)
                    curr_h = None
                
                self._append_row(rows, date.strftime("%d %b %Y"), date.strftime("%a"), eff_pts, day_total, m_cost, c_cost, d_cost, is_owner)

            totals["pts"] += eff_pts; totals["cost"] += day_total
            totals["m"] += m_cost; totals["c"] += c_cost; totals["d"] += d_cost

        if curr_h:
            self._append_row(rows, f"{curr_h} ({h_start:%b %d}-{h_end:%b %d})", "", h_pts, h_cost, h_m, h_c, h_d, is_owner)

        return SingleCalculationResult(
            pd.DataFrame(rows), totals["pts"], totals["cost"], disc_applied, list(set(disc_days)),
            totals["m"], totals["c"], totals["d"]
        )

    def _append_row(self, rows, date_str, day_str, pts, cost, m, c, d, is_owner):
        row = {"Date": date_str, "Day": day_str, "Points": pts}
        if is_owner:
            row.update({"Maintenance": f"${m:,.2f}", "Capital Cost": f"${c:,.2f}", "Depreciation": f"${d:,.2f}", "Total Cost": f"${cost:,.2f}"})
        else:
            row["Rent"] = f"${cost:,.2f}"
        rows.append(row)

    def compare_stays(self, resort_name: str, rooms: List[str], checkin: datetime.date, nights: int,
                     rate: float, discount_policy: DiscountPolicy, owner_params: dict = None) -> ComparisonResult:
        
        resort = self.repo.get_resort(resort_name)
        if not resort: return ComparisonResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

        daily_data = []
        holiday_data = []
        summary_rows = []
        
        # Pre-calculate Holiday Totals for Charting
        for room in rooms:
            res = self.calculate_single_stay(resort_name, room, checkin, nights, rate, discount_policy, owner_params)
            val_label = "Total Cost" if owner_params else "Total Rent"
            col_label = "TotalCostValue" if owner_params else "RentValue"
            
            # Summary Row for Pivot
            summary_rows.append({
                "Room Type": room, 
                "Total Points": res.total_points, 
                val_label: f"${res.financial_total:,.2f}"
            })

            # Re-iterate days for Charting Data (Daily)
            # Note: calculate_single_stay groups holidays, so we need a simpler daily loop for the bar chart
            for i in range(nights):
                date = checkin + timedelta(days=i)
                pts_map, h = self._get_points_map(resort, date)
                raw = pts_map.get(room, 0)
                
                # Calc math again for chart granularity (simplified reuse)
                eff = raw
                if owner_params: eff = math.floor(raw * owner_params['disc_mul'])
                elif discount_policy == DiscountPolicy.PRESIDENTIAL: eff = math.floor(raw * 0.7)
                elif discount_policy == DiscountPolicy.EXECUTIVE: eff = math.floor(raw * 0.75)
                
                if owner_params:
                    cost = (math.ceil(eff * rate) if owner_params['inc_m'] else 0) + \
                           (math.ceil(eff * owner_params['cap_rate']) if owner_params['inc_c'] else 0) + \
                           (math.ceil(eff * owner_params['dep_rate']) if owner_params['inc_d'] else 0)
                else:
                    cost = math.ceil(raw * rate)

                h_name = h.name if h else "No"
                
                daily_data.append({
                    "Day": date.strftime("%a"), 
                    "Date": date,
                    "Room Type": room, 
                    col_label: cost,
                    "Holiday": h_name
                })
                
                if h:
                    holiday_data.append({
                        "Holiday": h.name,
                        "Room Type": room,
                        col_label: cost # We sum this later
                    })

        # Construct DataFrames
        df_daily = pd.DataFrame(daily_data)
        df_holiday = pd.DataFrame(holiday_data)
        if not df_holiday.empty:
            df_holiday = df_holiday.groupby(["Holiday", "Room Type"])[col_label].sum().reset_index()

        # Construct Pivot Table manually to match old format
        # Date | Room 1 Cost | Room 2 Cost ...
        # We will use the Grouped Breakdown logic for the Pivot to be readable
        pivot_rows = []
        
        # Get date ranges (using first room as master timeline)
        master_res = self.calculate_single_stay(resort_name, rooms[0], checkin, nights, rate, discount_policy, owner_params)
        dates = master_res.breakdown_df["Date"].tolist()
        
        for date_str in dates:
            row = {"Date": date_str}
            for room in rooms:
                # Re-calc for just this specific date row logic is hard without re-running.
                # Optimized approach: Run calc for all rooms, merge on Date.
                r_res = self.calculate_single_stay(resort_name, room, checkin, nights, rate, discount_policy, owner_params)
                # Find value for this date
                val = r_res.breakdown_df.loc[r_res.breakdown_df["Date"] == date_str]
                if not val.empty:
                    target_col = "Total Cost" if owner_params else "Rent"
                    row[room] = val.iloc[0][target_col]
            pivot_rows.append(row)
            
        # Add Total Row
        tot_row = {"Date": "<b>TOTAL</b>"}
        for room in rooms:
            r_res = self.calculate_single_stay(resort_name, room, checkin, nights, rate, discount_policy, owner_params)
            tot_row[room] = f"<b>${r_res.financial_total:,.2f}</b>"
        pivot_rows.append(tot_row)

        return ComparisonResult(pd.DataFrame(pivot_rows), df_daily, df_holiday)

    def adjust_dates(self, resort_name: str, checkin: datetime.date, nights: int) -> Tuple[datetime.date, int, bool]:
        resort = self.repo.get_resort(resort_name)
        if not resort: return checkin, nights, False
        
        year = str(checkin.year)
        if year not in resort.years: return checkin, nights, False
        
        end = checkin + timedelta(days=nights-1)
        for h in resort.years[year].holidays:
            if h.start_date <= end and h.end_date >= checkin:
                if nights < 7: # Only adjust if less than a week (Old app logic)
                    return h.start_date, 7, True
        return checkin, nights, False

    def _empty_result(self):
        return SingleCalculationResult(pd.DataFrame(), 0, 0.0, False, [])

# ==============================================================================
# LAYER 4: UI (Streamlit)
# ==============================================================================

def main():
    # 1. Setup
    if st.session_state.data is None:
        try:
            with open("data_v2.json", "r") as f: st.session_state.data = json.load(f)
        except: pass

    with st.sidebar:
        uploaded = st.file_uploader("Upload Data (JSON)", type="json")
        if uploaded:
            st.session_state.data = json.load(uploaded)
            st.rerun()
    
    if not st.session_state.data:
        st.warning("Please upload data_v2.json"); st.stop()

    repo = MVCRepository(st.session_state.data)
    calc = MVCCalculator(repo)
    resort_list = repo.get_resort_list()

    st.title("MVC Calculator")

    # 2. Global Sidebar Params
    with st.sidebar:
        st.header("Settings")
        mode = st.selectbox("Mode", [m.value for m in UserMode])
        year = datetime.now().year
        def_rate = repo.get_config_value(["maintenance_rates", str(year)], 0.86)
        
        owner_params = None
        discount_policy = DiscountPolicy.NONE
        rate = def_rate

        if mode == UserMode.OWNER.value:
            cap = st.number_input("Purchase Price/Pt", value=16.0)
            disc = st.selectbox("Discount", [0, 25, 30], format_func=lambda x: f"{x}%")
            inc_m = st.checkbox("Maint.", True)
            rate = st.number_input("Rate", value=def_rate) if inc_m else 0
            inc_c = st.checkbox("Capital", True)
            coc = st.number_input("COC %", 7.0)/100 if inc_c else 0
            inc_d = st.checkbox("Deprec.", True)
            life = st.number_input("Life", 15) if inc_d else 1
            salvage = st.number_input("Salvage", 3.0) if inc_d else 0
            
            owner_params = {
                'disc_mul': 1 - (disc/100), 'inc_m': inc_m, 'inc_c': inc_c, 'inc_d': inc_d,
                'cap_rate': cap * coc / 365, 'dep_rate': (cap - salvage) / life / 365
            }
        else:
            adv = st.checkbox("Advanced Options")
            if adv:
                opt = st.radio("Rate", ["Standard", "Custom", "< 60 Days", "< 30 Days"])
                if opt == "Custom": rate = st.number_input("Rate", value=def_rate)
                elif opt == "< 60 Days": discount_policy = DiscountPolicy.PRESIDENTIAL
                elif opt == "< 30 Days": discount_policy = DiscountPolicy.EXECUTIVE

    # 3. Main Inputs
    st.subheader("Select Resort")
    r_name = st.selectbox("Resort", resort_list)
    
    c1, c2 = st.columns(2)
    checkin = c1.date_input("Check-in", datetime(2025, 6, 12))
    nights = c2.number_input("Nights", 1, 60, 7)

    # Logic: Adjust Date
    adj_in, adj_n, adj = calc.adjust_dates(r_name, checkin, nights)
    if adj: st.info(f"Adjusted to full holiday week: {adj_in} ({adj_n} nights)")

    # Logic: Populate Rooms
    # Get sample points to find valid rooms for this year
    sample_res = repo.get_resort(r_name)
    # Flatten all known rooms for this resort
    rooms = set()
    if sample_res and str(adj_in.year) in sample_res.years:
        yd = sample_res.years[str(adj_in.year)]
        for h in yd.holidays: rooms.update(h.room_points.keys())
        for s in yd.seasons:
            for d in s.day_categories: rooms.update(d.room_points.keys())
    
    room_opts = sorted(list(rooms))
    if not room_opts: st.error("No room data found for this year."); st.stop()
    
    sel_room = st.selectbox("Room Type", room_opts)
    comp_rooms = st.multiselect("Compare With", [r for r in room_opts if r != sel_room])

    # 4. Execution
    if st.button("Calculate"):
        # Single Breakdown
        res = calc.calculate_single_stay(r_name, sel_room, adj_in, adj_n, rate, discount_policy, owner_params)
        
        st.subheader(f"{r_name} Breakdown")
        st.dataframe(res.breakdown_df, use_container_width=True)
        
        m1, m2 = st.columns(2)
        m1.metric("Total Points", f"{res.total_points:,}")
        m2.metric("Total " + ("Cost" if mode=="Owner" else "Rent"), f"${res.financial_total:,.2f}")
        
        st.download_button("Download Breakdown CSV", res.breakdown_df.to_csv(index=False), "breakdown.csv")

        # Comparison
        if comp_rooms:
            all_rooms = [sel_room] + comp_rooms
            comp_res = calc.compare_stays(r_name, all_rooms, adj_in, adj_n, rate, discount_policy, owner_params)
            
            st.subheader("Comparison Table")
            st.dataframe(comp_res.pivot_df, use_container_width=True)
            st.download_button("Download Comparison CSV", comp_res.pivot_df.to_csv(index=False), "comparison.csv")
            
            # Charts
            if not comp_res.daily_chart_df.empty:
                # Daily Chart
                y_val = "TotalCostValue" if owner_params else "RentValue"
                title = "Daily " + ("Cost" if mode=="Owner" else "Rent")
                day_order = ["Fri", "Sat", "Sun", "Mon", "Tue", "Wed", "Thu"]
                fig = px.bar(comp_res.daily_chart_df, x="Day", y=y_val, color="Room Type", barmode="group", 
                             category_orders={"Day": day_order}, title=title)
                st.plotly_chart(fig, use_container_width=True)

            if not comp_res.holiday_chart_df.empty:
                # Holiday Chart
                h_fig = px.bar(comp_res.holiday_chart_df, x="Holiday", y=y_val, color="Room Type", barmode="group",
                               title="Holiday Week Comparison")
                st.plotly_chart(h_fig, use_container_width=True)

        # Gantt Chart
        st.subheader("Season Calendar")
        # Quick Gantt generation from Repo
        res_data = repo.get_resort(r_name)
        if res_data:
            g_data = []
            yd = res_data.years.get(str(adj_in.year))
            if yd:
                for s in yd.seasons:
                    for p in s.periods: g_data.append(dict(Task=s.name, Start=p.start, Finish=p.end, Type="Season"))
                for h in yd.holidays:
                    g_data.append(dict(Task=h.name, Start=h.start_date, Finish=h.end_date, Type="Holiday"))
            
            if g_data:
                gdf = pd.DataFrame(g_data)
                fig = px.timeline(gdf, x_start="Start", x_end="Finish", y="Task", color="Type")
                st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
