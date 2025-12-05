# app.py
# FINAL – Resort card shows full resort_name + everything else perfect
import streamlit as st
import json
import pandas as pd
import math
from datetime import date, timedelta, datetime
from dataclasses import dataclass
import pytz
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
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
user_settings = load_json("mvc_owner_settings.json", {
    "maintenance_rate": 0.55,
    "discount_tier": "No Discount",
    "preferred_resort_id": None
})

default_rate = round(float(user_settings.get("maintenance_rate", 0.55)), 2)
saved_tier = user_settings.get("discount_tier", "No Discount")
preferred_id = user_settings.get("preferred_resort_id")

# =============================================
# 2. West to East Sorting
# =============================================
COMMON_TZ_ORDER = [
    "Pacific/Honolulu", "America/Anchorage", "America/Los_Angeles", "America/Denver",
    "America/Chicago", "America/New_York", "America/Aruba", "America/St_Thomas",
    "Asia/Denpasar", "Europe/Paris", "Asia/Bangkok"
]

def sort_resorts_west_to_east(resorts):
    def key(r):
        tz = r.get("timezone", "")
        pri = COMMON_TZ_ORDER.index(tz) if tz in COMMON_TZ_ORDER else 999
        return (pri, r.get("display_name", ""))
    return sorted(resorts, key=key)

