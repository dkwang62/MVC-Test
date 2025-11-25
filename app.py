# launcher.py
import streamlit as st
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
