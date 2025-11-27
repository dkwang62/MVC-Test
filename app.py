import os
import sys
import streamlit as st
import plotly.io as pio

# ============================================
# Initialise Theme State
# ============================================
if "ui_theme" not in st.session_state:
    st.session_state.ui_theme = "Light"   # Auto, Light, Dark

# Fix Python path for Streamlit Cloud
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from common.ui import setup_page


# ============================================
# Cloud-Safe Theme System (CSS ONLY)
# ============================================
def apply_app_theme():
    theme = st.session_state.ui_theme

    # SAFE: no JavaScript injection, no DOM manipulation
    if theme == "Dark":
        css = """
        <style>
        body, .stApp {
            background-color: #0f172a !important;
            color: #e5e7eb !important;
        }
        </style>
        """
        pio.templates.default = "plotly_dark"

    elif theme == "Light":
        css = """
        <style>
        body, .stApp {
            background-color: #ffffff !important;
            color: #111827 !important;
        }
        </style>
        """
        pio.templates.default = "plotly"

    else:   # AUTO
        css = """
        <style>
        @media (prefers-color-scheme: dark) {
            body, .stApp {
                background-color: #0f172a !important;
                color: #e5e7eb !important;
            }
        }
        @media (prefers-color-scheme: light) {
            body, .stApp {
                background-color: #ffffff !important;
                color: #111827 !important;
            }
        }
        </style>
        """
        pio.templates.default = "plotly"

    st.markdown(css, unsafe_allow_html=True)


# ============================================
# Page Setup (must come BEFORE theme)
# ============================================
setup_page()

# Apply theme AFTER setup_page()
apply_app_theme()


# ============================================
# APPLICATION UI
# ============================================
st.sidebar.markdown("### 🧰 MVC Tools")

choice = st.sidebar.radio(
    "Choose Tool",
    ["Points & Rent Calculator", "Resort Data Editor"],
    index=0,
)

# Import tools AFTER selection to avoid preload failures
if choice == "Points & Rent Calculator":
    import calculator
    calculator.run()
else:
    import editor
    editor.run()


# ============================================
# SIDEBAR THEME SELECTOR
# ============================================
with st.sidebar:
    st.markdown("### 🎨 Display Theme")
    theme_choice = st.radio(
        "Colour scheme",
        ["Auto", "Light", "Dark"],
        index=["Auto", "Light", "Dark"].index(st.session_state.ui_theme),
        horizontal=True,
        help="Choose how the app colours should appear.",
    )

    st.session_state.ui_theme = theme_choice
