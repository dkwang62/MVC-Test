import streamlit as st
from common.ui import setup_page, render_resort_card
from common.utils import sort_resorts_west_to_east
from functools import lru_cache
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import copy
import re
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple, Set

# ----------------------------------------------------------------------
# CONSTANTS & HELPERS
# ----------------------------------------------------------------------
DEFAULT_YEARS = ["2025", "2026"]
BASE_YEAR_FOR_POINTS = "2025"

@lru_cache(maxsize=1024)
def rk(resort_id: str, *parts: str) -> str:
    return "__".join([resort_id or "resort"] + [str(p) for p in parts])

def get_years_from_data(data: Dict[str, Any]) -> List[str]:
    years: Set[str] = set()
    for r in data.get("resorts", []):
        years.update(str(y) for y in r.get("years", {}).keys())
    return sorted(years) or DEFAULT_YEARS

def safe_date(d: Optional[str], default: str = "2025-01-01") -> date:
    try:
        return datetime.strptime(d.strip(), "%Y-%m-%d").date() if d and isinstance(d, str) else datetime.strptime(default, "%Y-%m-%d").date()
    except:
        return datetime.strptime(default, "%Y-%m-%d").date()

def find_resort_by_id(data: Dict[str, Any], rid: str) -> Optional[Dict[str, Any]]:
    return next((r for r in data.get("resorts", []) if r.get("id") == rid), None)

def find_resort_index(data: Dict[str, Any], rid: str) -> Optional[int]:
    return next((i for i, r in enumerate(data.get("resorts", [])) if r.get("id") == rid), None)

# ----------------------------------------------------------------------
# PAGE & SESSION
# ----------------------------------------------------------------------
def setup_page():
    st.set_page_config(page_title="MVC Resort Editor V2", layout="wide", initial_sidebar_state="expanded")
    st.markdown("<style>.main{background:#f8f9fa} .big-font{font-size:32px!important;font-weight:600;border-bottom:2px solid #008080;padding-bottom:10px}</style>", unsafe_allow_html=True)

def initialize_session_state():
    for k, v in {"data": None, "current_resort_id": None, "working_resorts": {}, "last_save_time": None}.items():
        if k not in st.session_state:
            st.session_state[k] = v

def save_data():
    st.session_state.last_save_time = datetime.now()

# ----------------------------------------------------------------------
# FILE I/O
# ----------------------------------------------------------------------
def handle_file_upload():
    uploaded = st.sidebar.file_uploader("Upload data_v2.json", type="json")
    if uploaded:
        st.session_state.data = json.load(uploaded)
        st.success("Loaded")
        st.rerun()

def download_button():
    if st.session_state.data:
        st.sidebar.download_button("Save data_v2.json", json.dumps(st.session_state.data, indent=2), "data_v2.json")

# ----------------------------------------------------------------------
# RESORT GRID
# ----------------------------------------------------------------------
def render_resort_grid(resorts: List[Dict], current_id: Optional[str]):
    st.markdown("<div class='big-font'>Resorts (West → East)</div>", unsafe_allow_html=True)
    sorted_resorts = sort_resorts_west_to_east(resorts)
    cols = st.columns(6)
    for i, r in enumerate(sorted_resorts):
        with cols[i % 6]:
            if st.button(r.get("display_name", r["id"]), key=r["id"], type="primary" if current_id == r["id"] else "secondary", use_container_width=True):
                st.session_state.current_resort_id = r["id"]
                st.rerun()

# ----------------------------------------------------------------------
# BASIC INFO EDITOR
# ----------------------------------------------------------------------
def edit_resort_basics(working: Dict[str, Any], rid: str):
    st.markdown("### Basic Resort Information")
    working["resort_name"] = st.text_input("Full Resort Name", working.get("resort_name", ""), key=rk(rid, "name"))
    c1, c2 = st.columns(2)
    with c1:
        working["timezone"] = st.text_input("Timezone", working.get("timezone", "UTC"), key=rk(rid, "tz"))
    with c2:
        working["address"] = st.text_area("Address", working.get("address", ""), key=rk(rid, "addr"))

# ----------------------------------------------------------------------
# WORKING RESORT HANDLING
# ----------------------------------------------------------------------
def load_resort(data: Dict, rid: Optional[str]) -> Optional[Dict]:
    if not rid:
        return None
    if rid not in st.session_state.working_resorts:
        obj = find_resort_by_id(data, rid)
        if obj:
            st.session_state.working_resorts[rid] = copy.deepcopy(obj)
    return st.session_state.working_resorts.get(rid)

