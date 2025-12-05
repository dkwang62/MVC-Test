# app.py
# Mobile MVC Rent Calculator + Reliable Static Gantt (matplotlib)
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
# 1. Load data
# =============================================
@st.cache_data
def load_data():
    try:
        with open("data_v2.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("data_v2.json not found!")
        st.stop()

raw_data = load_data()

# =============================================
# 2. West to East
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
# 3. Static Gantt with Matplotlib (100% reliable)
# =============================================
COLORS = {
    "Peak": "#D73027", "High": "#FC8D59", "Mid": "#FEE08B",
    "Low": "#91BFDB", "Holiday": "#9C27B0", "No Data": "#DDDDDD"
}

def season_bucket(name):
    n = (name or "").lower()
    if "peak" in n: return "Peak"
    if "high" in n: return "High"
    if "mid" in n or "shoulder" in n: return "Mid"
    if "low" in n: return "Low"
    return "No Data"

@st.cache_data(ttl=3600)
def render_gantt_matplotlib(resort_data, year_str):
    rows = []
    yd = resort_data.get("years", {}).get(year_str, {})

    # Seasons
    for s in yd.get("seasons", []):
        name = s.get("name", "Season")
        color = season_bucket(name)
        for p in s.get("periods", []):
            try:
                start = datetime.strptime(p["start"], "%Y-%m-%d")
                end = datetime.strptime(p["end"], "%Y-%m-%d")
                rows.append((name, start, end, color))
            except: continue

    # Holidays
    for h in yd.get("holidays", []):
        ref = h.get("global_reference")
        if ref and ref in raw_data.get("global_holidays", {}).get(year_str, {}):
            info = raw_data["global_holidays"][year_str][ref]
            start = datetime.strptime(info["start_date"], "%Y-%m-%d")
            end = datetime.strptime(info["end_date"], "%Y-%m-%d")
            rows.append((h.get("name", "Holiday"), start, end, "Holiday"))

    if not rows:
        return None

    fig, ax = plt.subplots(figsize=(10, max(2, len(rows) * 0.4)))
    for i, (label, start, end, typ) in enumerate(rows):
        ax.barh(i, end - start, left=start, height=0.6,
                color=COLORS.get(typ, "#999999"), edgecolor="black", linewidth=0.8)

    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([label for label, _, _, _ in rows])
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.xaxis.set_minor_locator(mdates.DayLocator(interval=7))
    plt.xticks(rotation=0)
    ax.grid(True, axis='x', alpha=0.3)
    ax.set_title(f"{resort_data.get('display_name')} – {year_str} Season Calendar", pad=20, size=14)

    legend_elements = [
        Patch(facecolor=COLORS.get(k), label=k) for k in ["Peak","High","Mid","Low","Holiday"]
        if any(typ == k for _,_,_,typ in rows)
    ]
    ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1, 1))

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf)

# =============================================
# 4. Calculator
# =============================================
@dataclass
class HolidayObj:
    name: str; start: date; end: date

class MVCRepository:
    def __init__(self, raw): self._raw = raw; self._gh = self._parse_gh()
    def _parse_gh(self):
        p = {}
        for y, hols in self._raw.get("global_holidays", {}).items():
            p[y] = {}
            for n, d in hols.items():
                p[y][n] = (datetime.strptime(d["start_date"], "%Y-%m-%d").date(),
                          datetime.strptime(d["end_date"], "%Y-%m-%d").date())
        return p
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

    def calculate(self, resort_name, room, checkin, nights, rate, mul):
        r = self.repo.get_resort_data(resort_name)
        if not r: return None
        rate = round(rate, 2)
        rows = []; total = 0; disc = False; seen = set()
        i = 0
        while i < nights:
            d = checkin + timedelta(days=i)
            pts, hol = self.get_points(r, d)
            if hol and hol.name not in seen:
                seen.add(hol.name)
                raw = int(pts.get(room, 0))
                eff = math.floor(raw * mul) if mul < 1 else raw
                if eff < raw: disc = True
                rows.append({"Date": f"{hol.name}", "Pts": eff})
                total += eff
                i += (hol.end - hol.start).days + 1
            else:
                raw = int(pts.get(room, 0))
                eff = math.floor(raw * mul) if mul < 1 else raw
                if eff < raw: disc = True
                rows.append({"Date": d.strftime("%a %b %d"), "Pts": eff})
                total += eff
                i += 1
        return type('Res', (), {
            'df': pd.DataFrame(rows),
            'points': total,
            'cost': round(total * rate, 2),
            'disc': disc
        })()

# =============================================
# 5. Init
# =============================================
repo = MVCRepository(raw_data)
calc = MVCCalculator(repo)
resorts_sorted = sort_resorts_west_to_east(repo._raw.get("resorts", []))
options = [r["display_name"] for r in resorts_sorted]

# =============================================
# 6. UI
# =============================================
st.set_page_config(page_title="MVC Rent", layout="centered")
st.title("MVC Rent Calculator")
st.caption("Auto-calculate • Static Gantt • West to East")

resort = st.selectbox("Resort (West to East)", options)
rdata = repo.get_resort_data(resort)
tz = rdata.get("timezone", "America/New_York") if rdata else "America/New_York"

# Rooms
rooms = set()
for y in rdata.get("years", {}).values():
    for s in y.get("seasons", []):
        for c in s.get("day_categories", {}).values():
            rooms.update(c.get("room_points", {}).keys())
room = st.selectbox("Room Type", sorted(rooms)) if rooms else "1BR"

c1, c2 = st.columns(2)
checkin_in = c1.date_input("Check-in", date.today() + timedelta(days=7))
nights = c2.number_input("Nights", 1, 60, 7)

# West to East adjustment
def to_resort_date(d, tz_str):
    try:
        utc = datetime.combine(d, datetime.min.time()).replace(tzinfo=pytz.UTC)
        return utc.astimezone(pytz.timezone(tz_str)).date()
    except: return d
checkin = to_resort_date(checkin_in, tz)
if checkin != checkin_in:
    st.info(f"Adjusted to resort time: **{checkin.strftime('%a %b %d, %Y')}**")

rate = st.number_input("Rate $/pt", 0.30, 1.50, 0.55, 0.05, format="%.2f")
disc = st.selectbox("Discount", ["No Discount", "Executive (25% off)", "Presidential (30% off)"])
mul = 1.0 if "No" in disc else 0.75 if "Exec" in disc else 0.70

# Auto calculate
result = calc.calculate(resort, room, checkin, nights, rate, mul)
if result:
    col1, col2 = st.columns(2)
    col1.metric("Points", f"{result.points:,}")
    col2.metric("Cost", f"${result.cost:,.2f}")
    if result.disc: st.success("Discount Applied!")
    st.dataframe(result.df, use_container_width=True, hide_index=True)

# Static Gantt
with st.expander("Season Calendar", expanded=False):
    img = render_gantt_matplotlib(rdata, str(checkin.year))
    if img:
        st.image(img, use_column_width=True)
    else:
        st.info("No calendar data")

st.caption("data_v2.json loaded • Works on Streamlit Cloud • Mobile ready")
