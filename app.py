# app.py
import streamlit as st
import os
import sys

# Fix path for Streamlit Cloud
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from common.ui import setup_page

setup_page()

# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
# YOUR EXACT ORIGINAL TITLE + SIDEBAR SELECTOR
# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←

st.markdown(
    "<h1 style='text-align:center; color:#008080; margin-bottom:30px;'>Marriott Vacation Club Tools</h1>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Tool Selection")
    choice = st.radio(
        "Choose Tool",
        ["Points & Rent Calculator", "Resort Data Editor"],
        index=0,
        horizontal=False,
        label_visibility="collapsed"
    )

if choice == "Points & Rent Calculator":
    import calculator
    calculator.run()
else:
    import editor
    editor.run()
