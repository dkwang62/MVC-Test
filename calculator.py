import math
import pandas as pd
import json
import streamlit as st
import matplotlib.pyplot as plt 
from datetime import datetime, timedelta, date
from dataclasses import dataclass
from enum import Enum

from common.ui import render_page_header, render_resort_selector, render_resort_card
from common.charts import render_gantt, get_season_bucket
from common.data import ensure_data_in_session

class UserMode(Enum):
    RENTER = "Renter"
    OWNER = "Owner"

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

# --- HELPER: Render Dataframe as Static Image ---
def render_static_table(df):
    """
    Converts a pandas DataFrame into a matplotlib figure to render as a static image.
    """
    if df.empty:
        return None

    # Dynamic height based on number of rows
    num_rows = len(df)
    height = max(2, num_rows * 0.5 + 1) # Base height + row scaling
    
    fig, ax = plt.subplots(figsize=(8, height)) 
    ax.axis('off')
    ax.axis('tight')
    
    # Create the table
    table = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center')
    
    # Styling
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5) # Add some padding to cells
    
    # Header styling
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(weight='bold', color='white')
            cell.set_facecolor('#4b5563') # Dark gray header
            cell.set_edgecolor('white')
        else:
            cell.set_edgecolor('#e5e7eb') # Light gray borders
            
    return fig

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
                        "Date": f"{holiday_obj.name}",
                        "Pts": eff,
                        "Cost": f"${cost:,.0f}"
                    })
                    
                    total_pts += eff
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
                i += 1

        if mode == UserMode.RENTER:
            total_money = math.ceil(total_pts * rate)
            tot_m = tot_c = tot_d = 0.0

        elif mode == UserMode.OWNER and owner_cfg:
            maint_total = math.ceil(total_pts * rate)
            cap_rate = owner_cfg.get("cap_rate", 0.0)
            dep_rate = owner_cfg.get("dep_rate", 0.0)
            
            cap_total = math.ceil(total_pts * cap_rate) if owner_cfg.get("inc_c") else 0.0
            dep_total = math.ceil(total_pts * dep_rate) if owner_cfg.get("inc_d") else 0.0

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

