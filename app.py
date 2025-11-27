# app.py
import os
import sys
import streamlit as st
import plotly.io as pio

# ============================================================
# Theme State Initialisation
# ============================================================

if "ui_theme" not in st.session_state:
    st.session_state.ui_theme = "Auto"  # "Auto", "Light", "Dark"


# ============================================================
# Theme Application Function
# ============================================================

def apply_app_theme():
    choice = st.session_state.ui_theme

    # AUTO → follow browser preference
    if choice == "Auto":
        css = """
        <style>
        @media (prefers-color-scheme: dark) {
            :root {
                --bg-color: #0f172a;
                --card-color: #1e293b;
                --text-color: #e5e7eb;
            }
        }
        @media (prefers-color-scheme: light) {
            :root {
                --bg-color: #ffffff;
                --card-color: #f5f5f5;
                --text-color: #111827;
            }
        }
        .stApp {
            background-color: var(--bg-color);
            color: var(--text-color);
        }
        </style>
        """
        pio.templates.default = "plotly"  # neutral template

    # DARK MODE
    elif choice == "Dark":
        css = """
        <style>
        :root {
            --bg-color: #0f172a;
            --card-color: #1e293b;
            --text-color: #e5e7eb;
        }
        .stApp {
            background-color: var(--bg-color);
            color: var(--text-color);
        }
        </style>
        """
        pio.templates.default = "plotly_dark"

    # LIGHT MODE
    else:
        css = """
        <style>
        :root {
            --bg-color: #ffffff;
            --card-color: #f5f5f5;
            --text-color: #111827;
        }
        .stApp {
            background-color: var(--bg-color);
            color: var(--text-color);
        }
        </style>
        """
        pio.templates.default = "plotly"

    st.markdown(css, unsafe_allow_html=True)


# ============================================================
# PATH FIX FOR STREAMLIT CLOUD
# ============================================================

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from common.ui import setup_page

# Page config
setup_page()

# Apply theme BEFORE loading calculator/editor
apply_app_theme()


# ============================================================
# Side Panel – Tool Selector + Theme Selector
# ============================================================

st.sidebar.markdown("### 🧰 MVC Tools")
choice = st.sidebar.radio(
    "Choose Tool",
    ["Points & Rent Calculator", "Resort Data Editor"],
    index=0,
)

with st.sidebar:
