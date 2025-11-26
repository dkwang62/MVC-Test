from typing import Any, Dict, List, Optional

import streamlit as st

from common.utils import sort_resorts_west_to_east, get_region_label

# ----------------------------------------------------------------------
# PAGE CONFIG & GLOBAL STYLES
# ----------------------------------------------------------------------
def run():
    """Entry point used by app.py"""
    main()

def setup_page() -> None:
    """Standard page configuration and shared CSS for MVC apps."""
    st.set_page_config(
        page_title="MVC Tools",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "About": "Marriott Vacation Club – internal tools",
        },
    )

    # Shared CSS: cards, buttons, sidebar, typography etc.
    st.markdown(
        """
    <style>
        html, body, .main, [data-testid="stAppViewContainer"] {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                         'Helvetica Neue', Arial, sans-serif;
            color: var(--text-color);
        }
        :root {
            --primary-color: #008080;
            --secondary-color: #556B2F;
            --danger-color: #C0392B;
            --warning-color: #E67E22;
            --success-color: #27AE60;
            --text-color: #34495E;
            --bg-color: #F8F9FA;
            --card-bg: #FFFFFF;
            --border-color: #EAECEE;
        }
        .main {
            background-color: var(--bg-color);
        }
        .big-font {
            font-size: 32px !important;
            font-weight: 600;
            color: var(--text-color);
            border-bottom: 2px solid var(--primary-color);
            text-align: left;
            padding: 10px 0 15px 0;
            margin-bottom: 20px;
        }
        .card {
            background: var(--card-bg);
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
            margin-bottom: 20px;
            border: none;
            transition: all 0.2s ease;
        }
        .card:hover {
            box-shadow: 0 6px 15px rgba(0, 0, 0, 0.10);
            transform: translateY(-1px);
        }
        .stButton>button {
            border-radius: 6px;
            font-weight: 500;
            padding: 0.5rem 1.2rem;
            transition: all 0.2s ease;
            border: 1px solid var(--border-color);
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        .stButton>button:hover {
            transform: translateY(-1px);
            box-shadow: 0 3px 6px rgba(0,0,0,0.1);
        }
        .stButton [data-testid="baseButton-primary"] {
            background-color: #008080 !important;
            color: white !important;
            border: 1px solid #008080 !important;
        }
        .stButton [data-testid="baseButton-primary"]:hover {
            background-color: #006666 !important;
        }
        .section-header {
            font-size: 20px;
            font-weight: 600;
            color: var(--text-color);
            padding: 10px 0;
            border-bottom: 2px solid var(--border-color);
            margin-bottom: 20px;
        }
        section[data-testid="stSidebar"] {
            background-color: var(--card-bg);
            box-shadow: 2px 0 10px rgba(0,0,0,0.05);
            border-right: 1px solid var(--border-color);
        }
        section[data-testid="stSidebar"] * {
            color: var(--text-color) !important;
        }
        section[data-testid="stSidebar"] h2 {
            color: var(--primary-color) !important;
            font-weight: 700;
        }
        .success-box {
            background: #E8F8F5;
            color: var(--primary-color);
            padding: 16px;
            border-radius: 8px;
            margin: 20px 0;
            font-weight: 600;
            text-align: center;
            font-size: 15px;
            border: 1px solid #C0DEDD;
            box-shadow: none;
        }
    </style>
    """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------
# SHARED RESORT VISUAL COMPONENTS
# ----------------------------------------------------------------------


def render_resort_card(resort_name: str, timezone: str, address: str) -> None:
    """
    Render the standard resort information card (used by editor + calculator).
    """
    st.markdown(
        f"""
        <div style="
            background: var(--card-bg);
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
            margin-bottom: 20px;
            border-left: 4px solid var(--primary-color);
            transition: all 0.2s ease;
        ">
            <h2 style="margin:0; color: var(--primary-color); font-size: 28px; font-weight: 700;">
                🖖️ {resort_name}
            </h2>
            <p style="margin: 8px 0 0 0; color: #64748b; font-size: 16px;">
                🕒 Timezone: {timezone}
            </p>
            <p style="margin: 4px 0 0 0; color: #64748b; font-size: 14px;">
                📍 {address}
            </p>
        </div>
    """,
        unsafe_allow_html=True,
    )


def render_resort_grid(
    resorts: List[Dict[str, Any]],
    current_resort_key: Optional[str],
    *,
    title: str = "🏨 Resorts in Memory (West to East); Select a resort",
) -> None:
    """
    Shared resort grid, sorted West → East, laid out COLUMN-first.

    - `current_resort_key` can be either:
        * resort["id"]  (editor usage), or
        * resort["display_name"] (calculator usage).

    On click, this sets BOTH:
        - st.session_state.current_resort_id
        - st.session_state.current_resort

    So both apps can easily consume the selection.
    """
    st.markdown(
        f"<div class='section-header'>{title}</div>", unsafe_allow_html=True
    )

    if not resorts:
        st.info("No resorts available.")
        return

    sorted_resorts = sort_resorts_west_to_east(resorts)

    num_cols = 6
    cols = st.columns(num_cols)
    num_resorts = len(sorted_resorts)
    # COLUMN-FIRST layout, same as your editor:
    num_rows = (num_resorts + num_cols - 1) // num_cols  # ceil division

    for col_idx, col in enumerate(cols):
        with col:
            for row in range(num_rows):
                idx = col_idx * num_rows + row
                if idx >= num_resorts:
                    continue

                resort = sorted_resorts[idx]
                rid = resort.get("id")
                name = resort.get("display_name", rid or f"Resort {idx+1}")
                tz = resort.get("timezone", "UTC")
                region = get_region_label(tz)  # currently not shown, but available

                is_current = current_resort_key in (rid, name)

                button_type = "primary" if is_current else "secondary"

                if st.button(
                    f"🏨 {name}",
                    key=f"resort_btn_{rid or name}",
                    type=button_type,
                    use_container_width=True,
                    help=resort.get("address", "No address"),
                ):
                    # Normalise selection for BOTH apps
                    st.session_state.current_resort_id = rid
                    st.session_state.current_resort = name
                    if "delete_confirm" in st.session_state:
                        st.session_state.delete_confirm = False
                    st.rerun()

if __name__ == "__main__":
    run()
