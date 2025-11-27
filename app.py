# app.py
import os
import sys

import streamlit as st

import plotly.io as pio

if "ui_theme" not in st.session_state:
    st.session_state.ui_theme = "Auto"  # "Auto", "Light", "Dark"


# Ensure local package imports work on Streamlit Cloud
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from common.ui import setup_page

# Set up base page config and styling
setup_page()





# --- App shell: choose which tool to run ---

st.sidebar.markdown("### 🧰 MVC Tools")
choice = st.sidebar.radio(
    "Choose Tool",
    ["Points & Rent Calculator", "Resort Data Editor"],
    index=0,
)

if choice == "Points & Rent Calculator":
    import calculator

    calculator.run()
else:
    import editor

    editor.run()

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
