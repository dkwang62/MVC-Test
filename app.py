# mvc_rent_calculator.py
# Simple Mobile-Friendly MVC Points & Rent Calculator
# Fully self-contained - loads data_v2.json automatically!

import streamlit as st
import json
from datetime import date, timedelta
import math
import pandas as pd

st.set_page_config(page_title="MVC Rent Calc", layout="wide")

# === AUTOMATIC DATA LOAD ===
@st.cache_data
def load_data():
    try:
        with open('data_v2.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("data_v2.json not found! Please place it in the same directory.")
        st.stop()

data = load_data()
repo = MVCRepository(data)
calc = MVCCalculator(repo)
resorts = repo.get_resort_list()

# === SIMPLIFIED CLASSES (from original) ===
class UserMode(Enum):
    RENTER = "Renter"

class DiscountPolicy(Enum):
    NONE = "None"
    EXECUTIVE = "Executive" 
    PRESIDENTIAL = "Presidential"

@dataclass
class CalculationResult:
    breakdown_df: pd.DataFrame
    total_points: int
    financial_total: float
    discount_applied: bool
    m_cost: float = 0.0
    c_cost: float = 0.0
    d_cost: float = 0.0

@dataclass
class HolidayObj:
    name: str; start: date; end: date

class MVCRepository:
    def __init__(self, raw_data: dict):
        self._raw = raw_data
        self._gh = self._parse_global_holidays()

    def get_resort_list(self) -> list:
        return self._raw.get("resorts", [])

    def _parse_global_holidays(self):
        parsed = {}
        for y, hols in self._raw.get("global_holidays", {}).items():
            parsed[y] = {}
            for n, d in hols.items():
                parsed[y][n] = (
                    datetime.strptime(d["start_date"], "%Y-%m-%d").date(),
                    datetime.strptime(d["end_date"], "%Y-%m-%d").date()
                )
        return parsed

    def get_resort_data(self, name: str):
        return next((r for r in self._raw.get("resorts", []) if r["display_name"] == name), None)

class MVCCalculator:
    def __init__(self, repo):
        self.repo = repo

    def get_points(self, resort_data, day):
        y = str(day.year)
        if y not in resort_data.get("years", {}): return {}, None
        yd = resort_data["years"][y]
        
        # 1. Holiday Check
        for h in yd.get("holidays", []):
            ref = h.get("global_reference")
            start, end = None, None
            if ref and ref in self.repo._gh.get(y, {}):
                start, end = self.repo._gh[y][ref]
            
            if start and end and start <= day <= end:
                return h.get("room_points", {}), HolidayObj(h.get("name"), start, end)
        
        # 2. Season Check
        dow_map = {0:"Mon",1:"Tue",2:"Wed",3:"Thu",4:"Fri",5:"Sat",6:"Sun"}
        dow = dow_map[day.weekday()]
        
        for s in yd.get("seasons", []):
            for p in s.get("periods", []):
                try:
                    ps = datetime.strptime(p["start"], "%Y-%m-%d").date()
                    pe = datetime.strptime(p["end"], "%Y-%m-%d").date()
                    if ps <= day <= pe:
                        for cat in s.get("day_categories", {}).values():
                            if dow in cat.get("day_pattern", []):
                                return cat.get("room_points", {}), None
                except: continue
        return {}, None

    def calculate(self, resort_name, room, checkin, nights, mode, rate, discount_multiplier, owner_cfg):
        r_data = self.repo.get_resort_data(resort_name)
        if not r_data: 
            return None
        
        if mode == UserMode.RENTER:
            rate = round(float(rate), 2)

        rows = []
        total_pts = 0
        total_money = 0.0
        tot_m = tot_c = tot_d = 0.0
        disc_hit = False
        processed_holidays = set()
        
        mul = discount_multiplier

        i = 0
        while i < nights:
            d = checkin + timedelta(days=i)
            pts_map, holiday_obj = self.get_points(r_data, d)
            
            if holiday_obj:
                if holiday_obj.name not in processed_holidays:
                    processed_holidays.add(holiday_obj.name)
                    
                    raw = int(pts_map.get(room, 0))
                    eff = math.floor(raw * mul) if mul < 1.0 else raw
                    if eff < raw: 
                        disc_hit = True
                    
                    m, c, dp, cost = self._calc_costs(eff, mode, rate, owner_cfg)
                    
                    rows.append({
                        "Date": f"{holiday_obj.name} ({holiday_obj.start.strftime('%b %d')} - {holiday_obj.end.strftime('%b %d')})",
                        "Pts": eff,
                        "Cost": f"${cost:,.0f}"
                    })
                    
                    total_pts += eff
                    total_money += cost
                    tot_m += m; tot_c += c; tot_d += dp
                    
                    duration = (holiday_obj.end - holiday_obj.start).days + 1
                    i += duration
                else:
                    i += 1
            else:
                raw = int(pts_map.get(room, 0))
                eff = math.floor(raw * mul) if mul < 1.0 else raw
                if eff < raw: 
                    disc_hit = True
                
                m, c, dp, cost = self._calc_costs(eff, mode, rate, owner_cfg)
                
                rows.append({
                    "Date": d.strftime("%a %d %b"), 
                    "Pts": eff, 
                    "Cost": f"${cost:,.0f}"
                })
                
                total_pts += eff
                total_money += cost
                tot_m += m; tot_c += c; tot_d += dp
                i += 1

        if mode == UserMode.RENTER:
            total_money = total_pts * rate
            tot_m = tot_c = tot_d = 0.0
        elif mode == UserMode.OWNER and owner_cfg:
            maint_total = total_pts * rate
            cap_total = total_pts * owner_cfg.get("cap_rate", 0.0) if owner_cfg.get("inc_c") else 0.0
            dep_total = total_pts * owner_cfg.get("dep_rate", 0.0) if owner_cfg.get("inc_d") else 0.0

            tot_m = maint_total
            tot_c = cap_total
            tot_d = dep_total
            total_money = maint_total + cap_total + dep_total

        return CalculationResult(pd.DataFrame(rows), total_pts, total_money, disc_hit, tot_m, tot_c, tot_d)

    def _calc_costs(self, eff, mode, rate, owner_cfg):
        cost = 0.0
        m = c = dp = 0.0
        if mode == UserMode.OWNER and owner_cfg:
            m = math.ceil(eff * rate)
            if owner_cfg.get("inc_c"): 
                c = math.ceil(eff * owner_cfg.get("cap_rate", 0))
            if owner_cfg.get("inc_d"): 
                dp = math.ceil(eff * owner_cfg.get("dep_rate", 0))
            cost = m + c + dp
        else:
            cost = math.ceil(eff * rate)
        return m, c, dp, cost

# === MOBILE-FRIENDLY UI ===
st.title("🧮 MVC Rent Calculator")
st.caption("Mobile-friendly | Auto-loads data_v2.json | Renter Mode Only")

# Compact inputs
col1, col2 = st.columns(2)
resort_obj = next((r for r in resorts if r["id"] == st.session_state.get("current_resort_id", resorts[0]["id"])), resorts[0])
with col1:
    resort_name = st.selectbox("Resort", [r["display_name"] for r in resorts], key="resort_sel")
with col2:
    year = st.selectbox("Year", sorted(set(r.get("years", {}).keys() for r in resorts)), index=0)

# Get rooms for selected resort/year
r_data = repo.get_resort_data(resort_name)
if r_data and str(year) in r_data.get("years", {}):
    yd = r_data["years"][str(year)]
    if yd.get("seasons"):
        s = yd["seasons"][0]
        cat = next(iter(s.get("day_categories", {}).values()), None)
        rooms = sorted(list(cat.get("room_points", {}).keys())) if cat else []
    else:
        rooms = []
else:
    rooms = []

if not rooms:
    st.error(f"No data for {resort_name} in {year}")
    st.stop()

room = st.selectbox("Room", rooms)

col3, col4 = st.columns(2)
checkin = col3.date_input("Check-in", value=date.today() + timedelta(days=7))
nights = col4.number_input("Nights", 1, 60, 7)

rate = st.number_input("Rent Rate ($/pt)", value=0.50, step=0.05, format="%.2f")

tier_opts = ["No Discount", "Executive", "Presidential"]
tier = st.selectbox("Discount", tier_opts, index=0)
discount_mul = 1.0 if tier == "No Discount" else 0.75 if tier == "Executive" else 0.70

mode = UserMode.RENTER
owner_cfg = None

if st.button("Calculate", type="primary", use_container_width=True):
    res = calc.calculate(resort_name, room, checkin, nights, mode, rate, discount_mul, owner_cfg)
    
    if res:
        col5, col6 = st.columns(2)
        col5.metric("Points", f"{res.total_points:,}")
        col6.metric("Total Cost", f"${res.financial_total:,.0f}")
        
        if res.discount_applied: 
            st.success("✅ Discount Applied!")
        
        st.dataframe(res.breakdown_df, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("💡 Place data_v2.json in the same folder | Run: streamlit run mvc_rent_calculator.py")
