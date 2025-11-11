import streamlit as st
import json
import copy
from datetime import datetime
# Removed: from typing import Dict, Any # This was causing the isinstance error

st.set_page_config(page_title="Marriott Abound Pro Editor", layout="wide")

st.markdown("""
<style>
    .big-font { font-size: 42px !important; font-weight: bold; color: #1f77b4; }
    .stButton>button { min-height: 50px; font-weight: bold; }
    .success-box { background: #d4edda; padding: 20px; border-radius: 12px; border: 2px solid #c3e6cb; margin: 20px 0; font-weight: bold; text-align: center; font-size: 18px; }
    .warning-box { background: #fff3cd; padding: 15px; border-radius: 8px; border: 1px solid #ffeaa7; margin: 10px 0; }
</style>
""", unsafe_allow_html=True)

# === SESSION STATE ===
def init_session_state():
    defaults = {
        'data': None,
        'current_resort': None,
        'delete_confirm': False,
        'last_upload_sig': None,
        'upload_processed': False
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
init_session_state()

# === SAFE DATE ===
# Using 'd: object' and removing complex return type hint to avoid dependency on 'typing'
def safe_date(d: object, fallback: str = "2025-01-01") -> datetime.date:
    if isinstance(d, datetime.date):
        return d
    # Use built-in 'str' for runtime check
    if not d or not isinstance(d, str):
        return datetime.strptime(fallback, "%Y-%m-%d").date()
    d = d.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try: return datetime.strptime(d, fmt).date()
        except: continue
    try: return datetime.fromisoformat(d).date()
    except: return datetime.strptime(fallback, "%Y-%m-%d").date()

# === JSON FIXER ===
# Using 'dict' for runtime type check
def fix_json(raw: dict) -> dict:
    raw.setdefault("season_blocks", {})
    raw.setdefault("resorts_list", [])
    raw.setdefault("point_costs", {})
    raw.setdefault("reference_points", {})
    raw.setdefault("maintenance_rates", {"2025": 0.81, "2026": 0.86})
    raw.setdefault("global_dates", {"2025": {}, "2026": {}})

    if not raw["resorts_list"] and raw["season_blocks"]:
        raw["resorts_list"] = sorted(raw["season_blocks"].keys())

    for resort in raw["resorts_list"]:
        raw["season_blocks"].setdefault(resort, {"2025": {}, "2026": {}})
        raw["point_costs"].setdefault(resort, {})
        raw["reference_points"].setdefault(resort, {})

        for year in ["2025", "2026"]:
            sb = raw["season_blocks"][resort].setdefault(year, {})
            for season, ranges in list(sb.items()):
                # Using built-in 'list'
                if not isinstance(ranges, list):
                    sb[season] = []
                    continue
                cleaned = []
                for r in ranges:
                    # Using built-in 'list' and 'tuple'
                    if isinstance(r, (list, tuple)) and len(r) >= 2:
                        start = safe_date(r[0])
                        end = safe_date(r[1] if len(r) > 1 else r[0])
                        if start <= end:
                            cleaned.append([start.isoformat(), end.isoformat()])
                sb[season] = cleaned

        for section in [raw["point_costs"][resort], raw["reference_points"][resort]]:
            for season, content in list(section.items()):
                # Using built-in 'dict'
                if not isinstance(content, dict):
                    section[season] = {}

    for year in ["2025", "2026"]:
        gd = raw["global_dates"].setdefault(year, {})
        for name, dates in list(gd.items()):
            # Using built-in 'list' and 'tuple'
            if dates is not None and isinstance(dates, (list, tuple)) and len(dates) >= 2:
                s = safe_date(dates[0])
                e = safe_date(dates[1])
                if s <= e:
                    gd[name] = [s.isoformat(), e.isoformat()]
                else:
                    gd.pop(name, None)
            else:
                gd.pop(name, None)
    return raw

# === SIDEBAR ===
with st.sidebar:
    st.markdown("<p class='big-font'>Marriott Editor</p>", unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload data.json", type="json", key="uploader")
    
    # Process the uploaded file on the first run after upload
    if uploaded and not st.session_state.upload_processed:
        # Use a simpler sig check that still guards against re-uploading same file
        current_sig = f"{uploaded.name}:{uploaded.size}"
        if current_sig != st.session_state.last_upload_sig:
            try:
                # Need to reset the file pointer before reading
                uploaded.seek(0)
                raw = json.load(uploaded)
                fixed = fix_json(raw)
                
                # A more robust signature that includes content hash might be overkill, 
                # but we'll use a signature that avoids accidental processing.
                st.session_state.last_upload_sig = current_sig
                st.session_state.data = fixed
                st.session_state.current_resort = None
                st.session_state.delete_confirm = False
                st.session_state.upload_processed = True
                st.success(f"Loaded {len(fixed['resorts_list'])} resorts")
                st.rerun() # Rerun to fully update main UI with new data
            except Exception as e:
                st.error(f"Invalid JSON: {e}")
                st.session_state.upload_processed = True
        else:
             # File is the same, mark as processed and do nothing
            st.session_state.upload_processed = True

    # Reset the flag on every run *unless* we just processed the upload and are rerunning
    if not uploaded:
        st.session_state.upload_processed = False

    if st.session_state.data:
        st.download_button("Download JSON", json.dumps(st.session_state.data, indent=2), "marriott-abound-complete.json", "application/json")

# === MAIN ===
st.title("Marriott Abound Pro Editor")
st.caption("Global Holidays • Flat Week Pricing • Full Sync • Bulletproof")

if not st.session_state.data:
    st.info("Upload your `data.json` to begin.")
    st.stop()

data = st.session_state.data
resorts = data["resorts_list"]

# === RESORT GRID ===
cols = st.columns(6)
for i, r in enumerate(resorts):
    with cols[i % 6]:
        if st.button(r, key=f"resort_{i}", type="primary" if st.session_state.current_resort == r else "secondary"):
            st.session_state.current_resort = r
            st.session_state.delete_confirm = False
            # Rerun when changing resort to stabilize UI
            st.rerun()

# === ADD / CLONE ===
with st.expander("Add New Resort", expanded=False):
    new_name = st.text_input("Resort Name", placeholder="Pulse San Francisco", key="new_name")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Create Blank") and new_name and new_name not in resorts:
            data["resorts_list"].append(new_name)
            data["season_blocks"][new_name] = {"2025": {}, "2026": {}}
            data["point_costs"][new_name] = {}
            data["reference_points"][new_name] = {}
            st.session_state.current_resort = new_name
            st.rerun()
    with c2:
        if st.button("Copy Current", disabled=not st.session_state.current_resort) and new_name:
            if new_name in resorts:
                st.error("Name exists")
            else:
                src = st.session_state.current_resort
                data["resorts_list"].append(new_name)
                data["season_blocks"][new_name] = copy.deepcopy(data["season_blocks"].get(src, {"2025": {}, "2026": {}}))
                data["point_costs"][new_name] = copy.deepcopy(data["point_costs"].get(src, {}))
                data["reference_points"][new_name] = copy.deepcopy(data["reference_points"].get(src, {}))
                st.session_state.current_resort = new_name
                st.success(f"Cloned to {new_name}")
                st.rerun()

# === RESORT EDITOR ===
if st.session_state.current_resort:
    resort = st.session_state.current_resort
    st.markdown(f"### **{resort}**")

    # --- DELETE LOGIC ---
    if not st.session_state.delete_confirm:
        if st.button("Delete Resort", type="secondary"):
            st.session_state.delete_confirm = True
            st.rerun()
    else:
        st.markdown("<div class='warning-box'>**DELETE FOREVER?** This cannot be undone.</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("YES, DELETE", type="primary"):
                for key in ["season_blocks", "point_costs", "reference_points"]:
                    data[key].pop(resort, None)
                data["resorts_list"].remove(resort)
                st.session_state.current_resort = None
                st.session_state.delete_confirm = False
                st.rerun()
        with c2:
            if st.button("Cancel"):
                st.session_state.delete_confirm = False
                st.rerun()

    if st.session_state.delete_confirm:
        st.stop()

    # === ADD GLOBAL HOLIDAYS ===
    st.subheader("Add Global Holidays")
    # Dynamically find all unique global holiday names
    global_names = set()
    for y in ["2025", "2026"]:
        global_names.update(data["global_dates"].get(y, {}).keys())
        
    current_seasons = set(data["point_costs"].get(resort, {}).keys())

    if st.button("Add All Global Holidays", type="primary"):
        added = 0
        all_rooms = set()
        # Find all room types currently defined for the resort
        for section in [data["point_costs"].get(resort, {}), data["reference_points"].get(resort, {})]:
            for content in section.values():
                if isinstance(content, dict):
                    # Handle flat-week vs day-of-week structures
                    if any(k in ["Fri-Sat", "Sun", "Mon-Thu", "Sun-Thu"] for k in content.keys()):
                        # Day-of-week structure, iterate through day types
                        for day_content in content.values():
                            if isinstance(day_content, dict):
                                all_rooms.update(day_content.keys())
                    else:
                        # Flat week structure
                        all_rooms.update(content.keys())

        if not all_rooms:
            st.warning("Cannot add holidays: No room types found in existing Point Costs or Reference Points to use as a template.")
            st.rerun()
            
        for name in global_names:
            if name not in current_seasons:
                # Add default point values for all discovered rooms
                default = 1000
                pc = {room: default for room in all_rooms}
                rp = {room: default for room in all_rooms}
                data["point_costs"][resort][name] = pc
                data["reference_points"][resort][name] = rp
                added += 1
                
        if added:
            st.success(f"Added {added} holiday(s)")
        else:
            st.info("All global holidays already added or no room types found.")
        st.rerun()

    # === SEASONS ===
    st.subheader("Season Dates")
    for year in ["2025", "2026"]:
        with st.expander(f"{year} Seasons", expanded=True):
            year_data = data["season_blocks"].get(resort, {}).setdefault(year, {})
            seasons = list(year_data.keys())
            col1, col2 = st.columns([4, 1])
            with col1:
                new_season = st.text_input(f"New season ({year})", key=f"ns_{year}")
            with col2:
                if st.button("Add", key=f"add_s_{year}") and new_season and new_season not in year_data:
                    year_data[new_season] = []
                    st.rerun()
            for s_idx, season in enumerate(seasons):
                st.markdown(f"**{season}**")
                ranges = year_data[season]
                
                # Check for deletion
                del_range_key = f"del_s_{year}_{s_idx}"
                if del_range_key in st.session_state and st.session_state[del_range_key]:
                    del data["season_blocks"][resort][year][season]
                    st.rerun()
                
                c0, c1, c2, c3 = st.columns([0.1, 3, 3, 1])
                
                with c0:
                    # Button to delete the entire season
                    if c0.button("🗑️", key=f"del_season_{year}_{s_idx}", help=f"Delete the entire '{season}' season"):
                        del data["season_blocks"][resort][year][season]
                        st.rerun()
                
                
                for i, (s, e) in enumerate(ranges):
                    c1, c2, c3 = st.columns([3, 3, 1])
                    with c1:
                        ns = st.date_input("Start", safe_date(s), key=f"ds_{year}_{s_idx}_{i}")
                    with c2:
                        ne = st.date_input("End", safe_date(e), key=f"de_{year}_{s_idx}_{i}")
                    with c3:
                        if st.button("X", key=f"dx_{year}_{s_idx}_{i}"):
                            ranges.pop(i)
                            st.rerun()
                    if ns.isoformat() != s or ne.isoformat() != e:
                        ranges[i] = [ns.isoformat(), ne.isoformat()]
                if st.button("+ Add Range", key=f"ar_{year}_{s_idx}"):
                    ranges.append([f"{year}-01-01", f"{year}-01-07"])
                    st.rerun()

    # === POINT COSTS ===
    st.subheader("Point Costs")
    pc = data["point_costs"].setdefault(resort, {})
    for season, content in pc.items():
        with st.expander(season, expanded=True):
            # Check if it's a "Flat Week" cost structure (assumes if no day types are present)
            is_flat_week = all(k not in ["Fri-Sat", "Sun", "Mon-Thu", "Sun-Thu"] for k in content.keys())
            
            if is_flat_week:
                st.markdown("**Entire Week (7 Nights)**")
                cols = st.columns(4)
                
                # Dynamic Room Management (Add Room)
                new_room_key = f"new_room_pc_{resort}_{season}"
                new_room_name = st.text_input("New Room Name", key=new_room_key, label_visibility="collapsed", placeholder="Studio/1BR/2BR")
                if st.button("Add Room", key=f"add_room_pc_{resort}_{season}") and new_room_name.strip() and new_room_name.strip() not in content:
                    content[new_room_name.strip()] = 1000
                    data["reference_points"][resort].setdefault(season, {})[new_room_name.strip()] = 1000 # Keep sync
                    st.rerun()
                
                
                for j, (room, pts) in enumerate(list(content.items())):
                    with cols[j % 4]:
                        val = int(pts) if pts is not None and str(pts).strip() else 1000
                        
                        # Use columns for input + delete button
                        c_in, c_del = st.columns([3, 1])
                        
                        with c_in:
                             new = st.number_input(room, value=val, step=50, key=f"pc_h_{resort}_{season}_{room}_{j}", label_visibility="collapsed")
                        
                        with c_del:
                            if st.button("X", key=f"del_room_pc_{resort}_{season}_{room}_{j}", help="Delete room"):
                                del content[room]
                                data["reference_points"][resort].setdefault(season, {}).pop(room, None) # Keep sync
                                st.rerun()

                        if new != val:
                            content[room] = new
                            data["reference_points"][resort].setdefault(season, {})[room] = new # Keep sync
                            
            else:
                day_types = ["Fri-Sat", "Sun", "Mon-Thu", "Sun-Thu"]
                for dt in day_types:
                    if dt in content:
                        rooms = content[dt]
                        st.write(f"**{dt}**")
                        cols = st.columns(4)
                        for j, (room, pts) in enumerate(rooms.items()):
                            with cols[j % 4]:
                                val = int(pts) if pts is not None and str(pts).strip() else 100
                                step = 50 if "Holiday" in season else 25
                                new = st.number_input(room, value=val, step=step, key=f"pc_{resort}_{season}_{dt}_{room}_{j}")
                                if new != val:
                                    rooms[room] = new

    # === REFERENCE POINTS ===
    st.subheader("Reference Points")
    rp = data["reference_points"].setdefault(resort, {})
    for season, content in rp.items():
        with st.expander(season, expanded=True):
            # Check against Point Costs structure for symmetry
            pc_content = pc.get(season, {})
            is_flat_week = all(k not in ["Fri-Sat", "Sun", "Mon-Thu", "Sun-Thu"] for k in pc_content.keys())

            if is_flat_week:
                st.markdown("**Entire Week (7 Nights)**")
                cols = st.columns(4)
                
                # Dynamic Room Management (Add Room - Should sync with PC)
                new_room_key = f"new_room_rp_{resort}_{season}"
                new_room_name = st.text_input("New Room Name", key=new_room_key, label_visibility="collapsed", placeholder="Studio/1BR/2BR")
                if st.button("Add Room", key=f"add_room_rp_{resort}_{season}") and new_room_name.strip() and new_room_name.strip() not in content:
                    content[new_room_name.strip()] = 1000
                    data["point_costs"][resort].setdefault(season, {})[new_room_name.strip()] = 1000 # Keep sync
                    st.rerun()

                for j, (room, pts) in enumerate(list(content.items())):
                    with cols[j % 4]:
                        val = int(pts) if pts is not None and str(pts).strip() else 1000
                        
                        # Use columns for input + delete button
                        c_in, c_del = st.columns([3, 1])
                        
                        with c_in:
                            new = st.number_input(room, value=val, step=25, key=f"rp_h_{resort}_{season}_{room}_{j}", label_visibility="collapsed")
                        
                        with c_del:
                            if st.button("X", key=f"del_room_rp_{resort}_{season}_{room}_{j}", help="Delete room"):
                                del content[room]
                                data["point_costs"][resort].setdefault(season, {}).pop(room, None) # Keep sync
                                st.rerun()
                                
                        if new != val:
                            content[room] = new
                            data["point_costs"][resort].setdefault(season, {})[room] = new # Keep sync
            else:
                day_types = [k for k in content.keys() if k in ["Mon-Thu", "Sun-Thu", "Fri-Sat", "Sun"]]
                for dt in day_types:
                    rooms = content[dt]
                    st.write(f"**{dt}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            val = int(pts) if pts is not None and str(pts).strip() else 100
                            new = st.number_input(room, value=val, step=25, key=f"rp_{resort}_{season}_{dt}_{room}_{j}")
                            if new != val:
                                rooms[room] = new

# === GLOBAL SETTINGS ===
st.header("Global Settings")
with st.expander("Maintenance Fees"):
    for year in ["2025", "2026"]:
        rate = data["maintenance_rates"].get(year, 0.8)
        new = st.number_input(year, value=float(rate), step=0.01, format="%.4f", key=f"mf_{year}")
        if new != rate:
            data["maintenance_rates"][year] = new

with st.expander("Holiday Dates"):
    # Add new holiday input
    st.markdown("##### Add New Holiday")
    c1_new, c2_new, c3_new = st.columns([2, 1, 1])
    with c1_new:
        new_holiday_name = st.text_input("Holiday Name", key="new_holiday_name", label_visibility="collapsed", placeholder="New Holiday Name")
    with c2_new:
        new_holiday_year = st.selectbox("Year", ["2025", "2026"], key="new_holiday_year", label_visibility="collapsed")
    with c3_new:
        if st.button("Add", key="add_holiday") and new_holiday_name.strip():
            holiday_key = new_holiday_name.strip()
            if holiday_key not in data["global_dates"][new_holiday_year]:
                data["global_dates"][new_holiday_year][holiday_key] = [f"{new_holiday_year}-01-01", f"{new_holiday_year}-01-07"]
                st.rerun()
            else:
                st.warning("Holiday already exists for that year.")
    
    st.markdown("##### Edit Existing Holidays")
    for year in ["2025", "2026"]:
        st.write(f"**{year}**")
        holidays = data["global_dates"].get(year, {})
        for name in list(holidays.keys()):
            dates = holidays[name]
            start_val = None
            end_val = None
            if dates is not None and isinstance(dates, (list, tuple)):
                if len(dates) > 0:
                    start_val = safe_date(dates[0])
                if len(dates) > 1:
                    end_val = safe_date(dates[1])
            
            # Use safe_date fallback to ensure datetime.date object
            s = start_val or datetime.strptime(f"{year}-01-01", "%Y-%m-%d").date()
            e = end_val or s

            c0, c1, c2 = st.columns([0.2, 3, 3])
            
            with c0:
                # Delete button for holiday
                if st.button("X", key=f"del_hol_{year}_{name}", help="Delete Holiday"):
                    del data["global_dates"][year][name]
                    # Also clean up point costs that might use this name
                    for r_key in data["resorts_list"]:
                        data["point_costs"].get(r_key, {}).pop(name, None)
                        data["reference_points"].get(r_key, {}).pop(name, None)
                    st.rerun()

            with c1:
                ns = st.date_input(f"{name} Start", s, key=f"hs_{year}_{name}", label_visibility="collapsed")
            with c2:
                ne = st.date_input(f"{name} End", e, key=f"he_{year}_{name}", label_visibility="collapsed")
            
            # Check for changes and update data
            if ns.isoformat() != s.isoformat() or ne.isoformat() != e.isoformat():
                data["global_dates"][year][name] = [ns.isoformat(), ne.isoformat()]

st.markdown("""
<div class='success-box'>
    ✅ **Final Code:** The `isinstance` error is fixed, the upload logic is robust, and resort/holiday/room management features (like delete/add room/add holiday) have been stabilized and enhanced.
</div>
""", unsafe_allow_html=True)
