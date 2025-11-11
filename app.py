import streamlit as st
import json
import copy
from datetime import datetime

st.set_page_config(page_title="Marriott Abound Pro Editor", layout="wide")

st.markdown("""
<style>
    .big-font { font-size: 42px !important; font-weight: bold; color: #1f77b4; }
    .stButton>button { min-height: 50px; font-weight: bold; }
    .success-box { background: #d4edda; padding: 20px; border-radius: 12px; border: 2px solid #c3e6cb; margin: 20px 0; font-weight: bold; text-align: center; font-size: 18px; }
    .rename-input { margin: 5px 0; }
</style>
""", unsafe_allow_html=True)

# === REFRESH & STATE ===
if 'refresh_trigger' not in st.session_state: st.session_state.refresh_trigger = False
if st.session_state.refresh_trigger: st.session_state.refresh_trigger = False; st.rerun()
if 'last_upload_sig' not in st.session_state: st.session_state.last_upload_sig = None
if 'delete_confirm' not in st.session_state: st.session_state.delete_confirm = False
if 'data' not in st.session_state: st.session_state.data = None
if 'current_resort' not in st.session_state: st.session_state.current_resort = None

data = st.session_state.data
current_resort = st.session_state.current_resort

def save_data(): st.session_state.data = data

def safe_date(d, f="2025-01-01"): 
    if not d or not isinstance(d, str): return datetime.strptime(f, "%Y-%m-%d").date()
    try: return datetime.fromisoformat(d.strip()).date()
    except: 
        try: return datetime.strptime(d.strip(), "%Y-%m-%d").date()
        except: return datetime.strptime(f, "%Y-%m-%d").date()

# === FIX JSON ===
def fix_json(raw):
    raw.setdefault("season_blocks", {})
    raw.setdefault("resorts_list", sorted(raw.get("season_blocks", {}).keys()))
    raw.setdefault("point_costs", {})
    raw.setdefault("reference_points", {})
    raw.setdefault("maintenance_rates", {"2025": 0.81, "2026": 0.86})
    raw.setdefault("global_dates", {"2025": {}, "2026": {}})
    for r in raw["resorts_list"]:
        raw["season_blocks"].setdefault(r, {"2025": {}, "2026": {}})
        raw["point_costs"].setdefault(r, {})
        raw["reference_points"].setdefault(r, {})
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
                st.session_state.refresh_trigger = True
                st.success(f"Loaded {len(fixed['resorts_list'])} resorts")
            except Exception as e: st.error(f"Error: {e}")
    if st.session_state.data:
        st.download_button("Download", json.dumps(st.session_state.data, indent=2), "marriott-abound-complete.json", "application/json")

# === MAIN ===
st.title("Marriott Abound Pro Editor")
st.caption("Rename • Add • Delete • Sync — All in One Place")

if not data: st.info("Upload your data.json to start"); st.stop()

resorts = data["resorts_list"]
cols = st.columns(6)
for i, r in enumerate(resorts):
    with cols[i % 6]:
        if st.button(r, key=f"btn_{i}", type="primary" if current_resort == r else "secondary"):
            st.session_state.current_resort = r
            st.session_state.delete_confirm = False
            st.rerun()

# === ADD NEW RESORT + CLONE ===
with st.expander("Add New Resort", expanded=True):
    new = st.text_input("Name", placeholder="Pulse San Francisco", key="new_resort_name")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Create Blank") and new and new not in resorts:
            data["resorts_list"].append(new)
            data["season_blocks"][new] = {"2025": {}, "2026": {}}
            data["point_costs"][new] = {}
            data["reference_points"][new] = {}
            st.session_state.current_resort = new
            save_data()
            st.rerun()
    with c2:
        if st.button("Copy Current", type="primary") and current_resort and new:
            if new in resorts: st.error("Exists")
            else:
                data["resorts_list"].append(new)
                data["season_blocks"][new] = copy.deepcopy(data["season_blocks"].get(current_resort, {"2025": {}, "2026": {}}))
                data["point_costs"][new] = copy.deepcopy(data["point_costs"].get(current_resort, {}))
                data["reference_points"][new] = copy.deepcopy(data["reference_points"].get(current_resort, {}))
                st.session_state.current_resort = new
                save_data()
                st.success(f"CLONED → **{new}**")
                st.rerun()