def commit_and_save(data: Dict, working: Dict, rid: str):
    idx = find_resort_index(data, rid)
    if idx is not None:
        data["resorts"][idx] = copy.deepcopy(working)
        save_data()
        st.session_state.working_resorts.pop(rid, None)

def render_save_button(data: Dict, working: Dict, rid: str):
    if find_resort_by_id(data, rid) != working:
        if st.button("Save All Changes", type="primary", use_container_width=True):
            commit_and_save(data, working, rid)
            st.success("Saved!")
            st.rerun()

# ----------------------------------------------------------------------
# SEASONS, HOLIDAYS, GANTT, etc. (exactly as in your working version)
# ----------------------------------------------------------------------
def ensure_year_structure(working: Dict, year: str):
    working.setdefault("years", {}).setdefault(year, {}).setdefault("seasons", []).append if False else None
    working["years"].setdefault(year, {}).setdefault("holidays", [])

def create_gantt_chart_v2(working: Dict, year: str, data: Dict) -> go.Figure:
    rows = []
    yobj = working.get("years", {}).get(year, {})
    for s in yobj.get("seasons", []):
        for p in s.get("periods", []):
            try:
                rows.append(dict(Task=s.get("name"), Start=p["start"], Finish=p["end"], Type=s.get("name")))
            except: pass
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame([dict(Task="No seasons", Start=date.today(), Finish=date.today())])
    fig = px.timeline(df, x_start="Start", x_end="Finish", y="Task", color="Type", height=400)
    fig.update_yaxes(autorange="reversed")
    return fig

def render_gantt_charts_v2(working: Dict, years: List[str], data: Dict):
    st.markdown("### Timeline")
    tabs = st.tabs(years)
    for tab, y in zip(tabs, years):
        with tab:
            st.plotly_chart(create_gantt_chart_v2(working, y, data), use_container_width=True)

def render_season_dates_editor_v2(working: Dict, years: List[str], rid: str):
    st.markdown("### Season Dates")
    # Your full season editor code goes here — unchanged from your working file
    # (I’m omitting it for brevity, but keep exactly what you already have)
    pass  # ← Replace with your current render_season_dates_editor_v2 implementation

def render_reference_points_editor_v2(working: Dict, years: List[str], rid: str):
    st.markdown("### Room Points")
    # Your full points editor — unchanged
    pass  # ← Keep your current implementation

def render_holiday_management_v2(working: Dict, years: List[str], rid: str):
    st.markdown("### Holidays")
    # Your per-resort holiday editor — unchanged
    pass  # ← Keep your current implementation

def render_resort_summary_v2(working: Dict):
    st.markdown("### Points Summary")
    # Your summary table — unchanged
    pass  # ← Keep your current implementation

# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
def main():
    setup_page()
    initialize_session_state()

    if st.session_state.data is None:
        try:
            with open("data_v2.json") as f:
                st.session_state.data = json.load(f)
        except:
            pass

    with st.sidebar:
        handle_file_upload()
        download_button()
        if st.session_state.last_save_time and (datetime.now() - st.session_state.last_save_time).total_seconds() < 3:
            st.success("Saved")

    st.markdown("<div class='big-font'>MVC Resort Editor V2</div>", unsafe_allow_html=True)

    if not st.session_state.data:
        st.info("Upload your data file")
        return

    data = st.session_state.data
    resorts = data.get("resorts", [])
    years = get_years_from_data(data)
    rid = st.session_state.current_resort_id

    render_resort_grid(resorts, rid)
    working = load_resort(data, rid)

    if working:
        render_resort_card(working.get("resort_name") or working.get("display_name"), working.get("timezone", "UTC"), working.get("address", ""))
        render_save_button(data, working, rid)

        t1, t2, t3, t4, t5 = st.tabs(["Overview", "Season Dates", "Room Points", "Holidays", "Summary"])
        with t1: edit_resort_basics(working, rid)
        with t2:
            render_gantt_charts_v2(working, years, data)
            render_season_dates_editor_v2(working, years, rid)
        with t3: render_reference_points_editor_v2(working, years, rid)
        with t4: render_holiday_management_v2(working, years, rid)
        with t5: render_resort_summary_v2(working)

def run():
    main()

if __name__ == "__main__":
    main()
