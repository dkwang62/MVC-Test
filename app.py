# app.py
# MVC Rent Calculator – Mobile First
# Last modified: Dec 7, 2025 @ 6:31 Singapore

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
from typing import List, Optional
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
# 3. Resort Card – No timezone
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
          <h3 style="
            margin: 0 0 0.6rem 0;
            font-size: 1.45rem;
            font-weight: 700;
            color: #1a202c;
            line-height: 1.2;
          ">{full_name}</h3>
          <div style="
            font-size: 0.9rem;
            color: #718096;
          ">
            {f"<div>{address}</div>" if address else ""}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# =============================================
# 4. Gantt – Fixed unpacking + Streamlit 1.40+ compatible
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
    ax.set_yticklabels([label for label, _, _, _ in rows])
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.grid(True, axis='x', alpha=0.3)
    ax.set_title(f"{resort_data.get('resort_name')} – {year_str}", pad=12, size=12)
    legend = [Patch(facecolor=COLORS[k], label=k) for k in COLORS if any(t==k for _,_,_,t in rows)]
    ax.legend(handles=legend, loc='upper right', bbox_to_anchor=(1, 1))

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf)

# =============================================
# 5. Calculator Core – Perfect Holiday Logic
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

            if holiday and holiday.name not in processed_holidays:
                holiday_start = max(current_date, holiday.start)
                holiday_end = min(end_date, holiday.end)

                raw = int(pts_map.get(room, 0))
                eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
                if eff < raw: disc_applied = True
                cost = math.ceil(eff * rate)

                rows.append({
                    "Date": f"{holiday.name} ({holiday_start.strftime('%b %d')}–{holiday_end.strftime('%b %d')})",
                    "Pts": eff,
                    "Cost": f"${cost:,}"
                })
                total_pts += eff
                processed_holidays.add(holiday.name)
                current_date = holiday_end + timedelta(days=1)
             # skip to after holiday
            else:
                raw = int(pts_map.get(room, 0))
                eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
                if eff < raw: disc_applied = True
                cost = math.ceil(eff * rate)

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
    """Extract every room type that appears in any season or holiday of the resort."""
    rooms = set()
    for year_obj in resort_data.get("years", {}).values():
        # Seasons
        for season in year_obj.get("seasons", []):
            for cat in season.get("day_categories", {}).values():
                rp = cat.get("room_points", {})
                if isinstance(rp, dict):
                    rooms.update(rp.keys())
        # Holidays
        for holiday in year_obj.get("holidays", []):
            rp = holiday.get("room_points", {})
            if isinstance(rp, dict):
                rooms.update(rp.keys())
    return sorted(rooms)


def build_rental_cost_table(resort_data: dict, year: int, rate: float, discount_mul: float = 1.0) -> Optional[str]:
    year_str = str(year)
    yd = resort_data.get("years", {}).get(year_str)
    if not yd:
        return None

    room_types = get_all_room_types_for_resort(resort_data)
    if not room_types:
        return None

    rows = []

    # ——— Seasons ———
    for season in yd.get("seasons", []):
        name = season.get("name", "").strip() or "Unnamed Season"
        weekly_totals = {}
        has_data = False

        for dow in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            for cat in season.get("day_categories", {}).values():
                if dow in cat.get("day_pattern", []):
                    points_map = cat.get("room_points", {})
                    for room in room_types:
                        pts = points_map.get(room, 0)
                        if pts:
                            has_data = True
                        weekly_totals[room] = weekly_totals.get(room, 0) + int(pts)
                    break

        if has_data:
            row = {"Season": name}
            for room in room_types:
                raw_pts = weekly_totals.get(room, 0)
                eff_pts = math.floor(raw_pts * discount_mul) if discount_mul < 1 else raw_pts
                cost = math.ceil(eff_pts * rate)
                row[room] = f"${cost:,}"
            rows.append(row)

    # ——— Holidays ———
    for holiday in yd.get("holidays", []):
        hname = holiday.get("name", "").strip() or "Unnamed Holiday"
        rp = holiday.get("room_points", {}) or {}
        row = {"Season": f"Holiday – {hname}"}
        any_value = False
        for room in room_types:
            raw = int(rp.get(room, 0))
            if raw:
                any_value = True
            eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
            cost = math.ceil(eff * rate) if raw else 0
            row[room] = f"${cost:,}" if raw else "—"
        if any_value:
            rows.append(row)

    if not rows:
        return None

    # Build proper HTML table manually (bypass pandas escaping issues)
    header = "".join(f"<th>{room}</th>" for room in room_types)
    body = ""
    for row in rows:
        season = row["Season"]
        cells = "".join(f"<td>{row.get(room, '—')}</td>" for room in room_types)
        body += f"<tr><td class='season-cell'>{season}</td>{cells}</tr>"


    discount_note = ""
    if discount_mul < 1:
        discount_note = "<small style='color:#059669; font-weight:600;'> (Elite discount applied)</small>"

    html = f"""
    <div style="margin-top: 2rem;">
        <div style="padding: 0.9rem 1rem; background: #f1f5f9; border-left: 4px solid #3b82f6; border-radius: 6px; margin-bottom: 1rem;">
            <strong style="font-size: 1.15rem; color: #1e293b;">
                7-Night Rental Costs ({year}) @ ${rate:.2f}/pt
            </strong>
            {discount_note}
        </div>

        <!-- This wrapper is the key for mobile scrolling -->
        <div style="overflow-x: auto; -webkit-overflow-scrolling: touch;">
            <table class="cost-table">
                <thead>
                    <tr>
                        <th style="position: sticky; left: 0; background: #f8fafc; z-index: 10; text-align: left; min-width: 170px;">Season</th>
                        {header}
                    </tr>
                </thead>
                <tbody>
                    {body}
                </tbody>
            </table>
        </div>
    </div>

    <style>
        .cost-table {{
            width: 100%;
            min-width: 1200px;           /* Forces horizontal scroll on small screens */
            border-collapse: separate;
            border-spacing: 0;
            font-size: 0.94rem;
            background: white;
            box-shadow: 0 4px 12px rgba(0,0,0,0.06);
            border-radius: 8px;
            overflow: hidden;
        }}
        .cost-table th {{
            padding: 1rem 0.8rem;
            text-align: center;
            background: #f8fafc;
            font-weight: 600;
            color: #1e293b;
            border-bottom: 2px solid #3b82f6;
            white-space: nowrap;
            top: 0;
            z-index: 9;
        }}
        .cost-table td {{
            padding: 0.9rem 0.8rem;
            text-align: center;
            border-bottom: 1px solid #e2e8f0;
            background: white;
        }}
        .cost-table .season-cell {{
            position: sticky;
            left: 0;
            background: white;
            font-weight: 500;
            text-align: left !important;
            min-width: 170px;
            z-index: 8;
            box-shadow: 2px 0 6px -2px rgba(0,0,0,0.1);
        }}
        .cost-table tr:hover td {{
            background-color: #f8faff !important;
        }}
        .cost-table tr:hover .season-cell {{
            background-color: #dbeafe !important;
        }}
        /* Smooth scrolling on iOS */
        .cost-table-wrapper {{
            -webkit-overflow-scrolling: touch;
        }}
    </style>
    """
    return html    
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

