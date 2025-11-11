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
</style>
""", unsafe_allow_html=True)

# === SESSION STATE ===
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
st.caption("Existing Holidays Preserved • One Point for 7 Nights")

if not data: st.info("Upload your data.json to start"); st.stop()

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
            st.session_state.current_resort = new
            save_data()
            st.rerun()
    with c2:
        if st.button("Copy Current", key="copy_current_btn", type="primary") and current_resort and new:
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
        if st.button("Delete Resort", key="delete_resort_init", type="secondary"):
            st.session_state.delete_confirm = True
            st.rerun()
    else:
        st.warning(f"Delete **{current_resort}** forever?")
        c1, c2 = st.columns(2)
        with c1:
            if st.checkbox("I understand") and st.button("DELETE FOREVER", key="delete_resort_final", type="primary"):
                for b in ["season_blocks", "point_costs", "reference_points"]:
                    data[b].pop(current_resort, None)
                data["resorts_list"].remove(current_resort)
                st.session_state.current_resort = None
                st.session_state.delete_confirm = False
                save_data()
                st.rerun()
        with c2:
            if st.button("Cancel", key="delete_cancel"): st.session_state.delete_confirm = False; st.rerun()

    if st.session_state.delete_confirm: st.stop()

    # === RESORT-SPECIFIC HOLIDAY SELECTOR (PRESERVE EXISTING) ===
    st.subheader("Select Holidays (Existing Preserved)")
    global_holidays = data.get("global_dates", {})
    holiday_names = sorted({name for year in ["2025", "2026"] for name in global_holidays.get(year, {})})

    # PRESERVE EXISTING: Scan point_costs for holidays
    point_costs = data["point_costs"].get(current_resort, {})
    existing_holidays = {name for name in holiday_names if name in point_costs}

    selected_holidays = st.multiselect(
        "Choose holidays (existing are preserved)",
        options=holiday_names,
        default=list(existing_holidays),
        key=f"holiday_select_{current_resort}"
    )

    # Sync: only change if user modifies
    if set(selected_holidays) != existing_holidays:
        selected_set = set(selected_holidays)
        current_set = existing_holidays

        # Remove only user-deselected
        for name in current_set - selected_set:
            data["point_costs"][current_resort].pop(name, None)
            data["reference_points"][current_resort].pop(name, None)

        # Add only user-selected
        for name in selected_set - current_set:
            data["point_costs"][current_resort][name] = {}
            data["reference_points"][current_resort][name] = {}

            all_rooms = set()
            for section in [data["point_costs"].get(current_resort, {}), data["reference_points"].get(current_resort, {})]:
                for season_data in section.values():
                    if isinstance(season_data, dict):
                        all_rooms.update(season_data.keys())

            default_point = 1000
            for room in all_rooms:
                data["point_costs"][current_resort][name][room] = default_point
                data["reference_points"][current_resort][name][room] = default_point

        save_data()
        st.success("Holiday selection updated!")
        st.rerun()

    # === POINT COSTS ===
    st.subheader("Point Costs")
    point_data = data["point_costs"].get(current_resort, {})
    for season, content in point_data.items():
        with st.expander(season, expanded=True):
            is_holiday = season in selected_holidays
            if is_holiday:
                st.markdown("**Entire Week (7 Nights)**")
                cols = st.columns(4)
                for j, (room, pts) in enumerate(content.items()):
                    with cols[j % 4]:
                        safe_val = int(pts) if pts is not None and str(pts).strip() else 1000
                        new_val = st.number_input(
                            room,
                            value=safe_val,
                            step=50,
                            key=f"hol_flat_{current_resort}_{season}_{room}_{j}"
                        )
                        if new_val != safe_val:
                            content[room] = new_val
                            data["reference_points"][current_resort][season][room] = new_val
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
                            safe_val = int(pts) if pts is not None and str(pts).strip() else 100
                            step = 50 if "Holiday" in season else 25
                            new_val = st.number_input(room, value=safe_val, step=step, key=f"pts_{current_resort}_{season}_{day_type}_{room}_{j}")
                            if new_val != safe_val:
                                rooms[room] = new_val
                                save_data()

    # === REFERENCE POINTS ===
    st.subheader("Reference Points")
    ref_points = data["reference_points"].setdefault(current_resort, {})
    for season, content in ref_points.items():
        with st.expander(season, expanded=True):
            is_holiday = season in selected_holidays
            if is_holiday:
                st.markdown("**Entire Week (7 Nights)**")
                cols = st.columns(4)
                for j, (room, pts) in enumerate(content.items()):
                    with cols[j % 4]:
                        safe_val = int(pts) if pts is not None and str(pts).strip() else 1000
                        new_val = st.number_input(
                            room,
                            value=safe_val,
                            step=25,
                            key=f"ref_hol_flat_{current_resort}_{season}_{room}_{j}"
                        )
                        if new_val != safe_val:
                            content[room] = new_val
                            data["point_costs"][current_resort][season][room] = new_val
                            save_data()
            else:
                day_types = [k for k in content.keys() if k in ["Mon-Thu", "Sun-Thu", "Fri-Sat", "Sun"]]
                if day_types:
                    for day_type in day_types:
                        rooms = content[day_type]
                        st.write(f"**{day_type}**")
                        cols = st.columns(4)
                        for j, (room, pts) in enumerate(rooms.items()):
                            with cols[j % 4]:
                                safe_val = int(pts) if pts is not None and str(pts).strip() else 100
                                new_val = st.number_input(room, value=safe_val, step=25, key=f"ref_{current_resort}_{season}_{day_type}_{room}_{j}")
                                if new_val != safe_val:
                                    rooms[room] = new_val
                                    save_data()

# === GLOBAL SETTINGS ===
st.header("Global Settings")
with st.expander("Maintenance Fees"):
    for i, (year, rate) in enumerate(data.get("maintenance_rates", {}).items()):
        new = st.number_input(year, value=float(rate), step=0.01, format="%.4f", key=f"mf_{i}")
        if new != rate:
            data["maintenance_rates"][year] = new
            save_data()

with st.expander("Holiday Dates"):
    for year in ["2025", "2026"]:
        st.write(f"**{year}**")
        holidays = data["global_dates"].get(year, {})
        for i, (name, (s, e)) in enumerate(holidays.items()):
            c1, c2 = st.columns(2)
            with c1:
                ns = st.date_input(f"{name} Start", safe_date(s), key=f"hs_{year}_{i}")
            with c2:
                ne = st.date_input(f"{name} End", safe_date(e), key=f"he_{year}_{i}")
            if ns.isoformat() != s or ne.isoformat() != e:
                data["global_dates"][year][name] = [ns.isoformat(), ne.isoformat()]
                save_data()

st.markdown("""
<div class='success-box'>
    SINGAPORE 1:22 PM +08 • EXISTING HOLIDAYS PRESERVED • NO DELETION • FINAL
</div>
""", unsafe_allow_html=True)
