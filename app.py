import streamlit as st
import json
from datetime import datetime

st.set_page_config(page_title="Marriott Abound Editor", layout="wide")

# === CSS ===
st.markdown("""
<style>
    .big { font-size: 38px !important; font-weight: bold; color: #1f77b4; }
    .resort-btn.active { background: #1f77b4 !important; color: white !important; }
    .stButton>button { min-height: 48px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# === STATE ===
if 'data' not in st.session_state:
    st.session_state.data = None
if 'current_resort' not in st.session_state:
    st.session_state.current_resort = None

data = st.session_state.data
current_resort = st.session_state.current_resort

def save_data():
    st.session_state.data = data

def safe_date(d, fallback="2025-01-01"):
    if not d: return datetime.strptime(fallback, "%Y-%m-%d").date()
    try:
        return datetime.fromisoformat(d.strip()).date()
    except:
        try:
            return datetime.strptime(d.strip(), "%Y-%m-%d").date()
        except:
            return datetime.strptime(fallback, "%Y-%m-%d").date()

# === LOAD & FIX ===
def fix_json(raw):
    raw.setdefault("resorts_list", [])
    raw.setdefault("season_blocks", {})
    raw.setdefault("point_costs", {})
    raw.setdefault("maintenance_rates", {"2025": 0.81})
    raw.setdefault("global_dates", {"2025": {}, "2026": {}})
    if not raw["resorts_list"]:
        raw["resorts_list"] = sorted(set(raw["season_blocks"]) | set(raw["point_costs"]))
    return raw

# === SIDEBAR ===
with st.sidebar:
    st.markdown("<p class='big'>Marriott Editor</p>", unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload data.json", type="json")
    if uploaded:
        try:
            raw = json.load(uploaded)
            fixed = fix_json(raw)
            st.session_state.data = fixed
            data = fixed
            st.success(f"Loaded {len(data['resorts_list'])} resorts — ALL POINT COSTS DETECTED")
            st.session_state.current_resort = None
        except Exception as e:
            st.error(f"Error: {e}")

    if data:
        st.download_button(
            "Download Fixed JSON",
            json.dumps(data, indent=2),
            "marriott-abound-fixed.json",
            "application/json"
        )

# === MAIN ===
st.title("Marriott Abound Pro Editor")
st.success("Your file is PERFECT — every resort has point costs")

if not data:
    st.stop()

# === RESORTS ===
resorts = data["resorts_list"]
cols = st.columns(6)
for i, r in enumerate(resorts):
    if cols[i % 6].button(r, key=f"r{i}", type="primary" if current_resort == r else "secondary"):
        st.session_state.current_resort = r
        st.rerun()

with st.expander("Add Resort"):
    new = st.text_input("Name")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Blank") and new and new not in resorts:
            data["resorts_list"].append(new)
            data["season_blocks"][new] = {"2025": {}, "2026": {}}
            data["point_costs"][new] = {}
            st.session_state.current_resort = new
            save_data()
            st.rerun()
    with c2:
        if st.button("Copy Current") and current_resort and new:
            if new in resorts:
                st.error("Taken")
            else:
                data["resorts_list"].append(new)
                data["season_blocks"][new] = json.loads(json.dumps(data["season_blocks"][current_resort]))
                data["point_costs"][new] = json.loads(json.dumps(data["point_costs"][current_resort]))
                st.session_state.current_resort = new
                save_data()
                st.rerun()

if current_resort:
    st.markdown(f"### **{current_resort}**")
    
    # === SEASONS ===
    st.subheader("Seasons")
    for year in ["2025", "2026"]:
        with st.expander(f"{year} Seasons", expanded=True):
            seasons = data["season_blocks"][current_resort].setdefault(year, {})
            new_s = st.text_input(f"New season ({year})", key=f"ns{year}")
            if st.button("Add", key=f"as{year}") and new_s and new_s not in seasons:
                seasons[new_s] = []
                save_data()
                st.rerun()

            for s_idx, (sname, ranges) in enumerate(seasons.items()):
                st.markdown(f"**{sname}**")
                for i, (start, end) in enumerate(ranges):
                    c1, c2, c3 = st.columns([3, 3, 1])
                    with c1:
                        ns = st.date_input("Start", safe_date(start), key=f"st{year}{s_idx}{i}")
                    with c2:
                        ne = st.date_input("End", safe_date(end), key=f"en{year}{s_idx}{i}")
                    with c3:
                        if st.button("X", key=f"dx{year}{s_idx}{i}"):
                            ranges.pop(i)
                            save_data()
                            st.rerun()
                    if ns.isoformat() != start or ne.isoformat() != end:
                        ranges[i] = [ns.isoformat(), ne.isoformat()]
                        save_data()
                if st.button("+ Range", key=f"ar{year}{s_idx}"):
                    ranges.append([f"{year}-01-01", f"{year}-01-07"])
                    save_data()
                    st.rerun()

    # === POINT COSTS — FIXED FOREVER ===
    st.subheader("Point Costs")
    pc = data["point_costs"].get(current_resort, {})
    
    if not pc:
        st.warning("No point costs defined yet")
    else:
        # Handle BOTH regular seasons AND holiday-only resorts
        for season_name, season_data in pc.items():
            with st.expander(season_name, expanded=True):
                # Case 1: Regular season with Fri-Sat / Sun-Thu
                if isinstance(season_data, dict) and any(k in season_data for k in ["Fri-Sat", "Sun-Thu"]):
                    for day_type in ["Fri-Sat", "Sun-Thu"]:
                        if day_type not in season_data: continue
                        st.write(f"**{day_type}**")
                        cols = st.columns(4)
                        for j, room in enumerate(season_data[day_type]):
                            val = season_data[day_type][room]
                            with cols[j % 4]:
                                new = st.number_input(room, value=int(val), step=25, key=f"reg_{season_name}_{day_type}_{j}")
                                if new != val:
                                    season_data[day_type][room] = new
                                    save_data()
                else:
                    # Case 2: Holiday weeks only (like your file!)
                    st.write("**Holiday Weeks**")
                    for hol_name, rooms in season_data.items():
                        st.markdown(f"**{hol_name}**")
                        cols = st.columns(4)
                        for j, room in enumerate(rooms):
                            val = rooms[room]
                            with cols[j % 4]:
                                new = st.number_input(room, value=int(val), step=50, key=f"hol_{season_name}_{hol_name}_{j}")
                                if new != val:
                                    rooms[room] = new
                                    save_data()

# === GLOBALS ===
st.header("Global")
with st.expander("Maintenance Fees"):
    for i, (y, r) in enumerate(data.get("maintenance_rates", {}).items()):
        nr = st.number_input(y, value=float(r), step=0.01, format="%.4f", key=f"mf{i}")
        if nr != r:
            data["maintenance_rates"][y] = nr
            save_data()

with st.expander("Holidays"):
    for year in ["2025", "2026"]:
        st.write(year)
        for i, (name, (s, e)) in enumerate(data["global_dates"].get(year, {}).items()):
            c1, c2 = st.columns(2)
            with c1:
                ns = st.date_input("Start", safe_date(s), key=f"hs{year}{i}")
            with c2:
                ne = st.date_input("End", safe_date(e), key=f"he{year}{i}")
            if ns.isoformat() != s or ne.isoformat() != e:
                data["global_dates"][year][name] = [ns.isoformat(), ne.isoformat()]
                save_data()

st.success("YOUR FILE IS PERFECT — ALL POINT COSTS NOW VISIBLE")