def run():
    ensure_data_in_session()
    if not st.session_state.data:
        st.warning("Please go to Editor and load data_v2.json first.")
        return

    repo = MVCRepository(st.session_state.data)
    calc = MVCCalculator(repo)
    resorts = repo.get_resort_list()

    with st.sidebar:
        with st.expander("📂 Load Profile", expanded=False):
            cfg_file = st.file_uploader("Upload Settings", type="json", key="cfg_up")
            if cfg_file:
                try:
                    st.session_state["cfg_loaded"] = json.load(cfg_file)
                    st.success("Loaded!")
                except: 
                    st.error("Invalid File")

    defaults = st.session_state.get("cfg_loaded", {})
    
    mode_sel = st.radio("Mode", [m.value for m in UserMode], horizontal=True, label_visibility="collapsed")
    mode = UserMode(mode_sel)
    
    render_page_header("Calculator", mode.value, "🧮", "#059669" if mode == UserMode.OWNER else "#2563eb")

    with st.expander("⚙️ Advanced Configuration", expanded=False):
        tier_key = "discount_tier" if mode == UserMode.OWNER else "renter_discount_tier"
        saved_tier = defaults.get(tier_key, "No Discount")
        tier_opts = ["No Discount", "Executive", "Presidential"]
        try: 
            t_idx = next(i for i, v in enumerate(tier_opts) if v in saved_tier)
        except: 
            t_idx = 0
        
        tier = st.selectbox("Tier", tier_opts, index=t_idx)
        active_mul = 0.7 if "Pres" in tier else 0.75 if "Exec" in tier else 1.0

        inc_c = True
        inc_d = True
        cap_price = 18.0
        coc_pct = 5.0
        life = 10
        salvage = 3.0

        if mode == UserMode.OWNER:
            st.caption("Capital & Depreciation Settings")
            ac1, ac2, ac3 = st.columns(3)
            inc_c = ac1.checkbox("Capital", value=defaults.get("include_capital", True))
            inc_d = ac2.checkbox("Deprec.", value=defaults.get("include_depreciation", True))
            
            if inc_c:
                cap_price = st.number_input("Purchase Price", value=defaults.get("purchase_price", 18.0))
                coc_pct = st.number_input("Cost of Capital %", value=defaults.get("capital_cost_pct", 5.0))
            if inc_d:
                life = st.number_input("Life (yrs)", value=defaults.get("useful_life", 10))
                salvage = st.number_input("Salvage", value=defaults.get("salvage_value", 3.0))

    cap_rate = cap_price * (coc_pct/100.0)
    dep_rate = (cap_price - salvage) / life if life > 0 else 0

    if "current_resort_id" not in st.session_state:
        pref = defaults.get("preferred_resort_id")
        if pref and any(r['id'] == pref for r in resorts): 
            st.session_state.current_resort_id = pref
        else: 
            st.session_state.current_resort_id = resorts[0]["id"]
        
    render_resort_selector(resorts, st.session_state.current_resort_id)
    r_obj = next((r for r in resorts if r["id"] == st.session_state.current_resort_id), None)
    if not r_obj: 
        return
    
    render_resort_card(r_obj.get("resort_name", ""), r_obj.get("timezone", ""), r_obj.get("address", ""))

    # --- INPUTS: Standard columns (Will stack on mobile, no forced scroll) ---
    c1, c2, c3 = st.columns([1, 1, 2]) 
    with c1: 
        checkin = st.date_input("Check-in", value=date.today() + timedelta(days=1))
    with c2: 
        nights = st.number_input("Nights", 1, 60, 7)

    rooms = []
    years = r_obj.get("years", {})
    y_str = str(checkin.year)
    if y_str in years and years[y_str].get("seasons"):
        s = years[y_str]["seasons"][0]
        cat = next(iter(s.get("day_categories", {}).values()), None)
        if cat: 
            rooms = sorted(list(cat.get("room_points", {}).keys()))
    
    with c3:
        if not rooms:
            st.error(f"No data for {y_str}")
            room = None
        else:
            room = st.selectbox("Room Type", rooms)

    if not room: return

    st.divider()
    
    # Results Header
    rc1, rc2, rc3 = st.columns([1, 1, 1])
    
    with rc1:
        if mode == UserMode.OWNER:
            rate_to_use = st.number_input("Maint Rate", value=defaults.get("maintenance_rate", 0.55), step=0.01)
            owner_cfg = {
                "inc_c": inc_c, 
                "cap_rate": cap_rate, 
                "inc_d": inc_d, 
                "dep_rate": dep_rate, 
                "disc_mul": active_mul
            }
            save_data = {
                "maintenance_rate": rate_to_use, "purchase_price": cap_price, "capital_cost_pct": coc_pct,
                "include_capital": inc_c, "include_depreciation": inc_d, "discount_tier": tier,
                "preferred_resort_id": st.session_state.get("current_resort_id", "")
            }
        else:
            rate_to_use = st.number_input("Rent Rate", value=defaults.get("renter_rate", 0.50), step=0.05)
            rate_to_use = round(float(rate_to_use), 2)
            owner_cfg = None
            save_data = {
                "renter_rate": rate_to_use, "renter_discount_tier": tier,
                "preferred_resort_id": st.session_state.get("current_resort_id", "")
            }

    res = calc.calculate(r_obj["display_name"], room, checkin, nights, mode, rate_to_use, active_mul, owner_cfg)

    with rc2:
        st.metric("Points", f"{res.total_points:,}")

    with rc3:
        st.metric("Total", f"${res.financial_total:,.0f}")

    if mode == UserMode.OWNER:
        st.caption(f"Details: Maint ${res.m_cost:,.0f} | Cap ${res.c_cost:,.0f} | Dep ${res.d_cost:,.0f}")

    # --- TABLE AS IMAGE ---
    fig = render_static_table(res.breakdown_df)
    if fig:
        st.pyplot(fig, use_container_width=True)

    with st.sidebar:
         st.download_button("💾 Save Profile", json.dumps(save_data, indent=2), "mvc_owner_settings.json", "application/json")

    other_rooms = [r for r in rooms if r != room]
    if other_rooms:
        with st.expander("📊 Compare Rooms", expanded=True):
            comp_rooms = st.multiselect("Select rooms:", other_rooms)
            if comp_rooms:
                comp_data = []
                comp_data.append({
                    "Room": room, 
                    "Pts": f"{res.total_points:,}",
                    "Cost": f"${res.financial_total:,.0f}"
                })
                
                for cr in comp_rooms:
                    c_res = calc.calculate(r_obj["display_name"], cr, checkin, nights, mode, rate_to_use, active_mul, owner_cfg)
                    if c_res:
                        comp_data.append({
                            "Room": cr, 
                            "Pts": f"{c_res.total_points:,}",
                            "Cost": f"${c_res.financial_total:,.0f}"
                        })
                
                # Compare Table as Image
                comp_df = pd.DataFrame(comp_data)
                fig_comp = render_static_table(comp_df)
                if fig_comp:
                    st.pyplot(fig_comp, use_container_width=True)

    # --- GANTT CHART (PREVIOUS VERSION) ---
    if r_obj and str(checkin.year) in r_obj.get("years", {}):
        with st.expander("📅 Season Calendar", expanded=False):
            yd = r_obj["years"][str(checkin.year)]
            g_rows = []
            for s in yd.get("seasons", []):
                for p in s.get("periods", []):
                    g_rows.append({"Task": s["name"], "Start": p["start"], "Finish": p["end"], "Type": get_season_bucket(s["name"])})
            for h in yd.get("holidays", []):
                ref = h.get("global_reference")
                gh = repo._gh.get(str(checkin.year), {}).get(ref)
                if gh: 
                    g_rows.append({"Task": h.get("name"), "Start": gh[0], "Finish": gh[1], "Type": "Holiday"})
            
            fig = render_gantt(g_rows, f"{checkin.year} Calendar")
            st.pyplot(fig, use_container_width=True)
