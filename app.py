import streamlit as st
import json
import copy
from datetime import datetime

st.set_page_config(page_title="Marriott Data Editor", layout="wide")

st.markdown("""
<style>
    .big-font { font-size: 42px !important; font-weight: bold; color: #1f77b4; }
    .stButton>button { min-height: 50px; font-weight: bold; }
    .success-box { background: #d4edda; padding: 20px; border-radius: 12px; border: 2px solid #c3e6cb; margin: 20px 0; font-weight: bold; text-align: center; font-size: 18px; }
    .rename-input { margin: 5px 0; }
</style>
""", unsafe_allow_html=True)

# === SESSION STATE & REFRESH CONTROL ===
if 'refresh_trigger' not in st.session_state: st.session_state.refresh_trigger = False
if st.session_state.refresh_trigger: st.session_state.refresh_trigger = False; st.rerun()
if 'last_upload_sig' not in st.session_state: st.session_state.last_upload_sig = None
if 'delete_confirm' not in st.session_state: st.session_state.delete_confirm = False
if 'data' not in st.session_state: st.session_state.data = None
if 'current_resort' not in st.session_state: st.session_state.current_resort = None

data = st.session_state.data
current_resort = st.session_state.current_resort

def save_data():
    """Saves the current state of the global 'data' dictionary to session state."""
    st.session_state.data = data

def safe_date(d, f="2025-01-01"):
    """Safely converts a date string (or None) to a datetime.date object, defaulting to f."""
    if not d or not isinstance(d, str): return datetime.strptime(f, "%Y-%m-%d").date()
    try: return datetime.fromisoformat(d.strip()).date()
    except:
        try: return datetime.strptime(d.strip(), "%Y-%m-%d").date()
        except: return datetime.strptime(f, "%Y-%m-%d").date()

# === JSON FIX & SANITIZE ===
def fix_json(raw):
    raw.setdefault("season_blocks", {})
    raw.setdefault("resorts_list", sorted(raw.get("season_blocks", {}).keys()))
    raw.setdefault("point_costs", {})
    raw.setdefault("reference_points", {})
    raw.setdefault("maintenance_rates", {"2025": 0.81, "2026": 0.86})
    raw.setdefault("global_dates", {"2025": {}, "2026": {}})
    raw.setdefault("holiday_weeks", {})
    for r in raw["resorts_list"]:
        raw["season_blocks"].setdefault(r, {"2025": {}, "2026": {}})
        raw["point_costs"].setdefault(r, {})
        raw["reference_points"].setdefault(r, {})
        raw["holiday_weeks"].setdefault(r, {"2025": {}, "2026": {}})
        for y in ("2025", "2026"):
            sb = raw["season_blocks"][r].setdefault(y, {})
            for s, rngs in list(sb.items()):
                if not isinstance(rngs, list) or any(not isinstance(x, (list, tuple)) or len(x) != 2 for x in rngs):
                    sb[s] = []
    return raw

