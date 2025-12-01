import math
import pandas as pd
import json
import streamlit as st
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

# --- REPOSITORY ---
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

# --- CALCULATOR LOGIC ---
class MVCCalculator:
    def __init__(self, repo):
        self.repo = repo

    def get_points(self, resort_data, day):
        y = str(day.year)
        if y not in resort_data.get("years", {}): return {}, None
        yd = resort_data["years"][y]
        
        # Holiday
        for h in yd.get("holidays", []):
            ref = h.get("global_reference")
            if ref and ref in self.repo._gh.get(y, {}):
                s, e = self.repo._gh[y][ref]
                if s <= day <= e: return h.get("room_points", {}), h.get("name")
        
        # Season
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

    def calculate(self, resort_name, room, checkin, nights, mode, rate, disc_tier, owner_cfg):
        r_data = self.repo.get_resort_data(resort_name)
        if not r_data: return None
        
        rows = []
        total_pts = 0
        total_money = 0.0
        tot_m = tot_c = tot_d = 0.0
        disc_hit = False
        
        mul = 1.0
        if mode == UserMode.RENTER:
            if "Presidential" in str(disc_tier): mul = 0.7
            elif "Executive" in str(disc_tier): mul = 0.75
        elif mode == UserMode.OWNER and owner_cfg:
            mul = owner_cfg.get("disc_mul", 1.0)

        for i in range(nights):
            d = checkin + timedelta(days=i)
            pts_map, h_name = self.get_points(r_data, d)
            raw = int(pts_map.get(room, 0))
            
            eff = math.floor(raw * mul) if mul < 1.0 else raw
            if eff < raw: disc_hit = True
            
            cost = 0.0
            m = c = dp = 0.0
            
            if mode == UserMode.OWNER and owner_cfg:
                m = math.ceil(eff * rate)
                if owner_cfg.get("inc_c"): c = math.ceil(eff * owner_cfg.get("cap_rate", 0))
                if owner_cfg.get("inc_d"): dp = math.ceil(eff * owner_cfg.get("dep_rate", 0))
                cost = m + c + dp
            else:
                cost = math.ceil(eff * rate)
            
            row = {"Date": d.strftime("%a %d"), "Pts": eff, "Cost": f"${cost}"}
            if h_name: row["Note"] = "Holiday"
            rows.append(row)
            
            total_pts += eff
            total_money += cost
            tot_m += m; tot_c += c; tot_d += dp

        return CalculationResult(pd.DataFrame(rows), total_pts, total_money, disc_hit, tot_m, tot_c, tot_d)

