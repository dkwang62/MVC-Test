# app.py
# MVC Rent Calculator – Mobile First
# Last modified: Dec 15, 2025 (fixed: re-added missing math import)

import streamlit as st
import json
import pandas as pd
import math  # Required for math.ceil() and math.floor()
from datetime import date, timedelta, datetime
from dataclasses import dataclass
import matplotlib.pyplot as plt
import matplotlib.dates as mdates  # Required for Gantt chart
from typing import List, Dict, Any, Optional
import io
from PIL import Image

# =============================================
# 1. Load JSON files
# =============================================
@st.cache_data
def load_json(file_path, default=None):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.warning(f"{file_path} not found – using defaults")
        return default or {}

raw_data = load_json("data_v2.json")
user_settings = load_json("mvc_owner_settings.json", {})
default_rate = round(float(user_settings.get("renter_rate", 0.55)), 2)
saved_tier = user_settings.get("renter_discount_tier", "No Discount")
preferred_id = user_settings.get("preferred_resort_id")

# =============================================
# 2. Resort selection grid (simplified region grouping)
# =============================================
def render_resort_grid(
    resorts: List[Dict[str, Any]],
    current_resort_key: Optional[str] = None,
    *,
    title: str = "🏨 Select a Resort (grouped by region)",
) -> None:
    slot = st.empty()
    # If hidden, show "Change resort" button
    if not st.session_state.get("show_resort_picker", True):
        with slot.container():
            current_name = st.session_state.get("current_resort_name") or "Selected resort"
            if st.button("Change resort", key="btn_change_resort"):
                st.session_state.show_resort_picker = True
                st.rerun()
        return

    # Full picker in expander
    with slot.expander(title, expanded=True):
        if not resorts:
            st.info("No resorts available.")
            return

        region_groups = {}
        for resort in resorts:
            code = (resort.get("code") or "").upper()
            tz = resort.get("timezone", "UTC")

            # Simple manual region labels
            if tz == "Pacific/Honolulu":
                region = "Hawaii"
            elif tz == "America/Anchorage":
                region = "Alaska"
            elif tz == "America/Los_Angeles":
                region = "US West Coast"
            elif tz in ("America/Denver", "America/Edmonton"):
                region = "US Mountain"
            elif tz in ("America/Chicago", "America/Winnipeg"):
                region = "US Central"
            elif tz in ("America/New_York", "America/Toronto"):
                region = "US East Coast"
            elif tz == "America/Halifax":
                region = "Atlantic Canada"
            elif tz == "America/Puerto_Rico":
                region = "Caribbean"
            elif code in ["MX", "CR"] or tz in ("America/Mazatlan", "America/Cancun"):
                region = "Central America"
            elif tz.startswith("Europe/"):
                region = "Western Europe" if tz in ("Europe/London", "Europe/Paris", "Europe/Madrid") else "Europe"
            elif tz.startswith("Asia/") or tz.startswith("Australia/"):
                region = "Asia Pacific"
            else:
                region = "Unknown"

            region_groups.setdefault(region, []).append(resort)

        desired_region_order = [
            "Hawaii", "Alaska", "US West Coast", "US Mountain", "US Central",
            "US East Coast", "Caribbean", "Central America",
            "Western Europe", "Europe", "Asia Pacific", "Unknown"
        ]

        for region in desired_region_order:
            if region not in region_groups:
                continue
            region_resorts = region_groups[region]
            st.markdown(f"**{region}**")
            num_cols = min(6, len(region_resorts))
            cols = st.columns(num_cols)
            for idx, resort in enumerate(region_resorts):
                col = cols[idx % num_cols]
                with col:
                    rid = resort.get("id")
                    name = resort.get("display_name", rid or "Unknown")
                    is_current = current_resort_key in (rid, name)
                    btn_type = "primary" if is_current else "secondary"
                    if st.button(
                        name,
                        key=f"resort_btn_{rid or name}_{idx}",
                        type=btn_type,
                        width="stretch",
                    ):
                        st.session_state.current_resort_id = rid
                        st.session_state.current_resort_name = name
                        st.session_state.show_resort_picker = False
                        st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)