# === SIDEBAR: UPLOAD & DOWNLOAD ===
with st.sidebar:
    st.markdown("<p class='big-font'>Marriott Editor</p>", unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload data.json", type="json")
    if uploaded:
        size = getattr(uploaded, "size", None)
        sig = f"{uploaded.name}:{size}"
        if sig != st.session_state.last_upload_sig:
            try:
                raw = json.load(uploaded)
                fixed = fix_json(raw)
                st.session_state.data = fixed
                data = fixed
                st.session_state.current_resort = None
                st.session_state.last_upload_sig = sig
                st.success(f"Loaded {len(fixed['resorts_list'])} resorts")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    if st.session_state.data:
        st.download_button("Download", json.dumps(st.session_state.data, indent=2), "marriott-abound-complete.json", "application/json")

# === MAIN UI ===
st.title("Marriott Data Editor")
st.caption("Rename • Add • Delete • Sync — All in One Place")

if not data:
    st.info("Upload your data.json to start")
    st.stop()

resorts = data["resorts_list"]

# === RESORT GRID ===
cols = st.columns(6)
for i, r in enumerate(resorts):
    with cols[i % 6]:
        if st.button(r, key=f"resort_btn_{i}", type="primary" if current_resort == r else "secondary"):
            st.session_state.current_resort = r
            st.session_state.delete_confirm = False
            st.rerun()

# === ADD / CLONE RESORT ===
with st.expander("Add New Resort", expanded=True):
    new = st.text_input("Name", placeholder="Pulse San Francisco", key="new_resort_name")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Create Blank", key="create_blank_btn") and new and new not in resorts:
            data["resorts_list"].append(new)
            data["season_blocks"][new] = {"2025": {}, "2026": {}}
            data["point_costs"][new] = {}
            data["reference_points"][new] = {}
            data["holiday_weeks"][new] = {"2025": {}, "2026": {}}
            st.session_state.current_resort = new
            save_data()
            st.rerun()
    with c2:
        if st.button("Copy Current", key="copy_current_btn", type="primary") and current_resort and new:
            if new in resorts:
                st.error("Exists")
            else:
                data["resorts_list"].append(new)
                data["season_blocks"][new] = copy.deepcopy(data["season_blocks"].get(current_resort, {"2025": {}, "2026": {}}))
                data["point_costs"][new] = copy.deepcopy(data["point_costs"].get(current_resort, {}))
                data["reference_points"][new] = copy.deepcopy(data["reference_points"].get(current_resort, {}))
                data["holiday_weeks"][new] = copy.deepcopy(data["holiday_weeks"].get(current_resort, {"2025": {}, "2026": {}}))
                st.session_state.current_resort = new
                save_data()
                st.success(f"CLONED → **{new}**")
                st.rerun()

# === RESORT EDITOR ===
if current_resort:
    st.markdown(f"### **{current_resort}**")

    # === DELETE RESORT (BULLETPROOF) ===
    if not st.session_state.delete_confirm:
        if st.button("Delete Resort", key="delete_resort_init", type="secondary"):
            st.session_state.delete_confirm = True
            st.rerun()
    else:
        st.warning(f"Are you sure you want to **permanently delete {current_resort}**?")
        c1, c2 = st.columns(2)
        with c1:
            if st.checkbox("I understand — this cannot be undone", key="delete_confirm_check"):
                if st.button("DELETE FOREVER", key="delete_resort_final", type="primary"):
                    for b in ["season_blocks", "point_costs", "reference_points", "holiday_weeks"]:
                        data[b].pop(current_resort, None)
                    data["resorts_list"].remove(current_resort)
                    st.session_state.current_resort = None
                    st.session_state.delete_confirm = False
                    save_data()
                    st.rerun()
        with c2:
            if st.button("Cancel", key="delete_cancel"):
                st.session_state.delete_confirm = False
                st.rerun()

    if st.session_state.delete_confirm:
        st.stop()

    # === RENAME SEASONS ===
    st.subheader("Rename Seasons (Applies to All Years & Sections)")
    seasons_used = set()
    for y in ["2025", "2026"]:
        seasons_used.update(data["season_blocks"][current_resort].get(y, {}).keys())
    seasons_used.update(data["point_costs"].get(current_resort, {}).keys())
    seasons_used.update(data["reference_points"].get(current_resort, {}).keys())
    seasons_used = sorted(seasons_used)

    for old_name in seasons_used:
        c1, c2 = st.columns([3, 1])
        with c1:
            new_name = st.text_input(f"Rename **{old_name}** →", value=old_name, key=f"rename_season_{old_name}")
        with c2:
            if st.button("Apply", key=f"apply_rename_season_{old_name}") and new_name != old_name and new_name:
                for y in ["2025", "2026"]:
                    if old_name in data["season_blocks"][current_resort].get(y, {}):
                        data["season_blocks"][current_resort][y][new_name] = data["season_blocks"][current_resort][y].pop(old_name)
                if old_name in data["point_costs"].get(current_resort, {}):
                    data["point_costs"][current_resort][new_name] = data["point_costs"][current_resort].pop(old_name)
                if old_name in data["reference_points"].get(current_resort, {}):
                    data["reference_points"][current_resort][new_name] = data["reference_points"][current_resort].pop(old_name)
                save_data()
                st.success(f"Renamed **{old_name}** → **{new_name}**")
                st.rerun()

    # === ADD / DELETE SEASON ===
    st.subheader("Add / Delete Season")
    new_season = st.text_input("New Season Name", key="new_season_input")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Add Season", key="add_season_btn") and new_season:
            for y in ["2025", "2026"]:
                data["season_blocks"][current_resort].setdefault(y, {})[new_season] = []
            data["reference_points"].setdefault(current_resort, {})[new_season] = {}
            data["point_costs"].setdefault(current_resort, {})[new_season] = {} 
            save_data()
            st.success(f"Added **{new_season}**")
            st.rerun()
    with c2:
        del_season = st.selectbox("Delete Season", [""] + seasons_used, key="del_season_select")
        if st.button("Delete Season", key="delete_season_btn") and del_season:
            for y in ["2025", "2026"]:
                data["season_blocks"][current_resort].get(y, {}).pop(del_season, None)
            data["point_costs"].get(current_resort, {}).pop(del_season, None)
            data["reference_points"].get(current_resort, {}).pop(del_season, None)
            save_data()
            st.success(f"Deleted **{del_season}**")
            st.rerun()

    # === RENAME ROOM TYPES ===
    st.subheader("Rename Room Types (Applies Everywhere)")
    all_rooms = set()
    for section in [data["point_costs"].get(current_resort, {}), data["reference_points"].get(current_resort, {})]:
        for season_data in section.values():
            for day_or_room in season_data.values():
                if isinstance(day_or_room, dict):
                    all_rooms.update(day_or_room.keys())
    all_rooms = sorted(all_rooms)

    for old_room in all_rooms:
        c1, c2 = st.columns([3, 1])
        with c1:
            new_room = st.text_input(f"Rename **{old_room}** →", value=old_room, key=f"rename_room_{old_room}")
        with c2:
            if st.button("Apply", key=f"apply_rename_room_{old_room}") and new_room != old_room and new_room:
                for section in [data["point_costs"].get(current_resort, {}), data["reference_points"].get(current_resort, {})]:
                    for season in section:
                        for day_type in section[season]:
                            if old_room in section[season][day_type]:
                                section[season][day_type][new_room] = section[season][day_type].pop(old_room)
                save_data()
                st.success(f"Renamed **{old_room}** → **{new_room}**")
                st.rerun()

    # === ADD / DELETE ROOM TYPE (FIXED: NO DUPLICATE IDs) ===
    st.subheader("Add / Delete Room Type")
    new_room_name = st.text_input("New Room Type", key="new_room_input")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Add Room Type", key="add_room_btn") and new_room_name:
            default_points = {"Mon-Thu": 100, "Fri-Sat": 200, "Sun": 150, "Sun-Thu": 120}
            for season in data["reference_points"].get(current_resort, {}):
                for day_type in ["Mon-Thu", "Fri-Sat", "Sun", "Sun-Thu"]:
                    if day_type in data["reference_points"][current_resort][season]:
                         data["reference_points"][current_resort][season][day_type].setdefault(new_room_name, default_points[day_type])
                    else: 
                         for sub_season_data in data["reference_points"][current_resort][season].values():
                              if isinstance(sub_season_data, dict):
                                   sub_season_data.setdefault(new_room_name, default_points["Mon-Thu"]) 
            save_data()
            st.success(f"Added **{new_room_name}**")
            st.rerun()
    with c2:
        del_room = st.selectbox("Delete Room Type", [""] + all_rooms, key="del_room_select")
        if st.button("Delete Room", key="delete_room_btn") and del_room:
            for section in [data["point_costs"].get(current_resort, {}), data["reference_points"].get(current_resort, {})]:
                for season in section:
                    for day_type in section[season]:
                        if isinstance(section[season][day_type], dict):
                             section[season][day_type].pop(del_room, None)
                        else:
                             section[season].pop(del_room, None) 
            save_data()
            st.success(f"Deleted **{del_room}**")
            st.rerun()

# --- Holiday Week Management Section (Synchronization logic for reference_points and holiday_weeks) ---
    st.subheader("Manage Individual Holiday Weeks")
    st.caption("Add or remove specific holiday weeks (e.g., Presidents Day) from this resort's **Reference Points**.")

    HOLIDAY_SEASON_KEY = "Holiday Week"
    
    ref_points_data = data["reference_points"].get(current_resort, {})
    ref_points_data.setdefault(HOLIDAY_SEASON_KEY, {})
    
    all_global_holidays = set(data["global_dates"].get("2025", {}).keys()).union(data["global_dates"].get("2026", {}).keys())
    all_global_holidays = {h for h in all_global_holidays if h} 

    current_active_holidays_set = set(ref_points_data.get(HOLIDAY_SEASON_KEY, {}).keys()) 
    current_active_holidays_sorted = sorted(current_active_holidays_set)
    
    resort_rooms = set()
    for season_data in data["reference_points"].get(current_resort, {}).values():
        for day_or_room in season_data.values():
            if isinstance(day_or_oroom, dict):
                resort_rooms.update(day_or_room.keys())
    resort_rooms = sorted(resort_rooms)

    if not all_global_holidays:
        st.warning("No global holiday dates are defined in Global Settings.")
    else:
        
        if current_active_holidays_sorted:
            st.info(f"✅ Active Holiday Weeks: **{', '.join(current_active_holidays_sorted)}**")
        else:
            st.info("No holiday weeks are currently active for this resort. Use the control below to add one.")

        c1, c2 = st.columns(2)

        # --- REMOVE HOLIDAY ---
        with c1:
            st.markdown("##### Remove Holiday Week")
            del_holiday = st.selectbox("Select Holiday to Remove", [""] + current_active_holidays_sorted, key="del_holiday_select")
            if st.button("Remove Selected Holiday", key="remove_holiday_btn", disabled=not del_holiday):
                ref_points_data.get(HOLIDAY_SEASON_KEY, {}).pop(del_holiday, None)
                
                # Synchronization: Remove from holiday_weeks
                data["holiday_weeks"].get(current_resort, {}).get("2025", {}).pop(del_holiday, None)
                data["holiday_weeks"].get(current_resort, {}).get("2026", {}).pop(del_holiday, None)
                
                save_data()
                st.success(f"Removed holiday **{del_holiday}**.")
                st.rerun()

        # --- ADD HOLIDAY ---
        with c2:
            st.markdown("##### Add Holiday Week")
            
            available_to_add = sorted(list(all_global_holidays - current_active_holidays_set))
            
            add_holiday = st.selectbox("Select Holiday to Add", [""] + available_to_add, key="add_holiday_select")
            
            if st.button("Add Selected Holiday", key="add_holiday_btn", type="primary", disabled=not add_holiday):
                
                default_pts_per_room = {
                    "Doubles": 1750,
                    "King": 1750,
                    "King City": 1925,
                    "2-Bedroom": 3500,
                }
                
                new_holiday_data = {}
                for room in resort_rooms:
                    new_holiday_data[room] = default_pts_per_room.get(room, 1500)
                
                if not new_holiday_data: 
                     new_holiday_data = default_pts_per_room
                
                # Synchronization: Add to reference_points
                ref_points_data.get(HOLIDAY_SEASON_KEY, {})[add_holiday] = copy.deepcopy(new_holiday_data)

                # Synchronization: Add to holiday_weeks
                data["holiday_weeks"].setdefault(current_resort, {}).setdefault("2025", {})[add_holiday] = f"global:{add_holiday}"
                data["holiday_weeks"].setdefault(current_resort, {}).setdefault("2026", {})[add_holiday] = f"global:{add_holiday}"

                save_data()
                st.success(f"Added holiday **{add_holiday}**.")
                st.rerun()
# --- End Holiday Week Management Section ---

    # === SEASON DATES (REVERTED TO STABLE CODE) ===
    st.subheader("Season Dates")
    for year in ["2025", "2026"]:
        with st.expander(f"{year} Seasons", expanded=True):
            year_data = data["season_blocks"][current_resort].setdefault(year, {})
            seasons = list(year_data.keys())
            
            # Add New Season UI
            col1, col2 = st.columns([4, 1])
            with col1:
                new_s = st.text_input(f"New season ({year})", key=f"ns_{year}")
            with col2:
                if st.button("Add", key=f"add_s_{year}") and new_s and new_s not in year_data:
                    year_data[new_s] = []
                    save_data()
                    st.rerun()
            
            # Loop for Season Date Editing (STABLE LAYOUT)
            for s_idx, season in enumerate(seasons):
                st.markdown(f"**{season}**") # Renders the season name
                
                ranges = year_data[season]
                
                # This simple structure avoids the previous TypeError:
                with st.expander("Edit Date Ranges", expanded=True, key=f"range_exp_{year}_{s_idx}"): 
                    for i, (s, e) in enumerate(ranges):
                        c1, c2, c3 = st.columns([3, 3, 1])
                        with c1:
                            ns = st.date_input("Start", safe_date(s), key=f"ds_{year}_{s_idx}_{i}")
                        with c2:
                            ne = st.date_input("End", safe_date(e), key=f"de_{year}_{s_idx}_{i}")
                        with c3:
                            if st.button("X", key=f"dx_{year}_{s_idx}_{i}"):
                                ranges.pop(i)
                                save_data()
                                st.rerun()
                        
                        if ns.isoformat() != s or ne.isoformat() != e:
                            ranges[i] = [ns.isoformat(), ne.isoformat()]
                            save_data()

                    if st.button("+ Add Range", key=f"ar_{year}_{s_idx}"):
                        ranges.append([f"{year}-01-01", f"{year}-01-07"])
                        save_data()
                        st.rerun()
    # === END SEASON DATES REVERSION ===

    st.subheader("Point Costs")
    point_data = data["point_costs"].get(current_resort, {})
    for season, content in point_data.items():
        with st.expander(season, expanded=True):
            is_holiday_season = all(isinstance(v, dict) for v in content.values())
            
            if is_holiday_season:
                for holiday_name, rooms in content.items():
                    st.markdown(f"**{holiday_name}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            # FIX: Explicitly cast pts to int for comparison to avoid loop if pts is a string
                            current_pts_int = int(pts) 
                            new_val = st.number_input(room, value=current_pts_int, step=50, key=f"hol_{current_resort}_{season}_{holiday_name}_{room}_{j}")
                            
                            if new_val != current_pts_int:
                                rooms[room] = int(new_val) # Store as int
                                save_data()
            else:
                day_types = ["Fri-Sat", "Sun", "Mon-Thu", "Sun-Thu"]
                available = [d for d in day_types if d in content]
                for day_type in available:
                    rooms = content[day_type]
                    st.write(f"**{day_type}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            step = 50 if "Holiday" in season else 25
                            # FIX: Explicitly cast pts to int for comparison
                            current_pts_int = int(pts)
                            new_val = st.number_input(room, value=current_pts_int, step=step, key=f"pts_{current_resort}_{season}_{day_type}_{room}_{j}")
                            
                            if new_val != current_pts_int:
                                rooms[room] = int(new_val) # Store as int
                                save_data()

    st.subheader("Reference Points")
    ref_points = data["reference_points"].setdefault(current_resort, {})
    for season, content in ref_points.items():
        with st.expander(season, expanded=True):
            day_types_present = [k for k in content.keys() if k in ["Mon-Thu", "Sun-Thu", "Fri-Sat", "Sun"]]
            is_holiday_season = not day_types_present and all(isinstance(v, dict) for v in content.values())
            
            if day_types_present:
                for day_type in day_types_present:
                    rooms = content[day_type]
                    st.write(f"**{day_type}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            # FIX: Explicitly cast pts to int for comparison
                            current_pts_int = int(pts)
                            new_val = st.number_input(room, value=current_pts_int, step=25, key=f"ref_{current_resort}_{season}_{day_type}_{room}_{j}")
                            
                            if new_val != current_pts_int:
                                rooms[room] = int(new_val) # Store as int
                                save_data()
            elif is_holiday_season:
                for sub_season, rooms in content.items():
                    st.markdown(f"**{sub_season}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            # FIX: Explicitly cast pts to int for comparison
                            current_pts_int = int(pts)
                            new_val = st.number_input(room, value=current_pts_int, step=25, key=f"refhol_{current_resort}_{season}_{sub_season}_{room}_{j}")
                            
                            if new_val != current_pts_int:
                                rooms[room] = int(new_val) # Store as int
                                save_data()

# === GLOBAL SETTINGS ===
st.header("Global Settings")
with st.expander("Maintenance Fees"):
    for i, (year, rate) in enumerate(data.get("maintenance_rates", {}).items()):
        # FIX: Explicitly cast rate to float for comparison
        current_rate_float = float(rate)
        new = st.number_input(year, value=current_rate_float, step=0.01, format="%.4f", key=f"mf_{i}")
        if new != current_rate_float:
            data["maintenance_rates"][year] = float(new) # Store as float
            save_data()

with st.expander("Holiday Dates"):
    for year in ["2025", "2026"]:
        st.write(f"**{year}**")
        holidays = data["global_dates"].get(year, {})
        
        # Display existing holidays and allow editing
        for i, (name, val) in enumerate(holidays.items()):
            val_list = val if isinstance(val, list) else [None, None]
            s_raw, e_raw = val_list[0], val_list[1]
            
            st.markdown(f"*{name}*")
            c1, c2, c3 = st.columns([4, 4, 1])
            with c1:
                ns = st.date_input(f"Start", safe_date(s_raw), key=f"hs_{year}_{i}", label_visibility="collapsed")
            with c2:
                ne = st.date_input(f"End", safe_date(e_raw), key=f"he_{year}_{i}", label_visibility="collapsed")
            with c3:
                 if st.button("🗑️", key=f"del_h_{year}_{i}"):
                     del holidays[name]
                     save_data()
                     st.rerun()
            
            # Helper to get the ISO string from the data, or the default ISO string if None
            stored_s_iso = s_raw if s_raw else safe_date(s_raw).isoformat()
            stored_e_iso = e_raw if e_raw else safe_date(e_raw).isoformat()

            # FIX: Robust comparison against the stored string value
            if ns.isoformat() != stored_s_iso or ne.isoformat() != stored_e_iso:
                data["global_dates"][year][name] = [ns.isoformat(), ne.isoformat()]
                save_data()

        # Add new holiday
        st.markdown("---")
        new_name = st.text_input(f"New Holiday Name ({year})", key=f"nhn_{year}")
        c1, c2, c3 = st.columns([4, 4, 1])
        with c1:
             new_start = st.date_input("New Start Date", datetime.strptime(f"{year}-01-01", "%Y-%m-%d").date(), key=f"nhs_{year}")
        with c2:
             new_end = st.date_input("New End Date", datetime.strptime(f"{year}-01-07", "%Y-%m-%d").date(), key=f"nhe_{year}")
        with c3:
             if st.button("Add Holiday", key=f"add_h_{year}") and new_name and new_name not in holidays:
                 data["global_dates"][year][new_name] = [new_start.isoformat(), new_end.isoformat()]
                 save_data()
                 st.rerun()


st.markdown("""
<div class='success-box'>
    SINGAPORE 9:08 PM +08 • FINAL CODE • SEASON REORDER REMOVED FOR STABILITY
</div>
""", unsafe_allow_html=True)
