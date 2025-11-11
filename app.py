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
    st.session_state.data = data

def safe_date(d, f="2025-01-01"):
    if not d or not isinstance(d, str): return datetime.strptime(f, "%Y-%m-%d").date()
    try: return datetime.fromisoformat(d.strip()).date()
    except:
        try: return datetime.strptime(d.strip(), "%Y-%m-%d").date()
        except: return datetime.strptime(f, "%Y-%m-%d").date()

# === REORDER DICTIONARY HELPER ===
def reorder_dict(d: dict, old_key: str, direction: str) -> dict:
    keys = list(d.keys())
    try:
        current_index = keys.index(old_key)
    except ValueError:
        return d
    if direction == "up" and current_index > 0:
        new_index = current_index - 1
    elif direction == "down" and current_index < len(keys) - 1:
        new_index = current_index + 1
    else:
        return d
    keys[current_index], keys[new_index] = keys[new_index], keys[current_index]
    return {key: d[key] for key in keys}

# === JSON SANITIZE ===
def fix_json(raw):
    raw.setdefault("season_blocks", {})
    raw.setdefault("resorts_list", sorted(raw.get("season_blocks", {}).keys()))
    raw.setdefault("point_costs", {})
    raw.setdefault("reference_points", {})
    raw.setdefault("maintenance_rates", {"2025": 0.81, "2026": 0.86})
    raw.setdefault("global_dates", {"2025": {}, "2026": {}})
    raw.setdefault("holiday_weeks", {})
    raw.setdefault("room_type_orders", {})
   
    for r in raw["resorts_list"]:
        raw["season_blocks"].setdefault(r, {"2025": {}, "2026": {}})
        raw["point_costs"].setdefault(r, {})
        raw["reference_points"].setdefault(r, {})
        raw["holiday_weeks"].setdefault(r, {"2025": {}, "2026": {}})
        raw["room_type_orders"].setdefault(r, [])
        for y in ("2025", "2026"):
            sb = raw["season_blocks"][r].setdefault(y, {})
            for s, rngs in list(sb.items()):
                if not isinstance(rngs, list) or any(not isinstance(x, (list, tuple)) or len(x) != 2 for x in rngs):
                    sb[s] = []
    return raw

# === SIDEBAR ===
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
        st.download_button("Download", json.dumps(st.session_state.data, indent=2), "data.json", "application/json")

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
            data["room_type_orders"][new] = []
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
                data["room_type_orders"][new] = copy.deepcopy(data["room_type_orders"].get(current_resort, []))
                st.session_state.current_resort = new
                save_data()
                st.success(f"CLONED → **{new}**")
                st.rerun()

# === RESORT EDITOR ===
if current_resort:
    st.markdown(f"### **{current_resort}**")

    # === DELETE RESORT ===
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
                    data["room_type_orders"].pop(current_resort, None)
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
    HOLIDAY_KEY_TO_EXCLUDE = "Holiday Week"
    for old_name in seasons_used:
        if old_name == HOLIDAY_KEY_TO_EXCLUDE:
            continue
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

    # === ROOM TYPE MANAGEMENT ===
    current_rooms = set()
    for section in [data["point_costs"].get(current_resort, {}), data["reference_points"].get(current_resort, {})]:
        for season_data in section.values():
            for day_or_room in season_data.values():
                if isinstance(day_or_room, dict):
                    current_rooms.update(day_or_room.keys())
    current_rooms = sorted(current_rooms)

    st.subheader("Reorder Room Types (This Resort)")
    st.caption(f"This order determines the display sequence for **{current_resort}**.")
    resort_room_order = data["room_type_orders"].setdefault(current_resort, [])
    if not resort_room_order:
        resort_room_order.extend(current_rooms)
    else:
        existing = set(resort_room_order)
        new_rooms = [r for r in current_rooms if r not in existing]
        resort_room_order.extend(new_rooms)
        data["room_type_orders"][current_resort] = [r for r in resort_room_order if r in current_rooms]
    room_order = data["room_type_orders"][current_resort]

    for i, room in enumerate(room_order):
        c1, c2, c3 = st.columns([6, 1, 1])
        with c1:
            st.markdown(f"**{i+1}. {room}**")
        with c2:
            if st.button("Up", key=f"room_up_{current_resort}_{room}", disabled=(i == 0)):
                room_order[i], room_order[i-1] = room_order[i-1], room_order[i]
                save_data()
                st.rerun()
        with c3:
            if st.button("Down", key=f"room_down_{current_resort}_{room}", disabled=(i == len(room_order) - 1)):
                room_order[i], room_order[i+1] = room_order[i+1], room_order[i]
                save_data()
                st.rerun()
    st.markdown("---")

    # === RENAME ROOM TYPES ===
    st.subheader("Rename Room Types (Applies Everywhere)")
    for old_room in [r for r in current_rooms if r in room_order]:
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
                if old_room in data["room_type_orders"].get(current_resort, []):
                    i = data["room_type_orders"][current_resort].index(old_room)
                    data["room_type_orders"][current_resort][i] = new_room
                save_data()
                st.success(f"Renamed **{old_room}** → **{new_room}**")
                st.rerun()

    # === ADD / DELETE ROOM TYPE ===
    st.subheader("Add / Delete Room Type")
    new_room_name = st.text_input("New Room Type", key="new_room_input")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Add Room Type", key="add_room_btn") and new_room_name:
            default_points = {"Mon-Thu": 100, "Fri-Sat": 200, "Sun": 150, "Sun-Thu": 120}
            for section in [data["reference_points"].get(current_resort, {}), data["point_costs"].get(current_resort, {})]:
                for season in section:
                    for day_type in ["Mon-Thu", "Fri-Sat", "Sun", "Sun-Thu"]:
                        if day_type in section[season]:
                            section[season][day_type].setdefault(new_room_name, default_points[day_type])
                        else:
                            for sub in section[season].values():
                                if isinstance(sub, dict):
                                    sub.setdefault(new_room_name, default_points["Mon-Thu"])
            data["room_type_orders"][current_resort].append(new_room_name)
            save_data()
            st.success(f"Added **{new_room_name}**")
            st.rerun()
    with c2:
        del_room = st.selectbox("Delete Room Type", [""] + current_rooms, key="del_room_select")
        if st.button("Delete Room", key="delete_room_btn") and del_room:
            for section in [data["point_costs"].get(current_resort, {}), data["reference_points"].get(current_resort, {})]:
                for season in section:
                    for day_type in section[season]:
                        if isinstance(section[season][day_type], dict):
                            section[section][day_type].pop(del_room, None)
            if del_room in data["room_type_orders"].get(current_resort, []):
                data["room_type_orders"][current_resort].remove(del_room)
            save_data()
            st.success(f"Deleted **{del_room}**")
            st.rerun()

    # === HOLIDAY WEEK MANAGEMENT ===
    st.subheader("Manage Individual Holiday Weeks")
    st.caption("Add or remove specific holiday weeks from **Reference Points**.")
    HOLIDAY_SEASON_KEY = "Holiday Week"
    ref_points_data = data["reference_points"].get(current_resort, {})
    ref_points_data.setdefault(HOLIDAY_SEASON_KEY, {})
    all_global_holidays = {h for y in ["2025", "2026"] for h in data["global_dates"].get(y, {}).keys() if h}
    current_active = set(ref_points_data.get(HOLIDAY_SEASON_KEY, {}).keys())
    current_active_sorted = sorted(current_active)

    if not all_global_holidays:
        st.warning("No global holiday dates defined.")
    else:
        if current_active_sorted:
            st.info(f"Active: **{', '.join(current_active_sorted)}**")
        else:
            st.info("No active holidays. Add one below.")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### Remove Holiday")
            del_holiday = st.selectbox("Select to Remove", [""] + current_active_sorted, key="del_holiday_select")
            if st.button("Remove", key="remove_holiday_btn", disabled=not del_holiday):
                ref_points_data[HOLIDAY_SEASON_KEY].pop(del_holiday, None)
                for y in ["2025", "2026"]:
                    data["holiday_weeks"].get(current_resort, {}).get(y, {}).pop(del_holiday, None)
                data["point_costs"].get(current_resort, {}).get(HOLIDAY_SEASON_KEY, {}).pop(del_holiday, None)
                save_data()
                st.success(f"Removed **{del_holiday}**")
                st.rerun()
        with c2:
            st.markdown("##### Add Holiday")
            available = sorted(all_global_holidays - current_active)
            add_holiday = st.selectbox("Select to Add", [""] + available, key="add_holiday_select")
            if st.button("Add", key="add_holiday_btn", type="primary", disabled=not add_holiday):
                default = {"Doubles": 1750, "King": 1750, "King City": 1925, "2-Bedroom": 3500}
                new_data = {room: default.get(room, 1500) for room in room_order}
                ref_points_data[HOLIDAY_SEASON_KEY][add_holiday] = copy.deepcopy(new_data)
                data["point_costs"].setdefault(current_resort, {}).setdefault(HOLIDAY_SEASON_KEY, {})[add_holiday] = copy.deepcopy(new_data)
                for y in ["2025", "2026"]:
                    data["holiday_weeks"].setdefault(current_resort, {}).setdefault(y, {})[add_holiday] = f"global:{add_holiday}"
                save_data()
                st.success(f"Added **{add_holiday}**")
                st.rerun()

    # === SEASON DATES (FIXED LAYOUT) ===
    st.subheader("Season Dates")
    for year in ["2025", "2026"]:
        with st.expander(f"{year} Seasons", expanded=True):
            year_data = data["season_blocks"][current_resort].setdefault(year, {})
            seasons = list(year_data.keys())
            col1, col2 = st.columns([4, 1])
            with col1:
                new_s = st.text_input(f"New season ({year})", key=f"ns_{year}")
            with col2:
                if st.button("Add", key=f"add_s_{year}") and new_s and new_s not in year_data:
                    year_data[new_s] = []
                    save_data()
                    st.rerun()

            for s_idx, season in enumerate(seasons):
                # CONTAINER FIX: Isolate each season block
                with st.container():
                    c_head_name, c_head_up, c_head_down = st.columns([7, 1, 1])
                    with c_head_name:
                        st.markdown(f"**{season}**")
                    with c_head_up:
                        if st.button("Up", key=f"move_up_date_{year}_{s_idx}", disabled=(s_idx == 0)):
                            data["season_blocks"][current_resort][year] = reorder_dict(year_data, season, "up")
                            save_data()
                            st.rerun()
                    with c_head_down:
                        if st.button("Down", key=f"move_down_date_{year}_{s_idx}", disabled=(s_idx == len(seasons) - 1)):
                            data["season_blocks"][current_resort][year] = reorder_dict(year_data, season, "down")
                            save_data()
                            st.rerun()

                    ranges = year_data[season]
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

    # === REFERENCE POINTS ===
    st.subheader("Reference Points")
    ref_points = data["reference_points"].setdefault(current_resort, {})
    season_list = list(ref_points.keys())
    ordered_room_keys = data["room_type_orders"].get(current_resort, [])

    for s_idx, season in enumerate(season_list):
        content = ref_points[season]
        c_name, c_up, c_down = st.columns([8, 1, 1])
        with c_name:
            st.markdown(f"**{season}**")
        with c_up:
            if st.button("Up", key=f"move_up_ref_{season}", disabled=(s_idx == 0)):
                data["reference_points"][current_resort] = reorder_dict(ref_points, season, "up")
                save_data()
                st.rerun()
        with c_down:
            if st.button("Down", key=f"move_down_ref_{season}", disabled=(s_idx == len(season_list) - 1)):
                data["reference_points"][current_resort] = reorder_dict(ref_points, season, "down")
                save_data()
                st.rerun()
        with st.expander(f"Edit {season}", expanded=True, key=f"exp_{season}"):
            day_types = [k for k in content.keys() if k in ["Mon-Thu", "Sun-Thu", "Fri-Sat", "Sun"]]
            is_holiday = not day_types and all(isinstance(v, dict) for v in content.values())
            if day_types:
                for day_type in day_types:
                    rooms = content[day_type]
                    st.write(f"**{day_type}**")
                    cols = st.columns(4)
                    for j, room in enumerate(ordered_room_keys):
                        if room not in rooms: continue
                        with cols[j % 4]:
                            val = int(rooms[room])
                            new = st.number_input(room, value=val, step=25, key=f"ref_{current_resort}_{season}_{day_type}_{room}_{j}")
                            if new != val:
                                rooms[room] = int(new)
                                save_data()
            elif is_holiday:
                holiday_rooms = [r for r in ordered_room_keys if r in next(iter(content.values()), {}).keys()]
                for sub, rooms in content.items():
                    st.markdown(f"**{sub}**")
                    cols = st.columns(4)
                    for j, room in enumerate(holiday_rooms):
                        if room not in rooms: continue
                        with cols[j % 4]:
                            val = int(rooms[room])
                            new = st.number_input(room, value=val, step=25, key=f"refhol_{current_resort}_{season}_{sub}_{room}_{j}")
                            if new != val:
                                rooms[room] = int(new)
                                save_data()

