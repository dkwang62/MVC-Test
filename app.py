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
from typing import List, Optional, Dict, Any
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
# 2. West to East Sorting (inline former utils.py logic)
# =============================================

# Logical West → East ordering for common MVC timezones.
# This list is the PRIMARY source of truth for "west to east"
# ordering within each region.
COMMON_TZ_ORDER = [
    # Hawaii / Alaska / West Coast
    "Pacific/Honolulu",      # Hawaii
    "America/Anchorage",     # Alaska
    "America/Los_Angeles",   # US / Canada West Coast

    # Mexico / Mountain / Central
    "America/Mazatlan",      # Baja California Sur (Los Cabos)
    "America/Denver",        # US Mountain
    "America/Edmonton",      # Canada Mountain
    "America/Chicago",       # US Central
    "America/Winnipeg",      # Canada Central
    "America/Cancun",        # Quintana Roo (Cancún)

    # Eastern / Atlantic / Caribbean
    "America/New_York",      # US East
    "America/Toronto",       # Canada East
    "America/Halifax",       # Atlantic Canada
    "America/Puerto_Rico",   # Caribbean (AW, BS, VI, PR, etc.)
    "America/St_Johns",      # Newfoundland

    # Europe
    "Europe/London",
    "Europe/Paris",
    "Europe/Madrid",

    # Asia / Australia
    "Asia/Bangkok",
    "Asia/Singapore",
    "Asia/Makassar",         # Bali region (Denpasar alias)
    "Asia/Tokyo",
    "Australia/Brisbane",    # Surfers Paradise
    "Australia/Sydney",
]

# Region priority:
#   0 = USA + Canada + Caribbean
#   1 = Mexico + Costa Rica
#   2 = Europe
#   3 = Asia + Australia
#   99 = Everything else / fallback
REGION_US_CARIBBEAN = 0
REGION_MEX_CENTRAL = 1
REGION_EUROPE = 2
REGION_ASIA_AU = 3
REGION_FALLBACK = 99

# US state and DC we treat as "USA" region
US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
    "VA", "WA", "WV", "WI", "WY", "DC",
}

# Canadian provinces (kept in same region bucket as USA for navigation)
CA_PROVINCES = {
    "AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT",
}

# Caribbean / Atlantic codes we group with USA region
CARIBBEAN_CODES = {"AW", "BS", "VI", "PR"}  # Aruba, Bahamas, USVI, Puerto Rico

# Mexico + Central America grouping
MEX_CENTRAL_CODES = {"MX", "CR"}  # Mexico, Costa Rica

# Europe country codes we currently support
EUROPE_CODES = {"ES", "FR", "GB", "UK", "PT", "IT", "DE", "NL", "IE"}

# Asia + Australia country codes we currently support
ASIA_AU_CODES = {"TH", "ID", "SG", "JP", "CN", "MY", "PH", "VN", "AU"}

# Fixed reference date to avoid DST variability in offset calculations
_REF_DT = datetime(2025, 1, 15, 12, 0, 0)