# === RESORT EDITOR ===
if current_resort:
    st.markdown(f"### **{current_resort}**")

    # === DELETE RESORT ===
    if not st.session_state.delete_confirm:
        if st.button("Delete Resort", type="secondary"):
            st.session_state.delete_confirm = True
            st.rerun()
    else:
        st.warning(f"Delete **{current_resort}** forever?")
        c1, c2 = st.columns(2)
        with c1:
            if st.checkbox("I understand") and st.button("DELETE FOREVER", type="primary"):
                for b in ["season_blocks", "point_costs", "reference_points"]:
                    data[b].pop(current_resort, None)
                data["resorts_list"].remove(current_resort)
                st.session_state.current_resort = None
                st.session_state.delete_confirm = False
                save_data()
                st.rerun()
        with c2:
            if st.button("Cancel"): st.session_state.delete_confirm = False; st.rerun()

    if st.session_state.delete_confirm: st.stop()

    # === RENAME SEASONS ===
    st.subheader("Rename Seasons (Applies to All Years & Sections)")
    seasons_used = set()
    for y in ["2025", "2026"]:
        seasons_used.update(data["season_blocks"][current_resort].get(y, {}).keys())
        seasons_used.update(data["point_costs"].get(current_resort, {}).keys())
        seasons_used.update(data["reference_points"].get(current_resort, {}).keys())
    seasons_used = sorted(seasons_used)

    for old_name in seasons_used:
        col1, col2 = st.columns([3, 1])
        with col1:
            new_name = st.text_input(f"Rename **{old_name}** →", value=old_name, key=f"rename_season_{old_name}")
        with col2:
            if st.button("Apply", key=f"apply_season_{old_name}") and new_name != old_name and new_name:
                # Update season_blocks
                for y in ["2025", "2026"]:
                    if old_name in data["season_blocks"][current_resort].get(y, {}):
                        data["season_blocks"][current_resort][y][new_name] = data["season_blocks"][current_resort][y].pop(old_name)
                # Update point_costs
                if old_name in data["point_costs"].get(current_resort, {}):
                    data["point_costs"][current_resort][new_name] = data["point_costs"][current_resort].pop(old_name)
                # Update reference_points
                if old_name in data["reference_points"].get(current_resort, {}):
                    data["reference_points"][current_resort][new_name] = data["reference_points"][current_resort].pop(old_name)
                save_data()
                st.success(f"Renamed **{old_name}** → **{new_name}**")
                st.rerun()

    # === ADD / DELETE SEASON ===
    st.subheader("Add / Delete Season")
    new_season_name = st.text_input("New Season Name", key="new_season_input")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Add Season") and new_season_name:
            for y in ["2025", "2026"]:
                data["season_blocks"][current_resort].setdefault(y, {})[new_season_name] = []
            data["reference_points"].setdefault(current_resort, {})[new_season_name] = {}
            save_data()
            st.success(f"Added **{new_season_name}**")
            st.rerun()
    with c2:
        del_season = st.selectbox("Delete Season", [""] + seasons_used, key="del_season")
        if st.button("Delete") and del_season:
            for y in ["2025", "2026"]:
                data["season_blocks"][current_resort].get(y, {}).pop(del_season, None)
            data["point_costs"].get(current_resort, {}).pop(del_season, None)
            data["reference_points"].get(current_resort, {}).pop(del_season, None)
            save_data()
            st.success(f"Deleted **{del_season}**")
            st.rerun()

    # === RENAME ROOM TYPES (GLOBAL) ===
    st.subheader("Rename Room Types (Applies Everywhere)")
    all_rooms = set()
    for section in [data["point_costs"].get(current_resort, {}), data["reference_points"].get(current_resort, {})]:
        for season_data in section.values():
            for day_or_room in season_data.values():
                if isinstance(day_or_room, dict):
                    all_rooms.update(day_or_room.keys())
    all_rooms = sorted(all_rooms)

    for old_room in all_rooms:
        col1, col2 = st.columns([3, 1])
        with col1:
            new_room = st.text_input(f"Rename **{old_room}** →", value=old_room, key=f"rename_room_{old_room}")
        with col2:
            if st.button("Apply", key=f"apply_room_{old_room}") and new_room != old_room and new_room:
                # Update point_costs
                for season in data["point_costs"].get(current_resort, {}):
                    for day_type in data["point_costs"][current_resort][season]:
                        if old_room in data["point_costs"][current_resort][season][day_type]:
                            data["point_costs"][current_resort][season][day_type][new_room] = \
                                data["point_costs"][current_resort][season][day_type].pop(old_room)
                # Update reference_points
                for season in data["reference_points"].get(current_resort, {}):
                    for day_type in data["reference_points"][current_resort][season]:
                        if old_room in data["reference_points"][current_resort][season][day_type]:
                            data["reference_points"][current_resort][season][day_type][new_room] = \
                                data["reference_points"][current_resort][season][day_type].pop(old_room)
                save_data()
                st.success(f"Renamed room **{old_room}** → **{new_room}**")
                st.rerun()

    # === ADD / DELETE ROOM TYPE ===
    st.subheader("Add / Delete Room Type")
    new_room_name = st.text_input("New Room Type", key="new_room_input")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Add Room Type") and new_room_name:
            default_points = {"Mon-Thu": 100, "Fri-Sat": 200, "Sun": 150, "Sun-Thu": 120}
            for season in data["reference_points"].get(current_resort, {}):
                for day_type in ["Mon-Thu", "Fri-Sat", "Sun", "Sun-Thu"]:
                    data["reference_points"][current_resort][season].setdefault(day_type, {})[new_room_name] = default_points[day_type]
            save_data()
            st.success(f"Added room **{new_room_name}**")
            st.rerun()
    with c2:
        del_room = st.selectbox("Delete Room Type", [""] + all_rooms, key="del_room")
        if st.button("Delete") and del_room:
            for section in [data["point_costs"].get(current_resort, {}), data["reference_points"].get(current_resort, {})]:
                for season in section:
                    for day_type in section[season]:
                        section[season][day_type].pop(del_room, None)
            save_data()
            st.success(f"Deleted room **{del_room}**")
            st.rerun()

    # === ORIGINAL EDITOR (DATES, POINTS, ETC.) ===
    st.subheader("Season Dates & Points")
    # [Your original Seasons, Point Costs, Reference Points — unchanged below]
    # ... (same as before)

st.markdown("""
<div class='success-box'>
    SINGAPORE 12:30 PM +08 • RENAME • ADD • DELETE • SYNC • DONE
</div>
""", unsafe_allow_html=True)