saved_lower = saved_tier.lower()
default_tier_idx = 2 if "presidential" in saved_lower or "chairman" in saved_lower else \
                   1 if "executive" in saved_lower else 0

# =============================================
# 7. UI – Streamlit 1.40+ Ready
# =============================================
st.set_page_config(page_title="MVC Rent", layout="centered")
st.markdown("<h1 style='font-size: 1.9rem; margin: 0.5rem 0;'>MVC Rent Calculator</h1>", unsafe_allow_html=True)

resort_display = st.selectbox("Resort (West to East)", resort_options, index=default_resort_index)
rdata = repo.get_resort_data(resort_display)
render_resort_card(rdata)

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
    st.info(f"Adjusted to resort time: **{checkin.strftime('%a %b %d, %Y')}**")

rate = st.number_input(
    "MVC Abound Maintenance Rate ($/pt)",
    0.30, 1.50, default_rate, 0.05, format="%.2f"
)

membership_display = st.selectbox(
    "MVC Membership Tier",
    ["Ordinary Level", "Executive Level", "Presidential Level"],
    index=default_tier_idx
)

mul = 0.70 if "Presidential" in membership_display else \
      0.75 if "Executive" in membership_display else 1.0

result = calc.calculate(resort_display, room, checkin, nights, rate, mul)
if result:
    col1, col2 = st.columns(2)
    col1.metric("Total Points", f"{result.points:,}")
    col2.metric("Total Rent", f"${result.cost:,.2f}")
    if result.disc:
        st.success("Membership benefits applied")
    st.dataframe(result.df, width='stretch', hide_index=True)

with st.expander("All Room Types – This Stay", expanded=False):
    comp_data = []
    for rm in all_rooms:
        pts, cost = calc.calculate_total_only(resort_display, rm, checkin, nights, rate, mul)
        comp_data.append({"Room Type": rm, "Points": f"{pts:,}", "Rent": f"${cost:,.2f}"})
    st.dataframe(pd.DataFrame(comp_data), width='stretch', hide_index=True)

with st.expander("Season Calendar", expanded=False):
    img = render_gantt_image(rdata, str(checkin.year))
    if img:
        st.image(img, use_column_width=True)

    # ——— NEW: Rental Cost Table in $ ———
    cost_table_html = build_rental_cost_table(
        resort_data=rdata,
        year=checkin.year,
        rate=rate,
        discount_mul=mul  # applies Presidential/Executive discount correctly
    )
    if cost_table_html:
        st.markdown(cost_table_html, unsafe_allow_html=True)
    else:
        st.info("No season or holiday pricing data available for this year.")
        

st.markdown("---")
st.caption("Auto-calculate • Full resort name • Holiday logic fixed • Last updated: Dec 7, 2025 @ 6:31 Singapore")