# --- MAIN ---
def run():
    ensure_data_in_session()
    if not st.session_state.data:
        st.warning("Please go to Editor and load data_v2.json first.")
        return

    repo = MVCRepository(st.session_state.data)
    calc = MVCCalculator(repo)
    resorts = repo.get_resort_list()

    with st.sidebar:
        # 1. Mode Selection
        mode_sel = st.radio("Mode", [m.value for m in UserMode], horizontal=True, label_visibility="collapsed")
        mode = UserMode(mode_sel)
        
        # 2. Load Profile (Settings Only)
        with st.expander("📂 Load Profile (Settings)", expanded=False):
            cfg_file = st.file_uploader("Upload mvc_owner_settings.json", type="json", key="cfg_up")
            if cfg_file:
                try:
                    cfg = json.load(cfg_file)
                    # Force update session state defaults
                    st.session_state["cfg_loaded"] = cfg
                    st.success("Settings Loaded!")
                except: st.error("Invalid Settings File")

        # Get defaults from loaded file or empty dict
        defaults = st.session_state.get("cfg_loaded", {})

        # 3. Settings Form
        with st.expander("⚙️ Settings", expanded=False):
            if mode == UserMode.OWNER:
                maint = st.number_input("Maint. Rate ($/pt)", value=defaults.get("maintenance_rate", 0.55), step=0.01)
                
                inc_c = st.checkbox("Include Capital", value=defaults.get("include_capital", True))
                cap_price = st.number_input("Purchase Price", value=defaults.get("purchase_price", 18.0)) if inc_c else 0.0
                coc_pct = st.number_input("Cost of Capital %", value=defaults.get("capital_cost_pct", 5.0)) if inc_c else 0.0
                
                inc_d = st.checkbox("Include Deprec.", value=defaults.get("include_depreciation", True))
                life = st.number_input("Useful Life (yrs)", value=defaults.get("useful_life", 10)) if inc_d else 10
                salvage = st.number_input("Salvage Value", value=defaults.get("salvage_value", 3.0)) if inc_d else 0.0
                
                # Derive internal rates
                cap_rate = cap_price * (coc_pct/100.0)
                dep_rate = (cap_price - salvage) / life if life > 0 else 0
                rate = maint
                
                # Discount Logic
                saved_tier = defaults.get("discount_tier", "No Discount")
                tier_opts = ["No Discount", "Executive", "Presidential"]
                # Find index safely
                try: t_idx = next(i for i, v in enumerate(tier_opts) if v in saved_tier)
                except: t_idx = 0
                
                tier = st.selectbox("Tier", tier_opts, index=t_idx)
                disc_mul = 0.7 if "Pres" in tier else 0.75 if "Exec" in tier else 1.0
                
                owner_cfg = {
                    "inc_c": inc_c, "cap_rate": cap_rate,
                    "inc_d": inc_d, "dep_rate": dep_rate, 
                    "disc_mul": disc_mul
                }
                d_policy = DiscountPolicy.NONE
                
                # JSON for Saving
                save_json = {
                    "maintenance_rate": maint, "purchase_price": cap_price, "capital_cost_pct": coc_pct,
                    "useful_life": life, "salvage_value": salvage, "discount_tier": tier,
                    "include_capital": inc_c, "include_depreciation": inc_d
                }

            else: # RENTER
                rate = st.number_input("Rent Rate ($/pt)", value=defaults.get("renter_rate", 0.50), step=0.05)
                
                saved_tier = defaults.get("renter_discount_tier", "No Discount")
                tier_opts = ["No Discount", "Executive", "Presidential"]
                try: t_idx = next(i for i, v in enumerate(tier_opts) if v in saved_tier)
                except: t_idx = 0
                
                tier_s = st.selectbox("Discount Eligibility", tier_opts, index=t_idx)
                d_policy = DiscountPolicy.PRESIDENTIAL if "Pres" in tier_s else DiscountPolicy.EXECUTIVE if "Exec" in tier_s else DiscountPolicy.NONE
                owner_cfg = None
                
                save_json = {"renter_rate": rate, "renter_discount_tier": tier_s}

            # 4. Save Button
            st.download_button("💾 Save Profile", json.dumps(save_json, indent=2), "mvc_owner_settings.json", "application/json")

    # --- UI HEADER ---
    render_page_header("Calculator", mode.value, "🧮", "#059669" if mode == UserMode.OWNER else "#2563eb")
    
    # Resort Selection (Default to preference if available)
    if "current_resort_id" not in st.session_state:
        pref = defaults.get("preferred_resort_id")
        # Validate preference exists in loaded data
        if pref and any(r['id'] == pref for r in resorts):
            st.session_state.current_resort_id = pref
        else:
            st.session_state.current_resort_id = resorts[0]["id"]
        
    render_resort_selector(resorts, st.session_state.current_resort_id)
    
    r_obj = next((r for r in resorts if r["id"] == st.session_state.current_resort_id), None)
    if not r_obj: return
    
    render_resort_card(r_obj.get("resort_name", ""), r_obj.get("timezone", ""), "")

    c1, c2 = st.columns(2)
    with c1: checkin = st.date_input("Check-in", value=date.today() + timedelta(days=1))
    with c2: nights = st.number_input("Nights", 1, 60, 7)

    # Room Selection
    rooms = []
    years = r_obj.get("years", {})
    y_str = str(checkin.year)
    if y_str in years and years[y_str].get("seasons"):
        s = years[y_str]["seasons"][0]
        cat = next(iter(s.get("day_categories", {}).values()), None)
        if cat: rooms = sorted(list(cat.get("room_points", {}).keys()))
    
    if not rooms:
        st.error(f"No pricing data found for {y_str}")
        return

    room = st.selectbox("Room Type", rooms)

    # Calculate
    res = calc.calculate(r_obj["display_name"], room, checkin, nights, mode, rate, d_policy, owner_cfg)
    
    st.divider()
    
    m1, m2 = st.columns(2)
    m1.metric("Points", f"{res.total_points:,}")
    m2.metric("Total Cost", f"${res.financial_total:,.0f}")
    
    if mode == UserMode.OWNER:
        st.caption(f"Maint: ${res.m_cost:,.0f} | Cap: ${res.c_cost:,.0f} | Dep: ${res.d_cost:,.0f}")
    
    if res.discount_applied: st.success("Discount Applied!")

    st.dataframe(res.breakdown_df, use_container_width=True, hide_index=True)

    # Comparison
    other_rooms = [r for r in rooms if r != room]
    if other_rooms:
        with st.expander("📊 Compare Rooms", expanded=True):
            comp_rooms = st.multiselect("Select rooms:", other_rooms)
            if comp_rooms:
                comp_data = []
                comp_data.append({"Room": room, "Total": res.financial_total})
                for cr in comp_rooms:
                    c_res = calc.calculate(r_obj["display_name"], cr, checkin, nights, mode, rate, d_policy, owner_cfg)
                    if c_res: comp_data.append({"Room": cr, "Total": c_res.financial_total})
                
                if comp_data:
                    st.bar_chart(pd.DataFrame(comp_data).set_index("Room"), use_container_width=True)

    # Calendar
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
                if gh: g_rows.append({"Task": h.get("name"), "Start": gh[0], "Finish": gh[1], "Type": "Holiday"})
            st.plotly_chart(render_gantt(g_rows, f"{checkin.year} Calendar"), use_container_width=True)
