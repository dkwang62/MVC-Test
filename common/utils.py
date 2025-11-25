# common/data.py
import json
import streamlit as st
from typing import Dict, Any, Optional
from datetime import datetime

def load_data() -> Dict[str, Any]:
    if "data" not in st.session_state or st.session_state.data is None:
        try:
            with open("data_v2.json", "r") as f:
                st.session_state.data = json.load(f)
                st.session_state.uploaded_file_name = "data_v2.json"
        except FileNotFoundError:
            st.session_state.data = None
    return st.session_state.data

def save_data(data: Dict[str, Any]):
    with open("data_v2.json", "w") as f:
        json.dump(data, f, indent=2)
    st.session_state.last_save_time = datetime.now()

def get_resorts(data: Dict[str, Any]) -> list:
    return data.get("resorts", []) if data else []

def get_resort_by_display_name(data: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    return next((r for r in get_resorts(data) if r.get("display_name") == name), None)

def get_maintenance_rate(data: Dict[str, Any], year: int) -> float:
    return float(data.get("configuration", {}).get("maintenance_rates", {}).get(str(year), 0.86))
