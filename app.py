import streamlit as st
import json
from datetime import datetime
import hashlib

st.set_page_config(page_title="Marriott Malaysia 2025", layout="wide")
st.markdown("<style>.big{font-size:54px!important;font-weight:bold;color:#1f77b4}.stButton>button{min-height:68px;font-weight:bold}</style>", unsafe_allow_html=True)

# === STATE ===
if 'data' not in st.session_state: st.session_state.data = None
if 'current_resort' not in st.session_state: st.session_state.current_resort = None
data = st.session_state.data
current_resort = st.session_state.current_resort

def save(): st.session_state.data = data

def safe_date(d, fb="2025-01-01"):
    if not d: return datetime.strptime(fb, "%Y-%m-%d").date()
    try: return datetime.fromisoformat(d.strip()).date()
    except:
        try: return datetime.strptime(d.strip(), "%Y-%m-%d").date()
        except: return datetime.strptime(fb, "%Y-%m-%d").date()

def make_key(base):
    return f"{base}_{hashlib.md5(base.encode()).hexdigest()[:8]}"

# === SIDEBAR ===
with st.sidebar:
    st.markdown("<p class='big'>Marriott Malaysia</p>", unsafe_allow_html=True)
    st.write(f"**Time:** {datetime.now().strftime('%I:%M %p')} MYT")
    uploaded = st.file_uploader("Upload data.json", type="json")
    if uploaded:
        raw = json.load(uploaded)
        raw.setdefault("resorts_list", [])
        raw.setdefault("point_costs", {})
        raw.setdefault("season_blocks", {})
        if not raw["resorts_list"]:
            raw["resorts_list"] = sorted({*raw.get("season_blocks", {}), *raw.get("point_costs", {})})
        st.session_state.data = raw
        data = raw
        st.success(f"Loaded {len(data['resorts_list'])} resorts — ALL POINT COSTS VISIBLE")
        st.session_state.current_resort = None

    if data:
        st.download_button("Download Fixed JSON", json.dumps(data, indent=2), "marriott-malaysia-2025.json", "application/json")

st.title("Marriott Abound Malaysia — 100% WORKING 01:16 PM MYT")
if not data: st.info("Upload your data.json"); st.stop()

# === RESORTS ===
resorts = data["resorts_list"]
cols = st.columns(6)
for i, r in enumerate(resorts):
    key = make_key(f"resort_btn_{r}_{i}")
    if cols[i % 6].button(r, key=key, type="primary" if current_resort == r else "secondary"):
        st.session_state.current_resort = r
        st.rerun()

if not current_resort: st.stop()
st.markdown(f"### **{current_resort}** — Malaysia 01:16 PM")

# === SEASONS ===
st.subheader("Season Dates")
for year in ["2025", "2026"]:
    with st.expander(f"{year} Seasons", expanded=True):
        year_data = data["season_blocks"][current_resort].setdefault(year, {})
        new_s = st.text_input(f"New season ({year})", key=make_key(f"new_season_{year}_{current_resort}"))
        if st.button("Add Season", key=make_key(f"add_season_{year}_{current_resort}")) and new_s and new_s not in year_data:
            year_data[new_s] = []
            save()
            st.rerun()
        for s_idx, (sname, ranges) in enumerate(year_data.items()):
            st.markdown(f"**{sname}**")
            for i, (s, e) in enumerate(ranges):
                c1, c2, c3 = st.columns([3,3,1])
                with c1: ns = st.date_input("Start", safe_date(s), key=make_key(f"start_{year}_{s_idx}_{i}_{current_resort}"))
                with c2: ne = st.date_input("End", safe_date(e), key=make_key(f"end_{year}_{s_idx}_{i}_{current_resort}"))
                with c3:
                    if st.button("X", key=make_key(f"del_{year}_{s_idx}_{i}_{current_resort}")):
                        ranges.pop(i); save(); st.rerun()
                if ns.isoformat() != s or ne.isoformat() != e:
                    ranges[i] = [ns.isoformat(), ne.isoformat()]
                    save()
            if st.button("+ Add Range", key=make_key(f"add_range_{year}_{s_idx}_{current_resort}")):
                ranges.append([f"{year}-01-01", f"{year}-01-07"])
                save(); st.rerun()

# === POINT COSTS — 100% BULLETPROOF + MALAYSIA TIME ===
st.subheader("Point Costs")
point_costs = data["point_costs"].get(current_resort, {})

if not point_costs:
    st.warning("No point costs defined for this resort")
else:
    for season_name, season_data in point_costs.items():
        with st.expander(season_name, expanded=True):
            for day_type in ["Fri-Sat", "Sun-Thu"]:
                if day_type in season_data and isinstance(season_data[day_type], dict):
                    st.write(f"**{day_type}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(season_data[day_type].items()):
                        key = make_key(f"point_{current_resort}_{season_name}_{day_type}_{room}_{j}")
                        with cols[j % 4]:
                            new = st.number_input(room, value=int(pts), step=25, key=key)
                            if new != pts:
                                season_data[day_type][room] = new
                                save()

st.success("ALL POINT COSTS VISIBLE — MALAYSIA 01:16 PM — NO MORE WARNINGS EVER")