def get_timezone_offset_minutes(tz_name: str) -> int:
    """Return offset from UTC in minutes for a given timezone.

    Used only as a tie-breaker within the same COMMON_TZ_ORDER bucket.
    We use a fixed reference date to avoid DST-vs-standard-time issues.
    """
    try:
        tz = pytz.timezone(tz_name)
    except Exception:
        return 0

    try:
        aware = tz.localize(_REF_DT)
        offset = aware.utcoffset()
        if offset is None:
            return 0
        return int(offset.total_seconds() // 60)
    except Exception:
        return 0

def get_timezone_offset(tz_name: str) -> float:
    """Backwards-compatible helper: UTC offset in HOURS."""
    minutes = get_timezone_offset_minutes(tz_name)
    return minutes / 60.0

def _region_from_code(code: str) -> int:
    """Internal helper: region strictly from resort.code."""
    if not code:
        return REGION_FALLBACK

    code = code.upper()

    if code in US_STATE_CODES:
        return REGION_US_CARIBBEAN

    if code in CA_PROVINCES or code == "CA":
        return REGION_US_CARIBBEAN

    if code in CARIBBEAN_CODES:
        return REGION_US_CARIBBEAN

    if code in MEX_CENTRAL_CODES:
        return REGION_MEX_CENTRAL

    if code in EUROPE_CODES:
        return REGION_EUROPE

    if code in ASIA_AU_CODES:
        return REGION_ASIA_AU

    return REGION_FALLBACK

def _region_from_timezone(tz: str) -> int:
    """Fallback region inference based only on timezone."""
    if not tz:
        return REGION_FALLBACK

    if tz.startswith("America/"):
        # Explicitly treat Cancun and Mazatlan as Mexico/Central bucket
        if tz in ("America/Cancun", "America/Mazatlan"):
            return REGION_MEX_CENTRAL
        return REGION_US_CARIBBEAN

    if tz.startswith("Europe/"):
        return REGION_EUROPE

    if tz.startswith("Asia/") or tz.startswith("Australia/"):
        return REGION_ASIA_AU

    return REGION_FALLBACK

def get_region_priority(resort: Dict[str, Any]) -> int:
    """Map a resort into a logical region bucket."""
    code = (resort.get("code") or "").upper()
    tz = resort.get("timezone") or ""

    region = _region_from_code(code)
    if region != REGION_FALLBACK:
        return region

    return _region_from_timezone(tz)

# Legacy-style human-friendly labels keyed by timezone.
TZ_TO_REGION = {
    # Hawaii / Alaska / West Coast
    "Pacific/Honolulu": "Hawaii",
    "America/Anchorage": "Alaska",
    "America/Los_Angeles": "US West Coast",

    # Mexico / Mountain / Central
    "America/Mazatlan": "Mexico (Pacific)",
    "America/Denver": "US Mountain",
    "America/Edmonton": "Canada Mountain",
    "America/Chicago": "US Central",
    "America/Winnipeg": "Canada Central",
    "America/Cancun": "Mexico (Caribbean)",

    # Eastern / Atlantic / Caribbean
    "America/New_York": "US East Coast",
    "America/Toronto": "Canada East",
    "America/Halifax": "Atlantic Canada",
    "America/Puerto_Rico": "Caribbean",
    "America/St_Johns": "Newfoundland",

    # Europe
    "Europe/London": "UK / Ireland",
    "Europe/Paris": "Western Europe",
    "Europe/Madrid": "Western Europe",

    # Asia / Australia
    "Asia/Bangkok": "SE Asia",
    "Asia/Singapore": "SE Asia",
    "Asia/Makassar": "Indonesia",
    "Asia/Tokyo": "Japan",
    "Australia/Brisbane": "Australia (QLD)",
    "Australia/Sydney": "Australia",
}

def get_region_label(tz: str) -> str:
    """Timezone → region label helper.

    If the timezone is not in TZ_TO_REGION, fall back to last component
    of the tz name (e.g. 'Europe/Paris' → 'Paris').
    """
    if not tz:
        return "Unknown"
    return TZ_TO_REGION.get(tz, tz.split("/")[-1] if "/" in tz else tz)

def sort_resorts_by_timezone(resorts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort resorts first by REGION, then West → East within each region."""
    def sort_key(r: Dict[str, Any]):
        region_prio = get_region_priority(r)

        tz = r.get("timezone") or "UTC"
        if tz in COMMON_TZ_ORDER:
            tz_index = COMMON_TZ_ORDER.index(tz)
        else:
            tz_index = len(COMMON_TZ_ORDER)

        offset_minutes = get_timezone_offset_minutes(tz)
        name = r.get("display_name") or r.get("resort_name") or ""

        return (region_prio, tz_index, offset_minutes, name)

    return sorted(resorts, key=sort_key)

def sort_resorts_west_to_east(resorts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Public API used by the app – resorts West → East with region grouping."""
    return sort_resorts_by_timezone(resorts)

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
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
import io
from PIL import Image
from datetime import datetime

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
    
    # --- Seasons ---
    for s in yd.get("seasons", []):
        name = s.get("name", "Season")
        bucket = season_bucket(name)
        for p in s.get("periods", []):
            try:
                start = datetime.strptime(p["start"], "%Y-%m-%d")
                end = datetime.strptime(p["end"], "%Y-%m-%d")
                rows.append((name, start, end, bucket))
            except:
                continue

    # --- Holidays ---
    for h in yd.get("holidays", []):
        ref = h.get("global_reference")
        if ref and ref in global_holidays.get(year_str, {}):
            info = global_holidays[year_str][ref]
            try:
                start = datetime.strptime(info["start_date"], "%Y-%m-%d")
                end = datetime.strptime(info["end_date"], "%Y-%m-%d")
                rows.append((h.get("name", "Holiday"), start, end, "Holiday"))
            except:
                continue

    if not rows:
        return None

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
    
    legend_elements = [Patch(facecolor=COLORS[k], label=k) for k in COLORS if any(t == k for _, _, _, t in rows)]
    ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1, 1))

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
    def __init__(self, repo):
        self.repo = repo

    def get_points(self, rdata, day):
        y = str(day.year)
        if y not in rdata.get("years", {}):
            return {}, None
        yd = rdata["years"][y]
        for h in yd.get("holidays", []):
            ref = h.get("global_reference")
            if ref and ref in self.repo._gh.get(y, {}):
                s, e = self.repo._gh[y][ref]
                if s <= day <= e:
                    return h.get("room_points", {}), HolidayObj(h.get("name"), s, e)
        dow = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day.weekday()]
        for s in yd.get("seasons", []):
            for p in s.get("periods", []):
                try:
                    ps = datetime.strptime(p["start"], "%Y-%m-%d").date()
                    pe = datetime.strptime(p["end"], "%Y-%m-%d").date()
                    if ps <= day <= pe:
                        for cat in s.get("day_categories", {}).values():
                            if dow in cat.get("day_pattern", []):
                                return cat.get("room_points", {}), None
                except:
                    continue
        return {}, None

    def calculate(self, resort_name, room, checkin, nights, rate, discount_mul):
        r = self.repo.get_resort_data(resort_name)
        if not r:
            return None
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
                if eff < raw:
                    disc_applied = True
                cost = math.ceil(eff * rate)

                rows.append({
                    "Date": f"{holiday.name} ({holiday_start.strftime('%b %d')}–{holiday_end.strftime('%b %d')})",
                    "Pts": eff,
                    "Cost": f"${cost:,}"
                })
                total_pts += eff
                processed_holidays.add(holiday.name)
                # skip to after holiday
                current_date = holiday_end + timedelta(days=1)
            else:
                raw = int(pts_map.get(room, 0))
                eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
                if eff < raw:
                    disc_applied = True
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
        if not r:
            return 0, 0.0
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