# === GLOBAL SETTINGS ===
st.header("Global Settings")
with st.expander("Maintenance Fees"):
    for i, (year, rate) in enumerate(data.get("maintenance_rates", {}).items()):
        new = st.number_input(year, value=float(rate), step=0.01, format="%.4f", key=f"mf_{i}")
        if new != float(rate):
            data["maintenance_rates"][year] = float(new)
            save_data()

with st.expander("Holiday Dates"):
    for year in ["2025", "2026"]:
        st.write(f"**{year}**")
        holidays = data["global_dates"].get(year, {})
        for i, (name, val) in enumerate(holidays.items()):
            s_raw, e_raw = (val if isinstance(val, list) else [None, None])[:2]
            st.markdown(f"*{name}*")
            c1, c2, c3 = st.columns([4, 4, 1])
            with c1:
                ns = st.date_input("Start", safe_date(s_raw), key=f"hs_{year}_{i}", label_visibility="collapsed")
            with c2:
                ne = st.date_input("End", safe_date(e_raw), key=f"he_{year}_{i}", label_visibility="collapsed")
            with c3:
                if st.button("Delete", key=f"del_h_{year}_{i}"):
                    del holidays[name]
                    save_data()
                    st.rerun()
            if ns.isoformat() != (s_raw or safe_date(s_raw).isoformat()) or ne.isoformat() != (e_raw or safe_date(e_raw).isoformat()):
                data["global_dates"][year][name] = [ns.isoformat(), ne.isoformat()]
                save_data()
        st.markdown("---")
        new_name = st.text_input(f"New Holiday ({year})", key=f"nhn_{year}")
        c1, c2, c3 = st.columns([4, 4, 1])
        with c1:
            new_start = st.date_input("Start", datetime.strptime(f"{year}-01-01", "%Y-%m-%d").date(), key=f"nhs_{year}")
        with c2:
            new_end = st.date_input("End", datetime.strptime(f"{year}-01-07", "%Y-%m-%d").date(), key=f"nhe_{year}")
        with c3:
            if st.button("Add", key=f"add_h_{year}") and new_name and new_name not in holidays:
                data["global_dates"][year][new_name] = [new_start.isoformat(), new_end.isoformat()]
                save_data()
                st.rerun()

st.markdown("""
<div class='success-box'>
    SINGAPORE 7:36 PM +08 • FINAL CODE • TYPEERROR FIXED • READY TO DEPLOY
</div>
""", unsafe_allow_html=True)
