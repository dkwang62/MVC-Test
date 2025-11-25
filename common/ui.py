# common/ui.py
import streamlit as st

def setup_page():
    st.set_page_config(
        page_title="MVC Tools",
        page_icon="handshake",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    st.markdown("""
    <style>
        .main {padding-top: 1rem;}
        .stButton>button {width: 100%; border-radius: 8px; font-weight: 500; transition: all 0.3s ease;}
        .stButton>button:hover {transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15);}
        div[data-testid="stMetricValue"] {font-size: 28px; font-weight: 600;}
        div[data-testid="metric-container"] {background-color: #f8f9fa; padding: 1rem; border-radius: 10px; border-left: 4px solid #0d6efd;}
        .section-header {font-size: 22px; font-weight: 700; color: #1e3a8a; border-bottom: 3px solid #008080; padding-bottom: 8px; margin: 30px 0 20px 0;}
        .card {background: white; border-radius: 12px; padding: 22px; box-shadow: 0 4px 15px rgba(0,0,0,0.07); border-left: 5px solid #008080; margin-bottom: 25px;}
        .card h2 {margin: 0; color: #008080;}
    </style>
    """, unsafe_allow_html=True)

def render_resort_card(resort_name: str, timezone: str, address: str):
    st.markdown(f"""
        <div class="card">
            <h2>handshake {resort_name}</h2>
            <p style="margin:6px 0 0 0; color:#64748b;">clock Timezone: {timezone}</p>
            <p style="margin:4px 0 0 0; color:#64748b;">location {address or "No address provided"}</p>
        </div>
    """, unsafe_allow_html=True)

def render_resort_grid(resorts: list, current_resort: str | None):
    from common.utils import sort_resorts_west_to_east
    st.markdown("<div class='section-header'>hotel Resort Selection (West to East)</div>", unsafe_allow_html=True)
    if not resorts:
        st.info("No resorts loaded.")
        return
    sorted_resorts = sort_resorts_west_to_east(resorts)
    cols = st.columns(6)
    for i, r in enumerate(sorted_resorts):
        with cols[i % 6]:
            name = r.get("display_name", r.get("id", "Unknown"))
            btn_type = "primary" if current_resort == name else "secondary"
            if st.button(f"hotel {name}", key=f"resort_{r.get('id','')}_{i}", type=btn_type, use_container_width=True):
                st.session_state.current_resort = name
                st.rerun()
