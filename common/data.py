import json
import streamlit as st
from datetime import datetime

DEFAULT_DATA_PATH = "data_v2.json"

def ensure_data_in_session():
    """Auto-load data if missing."""
    if "data" not in st.session_state or st.session_state.data is None:
        try:
            with open(DEFAULT_DATA_PATH, "r") as f:
                st.session_state.data = json.load(f)
        except FileNotFoundError:
            st.session_state.data = None

def save_data(data: dict):
    """Save to disk (local only) and update state timestamp."""
    try:
        with open(DEFAULT_DATA_PATH, "w") as f:
            json.dump(data, f, indent=2)
        st.session_state.last_save_time = datetime.now()
    except Exception:
        pass # Handle permission errors on cloud simply