# =============================================
# 3. Resort Card
# =============================================
def render_resort_card(resort_data) -> None:
    full_name = resort_data.get("resort_name", "Unknown Resort")
    address = resort_data.get("address", "")
    st.markdown(
        f"""
        <div style="
            background: white;
            border-radius: 12px;
            padding: 1rem 1.2rem;
            border: 1px solid #e2e8f0;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            margin: 0.8rem 0;
            text-align: center;
        ">
          <h3 style="margin: 0 0 0.6rem 0; font-size: 1.45rem; font-weight: 700; color: #1a202c;">{full_name}</h3>
          <div style="font-size: 0.9rem; color: #718096;">
            {f"<div>{address}</div>" if address else ""}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# =============================================
# 4. Gantt Chart
# =============================================
COLORS = {"Peak": "#D73027", "High": "#FC8D59", "Mid": "#FEE08B", "Low": "#91BFDB", "Holiday": "#9C27B0"}

def season_bucket(name):
    n = (name or "").lower()
    if "peak" in n: return "Peak"
    if "high" in n: return "High"
    if "mid" in n or "shoulder" in n: return "Mid"
    if "low" in n: return "Low"
    return "Low"

@st.cache_data(ttl=3600)
def render_gantt_image(resort_data, year_str, global_holidays):
    rows = []
    yd = resort_data.get("years", {}).get(year_str, {})
    
    for s in yd.get("seasons", []):
        name = s.get("name", "Season")
        bucket = season_bucket(name)
        for p in s.get("periods", []):
            try:
                start = datetime.strptime(p["start"], "%Y-%m-%d")
                end = datetime.strptime(p["end"], "%Y-%m-%d")
                rows.append((name, start, end, bucket))
            except: continue
    
    for h in yd.get("holidays", []):
        ref = h.get("global_reference")
        if ref and ref in global_holidays.get(year_str, {}):
            info = global_holidays[year_str][ref]
            try:
                start = datetime.strptime(info["start_date"], "%Y-%m-%d")
                end = datetime.strptime(info["end_date"], "%Y-%m-%d")
                rows.append((h.get("name", "Holiday"), start, end, "Holiday"))
            except: continue
    
    if not rows: return None
    
    fig, ax = plt.subplots(figsize=(10, max(3, len(rows) * 0.5)))
    for i, (label, start, end, typ) in enumerate(rows):
        ax.barh(i, end - start, left=start, height=0.6, color=COLORS.get(typ, "#999"), edgecolor="black")
    
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([label for label, _, _, _ in rows])
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.grid(True, axis='x', alpha=0.3)
    ax.set_title(f"{resort_data.get('resort_name')} – {year_str}", pad=12, size=12)
    
    legend_elements = [plt.Rectangle((0,0),1,1, facecolor=COLORS[k], label=k) for k in COLORS if any(t==k for _,_,_,t in rows)]
    ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1, 1))
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf)

# =============================================
# 5. Calculator Core
# =============================================
@dataclass
class HolidayObj:
    name: str
    start: date
    end: date

class MVCRepository:
    def __init__(self, raw):
        self._raw = raw
        self._gh = {}
        for y, hols in raw.get("global_holidays", {}).items():
            self._gh[y] = {}
            for n, d in hols.items():
                self._gh[y][n] = (
                    datetime.strptime(d["start_date"], "%Y-%m-%d").date(),
                    datetime.strptime(d["end_date"], "%Y-%m-%d").date()
                )

    def get_resort_data(self, name):
        return next((r for r in self._raw.get("resorts", []) if r["display_name"] == name), None)

class MVCCalculator:
    def __init__(self, repo): self.repo = repo

    def get_points(self, rdata, day):
        y = str(day.year)
        if y not in rdata.get("years", {}): return {}, None
        yd = rdata["years"][y]
        
        for h in yd.get("holidays", []):
            ref = h.get("global_reference")
            if ref and ref in self.repo._gh.get(y, {}):
                s, e = self.repo._gh[y][ref]
                if s <= day <= e:
                    return h.get("room_points", {}), HolidayObj(h.get("name"), s, e)
        
        dow = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][day.weekday()]
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

    def calculate(self, resort_name, room, checkin, nights, rate, discount_mul):
        r = self.repo.get_resort_data(resort_name)
        if not r: return None
        rate = round(float(rate), 2)
        rows = []
        total_pts = 0
        disc_applied = False
        processed_holidays = set()
        current_date = checkin
        end_date = checkin + timedelta(days=nights - 1)
        
        while current_date <= end_date:
            pts_map, holiday = self.get_points(r, current_date)
            raw = int(pts_map.get(room, 0))
            eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
            if eff < raw: disc_applied = True
            cost = math.ceil(eff * rate)
            
            if holiday and holiday.name not in processed_holidays:
                holiday_start = max(current_date, holiday.start)
                holiday_end = min(end_date, holiday.end)
                rows.append({
                    "Date": f"{holiday.name} ({holiday_start.strftime('%b %d')}–{holiday_end.strftime('%b %d')})",
                    "Pts": eff,
                    "Cost": f"${cost:,}"
                })
                total_pts += eff
                processed_holidays.add(holiday.name)
                current_date = holiday_end + timedelta(days=1)
            else:
                rows.append({
                    "Date": current_date.strftime("%a %b %d"),
                    "Pts": eff,
                    "Cost": f"${cost:,}"
                })
                total_pts += eff
                current_date += timedelta(days=1)
        
        total_cost = round(total_pts * rate, 2)
        return type('Res', (), {
            'df': pd.DataFrame(rows),
            'points': total_pts,
            'cost': total_cost,
            'disc': disc_applied
        })()

    def calculate_total_only(self, resort_name, room, checkin, nights, rate, discount_mul):
        r = self.repo.get_resort_data(resort_name)
        if not r: return 0, 0.0
        rate = round(float(rate), 2)
        total_pts = 0
        processed_holidays = set()
        current_date = checkin
        end_date = checkin + timedelta(days=nights - 1)
        
        while current_date <= end_date:
            pts_map, holiday = self.get_points(r, current_date)
            raw = int(pts_map.get(room, 0))
            eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
            total_pts += eff
            if holiday and holiday.name not in processed_holidays:
                processed_holidays.add(holiday.name)
                current_date = min(end_date, holiday.end) + timedelta(days=1)
            else:
                current_date += timedelta(days=1)
        
        total_cost = round(total_pts * rate, 2)
        return total_pts, total_cost

def get_all_room_types_for_resort(resort_data: dict) -> List[str]:
    rooms = set()
    for year_obj in resort_data.get("years", {}).values():
        for season in year_obj.get("seasons", []):
            for cat in season.get("day_categories", {}).values():
                rp = cat.get("room_points", {})
                if isinstance(rp, dict):
                    rooms.update(rp.keys())
        for holiday in year_obj.get("holidays", []):
            rp = holiday.get("room_points", {})
            if isinstance(rp, dict):
                rooms.update(rp.keys())
    return sorted(rooms)

def build_rental_cost_table(resort_data: dict, year: int, rate: float, discount_mul: float = 1.0) -> Optional[pd.DataFrame]:
    year_str = str(year)
    yd = resort_data.get("years", {}).get(year_str)
    if not yd:
        return None
    room_types = get_all_room_types_for_resort(resort_data)
    if not room_types:
        return None
    rows = []
    for season in yd.get("seasons", []):
        name = season.get("name", "").strip() or "Unnamed Season"
        weekly_totals = {}
        has_data = False
        for dow in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
            for cat in season.get("day_categories", {}).values():
                if dow in cat.get("day_pattern", []):
                    points_map = cat.get("room_points", {})
                    for room in room_types:
                        pts = int(points_map.get(room, 0))
                        if pts: has_data = True
                        weekly_totals[room] = weekly_totals.get(room, 0) + pts
                    break
        if has_data:
            row = {"Season": name}
            for room in room_types:
                raw = weekly_totals.get(room, 0)
                eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
                row[room] = f"${math.ceil(eff * rate):,}"
            rows.append(row)
    
    for holiday in yd.get("holidays", []):
        hname = holiday.get("name", "").strip() or "Unnamed Holiday"
        rp = holiday.get("room_points", {}) or {}
        row = {"Season": f"Holiday – {hname}"}
        for room in room_types:
            raw = int(rp.get(room, 0))
            eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
            row[room] = f"${math.ceil(eff * rate):,}" if raw else "—"
        rows.append(row)
    
    if not rows:
        return None
    return pd.DataFrame(rows, columns=["Season"] + room_types)

# =============================================
# 6. Init & UI
# =============================================
repo = MVCRepository(raw_data)
calc = MVCCalculator(repo)
all_resorts = repo._raw.get("resorts", [])

# Session state initialization
if "current_resort_id" not in st.session_state:
    st.session_state.current_resort_id = preferred_id
if "current_resort_name" not in st.session_state:
    if preferred_id:
        preferred_resort = next((r for r in all_resorts if r.get("id") == preferred_id), None)
        st.session_state.current_resort_name = preferred_resort["display_name"] if preferred_resort else None
    else:
        st.session_state.current_resort_name = None

current_resort_name = st.session_state.current_resort_name
rdata = repo.get_resort_data(current_resort_name) if current_resort_name else None

# Default membership tier index
saved_tier_str = saved_tier or "No Discount"
saved_lower = saved_tier_str.lower()
default_tier_idx = 2 if "presidential" in saved_lower or "chairman" in saved_lower else \
                   1 if "executive" in saved_lower else 0

# UI
st.set_page_config(page_title="MVC Rent", layout="centered")
st.markdown("<h1 style='font-size: 1.9rem; margin: 0.5rem 0;'>MVC Rent Calculator</h1>", unsafe_allow_html=True)

render_resort_grid(
    resorts=all_resorts,
    current_resort_key=st.session_state.get("current_resort_id") or st.session_state.get("current_resort_name"),
)

if not rdata:
    st.warning("Please select a resort to continue.")
    st.stop()

render_resort_card(rdata)

all_rooms = get_all_room_types_for_resort(rdata)
if not all_rooms:
    st.error("No room types found for this resort.")
    st.stop()

room = st.selectbox("Room Type", sorted(all_rooms))

c1, c2 = st.columns(2)
checkin_input = c1.date_input("Check-in", date.today() + timedelta(days=7))
nights = c2.number_input("Nights", 1, 60, 7)
checkin = checkin_input

rate = st.number_input(
    "MVC Abound Maintenance Rate ($/pt)",
    0.30, 1.50, default_rate, 0.01, format="%.2f"
)

membership_display = st.selectbox(
    "MVC Membership Tier",
    ["Ordinary Level", "Executive Level", "Presidential Level"],
    index=default_tier_idx
)

mul = 0.70 if "Presidential" in membership_display else \
      0.75 if "Executive" in membership_display else 1.0

result = calc.calculate(current_resort_name, room, checkin, nights, rate, mul)

if result:
    col1, col2 = st.columns(2)
    col1.metric("Total Points", f"{result.points:,}")
    col2.metric("Total Rent", f"${result.cost:,.2f}")
    if result.disc:
        st.success("Membership benefits applied")
    st.dataframe(result.df, width="stretch", hide_index=True)

with st.expander("All Room Types – This Stay", expanded=False):
    comp_data = []
    for rm in all_rooms:
        pts, cost = calc.calculate_total_only(current_resort_name, rm, checkin, nights, rate, mul)
        comp_data.append({"Room Type": rm, "Points": f"{pts:,}", "Rent": f"${cost:,.2f}"})
    st.dataframe(pd.DataFrame(comp_data), width="stretch", hide_index=True)

with st.expander("Season Calendar", expanded=False):
    global_holidays = raw_data.get("global_holidays", {})
    img = render_gantt_image(rdata, str(checkin.year), global_holidays)
    if img:
        st.image(img, use_column_width=True)
    df = build_rental_cost_table(rdata, checkin.year, rate, mul)
    if df is not None:
        st.caption(f"7-Night Rental Costs @ ${rate:.2f}/pt{' — Elite discount applied' if mul < 1 else ''}")
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.info("No season or holiday pricing data available for this year.")

st.markdown("---")
st.caption("Region-grouped resort grid • Central America includes Mexico + Costa Rica • Last updated: Dec 15, 2025")