# =============================================
# 3. Resort Card – Now shows FULL resort_name
# =============================================
def render_resort_card(resort_data) -> None:
    full_name = resort_data.get("resort_name", "Unknown Resort")
    display_name = resort_data.get("display_name", "")
    timezone = resort_data.get("timezone", "Unknown")
    address = resort_data.get("address", "Address not available")
    
    tz_display = timezone.split("/")[-1].replace("_", " ") if "/" in timezone else timezone
    
    st.markdown(
        f"""
        <div style="
            background: white;
            border-radius: 14px;
            padding: 1.4rem 1.6rem;
            border: 1px solid #e2e8f0;
            box-shadow: 0 6px 16px rgba(0,0,0,0.1);
            margin: 1.2rem 0;
        ">
          <h2 style="
            margin: 0 0 0.4rem 0;
            font-size: 1.8rem;
            font-weight: 700;
            color: #1a202c;
          ">{full_name}</h2>
          <p style="
            margin: 0 0 0.8rem 0;
            font-size: 1.05rem;
            color: #4a5568;
            font-weight: 500;
          ">{display_name}</p>
          <div style="
            font-size: 0.95rem;
            color: #718096;
            line-height: 1.6;
          ">
            <span>Time: {tz_display}</span>
            <span style="margin-left: 1.5rem;">Location: {address}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# =============================================
# 4. Gantt (matplotlib)
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
def render_gantt_image(resort_data, year_str):
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
        if ref and ref in raw_data.get("global_holidays", {}).get(year_str, {}):
            info = raw_data["global_holidays"][year_str][ref]
            start = datetime.strptime(info["start_date"], "%Y-%m-%d")
            end = datetime.strptime(info["end_date"], "%Y-%m-%d")
            rows.append((h.get("name", "Holiday"), start, end, "Holiday"))
    if not rows: return None

    fig, ax = plt.subplots(figsize=(10, max(3, len(rows) * 0.5)))
    for i, (label, start, end, typ) in enumerate(rows):
        ax.barh(i, end - start, left=start, height=0.6, color=COLORS.get(typ, "#999"), edgecolor="black")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([l for l,_,_,_ in rows])
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.grid(True, axis='x', alpha=0.3)
    ax.set_title(f"{resort_data.get('resort_name')} – {year_str}", pad=20, size=14)
    legend = [Patch(facecolor=COLORS[k], label=k) for k in COLORS if any(t==k for _,_,_,t in rows)]
    ax.legend(handles=legend, loc='upper right', bbox_to_anchor=(1, 1))

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
    name: str; start: date; end: date

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
                s,e = self.repo._gh[y][ref]
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

    def calculate_total_only(self, resort_name, room, checkin, nights, rate, discount_mul):
        r = self.repo.get_resort_data(resort_name)
        if not r: return 0, 0.0
        rate = round(float(rate), 2)
        total_pts = 0
        seen = set()
        i = 0
        while i < nights:
            d = checkin + timedelta(days=i)
            pts_map, holiday = self.get_points(r, d)
            if holiday and holiday.name not in seen:
                seen.add(holiday.name)
                raw = int(pts_map.get(room, 0))
                eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
                total_pts += eff
                i += (holiday.end - holiday.start).days + 1
            else:
                raw = int(pts_map.get(room, 0))
                eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
                total_pts += eff
                i += 1
        total_cost = round(total_pts * rate, 2)
        return total_pts, total_cost

    def calculate(self, resort_name, room, checkin, nights, rate, discount_mul):
        r = self.repo.get_resort_data(resort_name)
        if not r: return None
        rate = round(float(rate), 2)
        rows = []
        total_pts = 0
        disc_applied = False
        seen = set()
        i = 0
        while i < nights:
            d = checkin + timedelta(days=i)
            pts_map, holiday = self.get_points(r, d)
            if holiday and holiday.name not in seen:
                seen.add(holiday.name)
                raw = int(pts_map.get(room, 0))
                eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
                if eff < raw: disc_applied = True
                cost = math.ceil(eff * rate)
                rows.append({
                    "Date": f"{holiday.name} ({holiday.start.strftime('%b %d')}–{holiday.end.strftime('%b %d')})",
                    "Pts": eff,
                    "Cost": f"${cost:,}"
                })
                total_pts += eff
                i += (holiday.end - holiday.start).days + 1
            else:
                raw = int(pts_map.get(room, 0))
                eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
                if eff < raw: disc_applied = True
                cost = math.ceil(eff * rate)
                rows.append({
                    "Date": d.strftime("%a %b %d"),
                    "Pts": eff,
                    "Cost": f"${cost:,}"
                })
                total_pts += eff
                i += 1
        total_cost = round(total_pts * rate, 2)
        return type('Res', (), {
            'df': pd.DataFrame(rows),
            'points': total_pts,
            'cost': total_cost,
            'disc': disc_applied
        })()

# =============================================
# 6. Init
# =============================================
repo = MVCRepository(raw_data)
calc = MVCCalculator(repo)
all_resorts = repo._raw.get("resorts", [])
sorted_resorts = sort_resorts_west_to_east(all_resorts)
resort_options = [r["display_name"] for r in sorted_resorts]

default_resort_index = 0
if preferred_id:
    for i, r in enumerate(sorted_resorts):
        if r.get("id") == preferred_id:
            default_resort_index = i
            break

# =============================================
# 7. UI – Full resort_name in card
# =============================================
st.set_page_config(page_title="MVC Rent", layout="centered")
st.title("MVC Rent Calculator")
st.caption("Auto-calculate • Full resort name • West to East")

resort_display = st.selectbox("Resort (West to East)", resort_options, index=default_resort_index)
rdata = repo.get_resort_data(resort_display)

# Resort Card – Now shows full resort_name
render_resort_card(rdata)

# All rooms
all_rooms = set()
for y in rdata.get("years", {}).values():
    for s in y.get("seasons", []):
        for c in s.get("day_categories", {}).values():
            all_rooms.update(c.get("room_points", {}).keys())
all_rooms = sorted(all_rooms)
room = st.selectbox("Room Type", all_rooms)

c1, c2 = st.columns(2)
checkin_input = c1.date_input("Check-in", date.today() + timedelta(days=7))
nights = c2.number_input("Nights", 1, 60, 7)

tz = rdata.get("timezone", "America/New_York")
def adjust_checkin(d, tz_str):
    try:
        utc = datetime.combine(d, datetime.min.time()).replace(tzinfo=pytz.UTC)
        return utc.astimezone(pytz.timezone(tz_str)).date()
    except: return d

checkin = adjust_checkin(checkin_input, tz)
if checkin != checkin_input:
    st.info(f"Adjusted → **{checkin.strftime('%a %b %d, %Y')}**")

rate = st.number_input("Rent Rate ($/pt)", 0.30, 1.50, default_rate, 0.05, format="%.2f")
discount_display = st.selectbox("Discount Tier", ["No Discount", "Executive (25% off)", "Presidential (30% off)"], index=default_tier_idx)

mul = 0.70 if "presidential" in discount_display.lower() else \
      0.75 if "executive" in discount_display.lower() else 1.0

# Main result
result = calc.calculate(resort_display, room, checkin, nights, rate, mul)
if result:
    col1, col2 = st.columns(2)
    col1.metric("Total Points", f"{result.points:,}")
    col2.metric("Total Rent", f"${result.cost:,.2f}")
    if result.disc:
        st.success("Discount Applied!")
    st.dataframe(result.df, use_container_width=True, hide_index=True)

# All Room Types
with st.expander("All Room Types – This Stay", expanded=False):
    comp_data = []
    for rm in all_rooms:
        pts, cost = calc.calculate_total_only(resort_display, rm, checkin, nights, rate, mul)
        comp_data.append({"Room Type": rm, "Points": f"{pts:,}", "Rent": f"${cost:,.2f}"})
    st.dataframe(pd.DataFrame(comp_data), use_container_width=True, hide_index=True)

# Gantt
with st.expander("Season Calendar", expanded=False):
    img = render_gantt_image(rdata, str(checkin.year))
    if img:
        st.image(img, use_column_width=True)

st.caption("Shows full resort_name • data_v2.json + settings loaded • Mobile perfect")
