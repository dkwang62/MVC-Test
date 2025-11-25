# app.py
import streamlit as st
import os
import sys

# This line fixes everything on Streamlit Cloud (and locally)
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from common.ui import setup_page

setup_page()

st.markdown(
    "<h1 style='text-align:center; color:#008080; margin-bottom:30px;'>Marriott Vacation Club Tools</h1>",
    unsafe_allow_html=True,
)

choice = st.radio(
    "Select Tool",
    ["Points & Rent Calculator", "Resort Data Editor"],
    horizontal=True,
    label_visibility="collapsed",
    key="tool_selector"
)

if choice == "Points & Rent Calculator":
    import calculator
    calculator.run()
else:
    import editor
    editor.run()
