# common/ui.py
import streamlit as st
from typing import List, Dict, Any

from common.utils import sort_resorts_west_to_east


def setup_page() -> None:
    """Configure Streamlit page and inject base CSS."""
    st.set_page_config(
        page_title="MVC Tools",
        page_icon="🖖",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
            .main {padding-top: 1rem;}
            .stButton>button {
                width: 100%;
                border-radius: 8px;
                font-weight: 500;
                transition: all 0.3s ease;
            }
            .stButton>button:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }
            div[data-testid="stMetricValue"] {
                font-size: 28px;
                font-weight: 600;
            }
            .section-header {
                font-size: 1.1rem;
                font-weight: 600;
                margin: 0.5rem 0 0.75rem 0;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_resort_card(resort_name: str, timezone: str, address: str) -> None:
    """Simple resort info card used by calculator/editor."""
    st.markdown(
        f"""
        <div style="
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
            margin-bottom: 20px;
            border-left: 4px solid #008080;
        ">
            <h2 style="margin:0; color: #008080; font-size: 24px; font-weight: 700;">
                🏨 {resort_name}
            </h2>
            <p style="margin: 8px 0 0 0; color: #64748b; font-size: 14px;">
                🕒 Timezone: {timezone}
            </p>
            <p style="margin: 4px 0 0 0; color: #64748b; font-size: 13px;">
                📍 {address}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_resort_grid(resorts: List[Dict[str, Any]], current_resort: str | None) -> None:
    """Show resorts in a 6-column grid sorted West→East."""
    st.markdown(
        "<div class='section-header'>🏨 Resort Selection (West to East)</div>",
        unsafe_allow_html=True,
    )
    if not resorts:
        st.info("No resorts loaded.")
        return

    sorted_resorts = sort_resorts_west_to_east(resorts)
    cols = st.columns(6)
    for i, r in enumerate(sorted_resorts):
        col = cols[i % 6]
        with col:
            name = (
                r.get("display_name")
                or r.get("resort_name")
                or r.get("id", "Unknown resort")
            )
            btn_type = "primary" if current_resort == name else "secondary"
            if st.button(
                f"🏨 {name}",
                key=f"resort_{r.get('id', '')}_{i}",
                type=btn_type,
                use_container_width=True,
                help=r.get("address", "No address available"),
            ):
                st.session_state.current_resort = name
                st.rerun()