def build_rental_cost_table(resort_data: dict, year: int, rate: float, discount_mul: float = 1.0) -> Optional[pd.DataFrame]:
    year_str = str(year)
    yd = resort_data.get("years", {}).get(year_str)
    if not yd:
        return None

    room_types = get_all_room_types_for_resort(resort_data)
    if not room_types:
        return None

    rows = []

    # Seasons
    for season in yd.get("seasons", []):
        name = season.get("name", "").strip() or "Unnamed Season"
        weekly_totals = {}
        has_data = False

        for dow in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            for cat in season.get("day_categories", {}).values():
                if dow in cat.get("day_pattern", []):
                    points_map = cat.get("room_points", {})
                    for room in room_types:
                        pts = int(points_map.get(room, 0))
                        if pts:
                            has_data = True
                        weekly_totals[room] = weekly_totals.get(room, 0) + pts
                    break

        if has_data:
            row = {"Season": name}
            for room in room_types:
                raw = weekly_totals.get(room, 0)
                eff = math.floor(raw * discount_mul) if discount_mul < 1 else raw
                row[room] = f"${math.ceil(eff * rate):,}"
            rows.append(row)

    # Holidays
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
    except:
        return d

#checkin = adjust_checkin(checkin_input, tz)
checkin = checkin_input
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
    global_holidays = raw_data.get("global_holidays", {}) 
    img = render_gantt_image(rdata, str(checkin.year), global_holidays)
    
    if img:
        st.image(img, use_column_width=True)

    df = build_rental_cost_table(rdata, checkin.year, rate, mul)
    if df is not None:
        st.caption(f"7-Night Rental Costs @ ${rate:.2f}/pt{' — Elite discount applied' if mul < 1 else ''}")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No season or holiday pricing data available for this year.")
        
st.markdown("---")
st.caption("Auto-calculate • Full resort name • Holiday logic fixed • Last updated: Dec 7, 2025 @ 6:31 Singapore")
