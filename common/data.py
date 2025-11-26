# common/data.py
import json
import streamlit as st
from typing import Dict, Any, Optional
from datetime import datetime

def ensure_data_in_session(
    default_filename: str = "data_v2.json",
    session_key: str = "data",
    uploaded_name_key: str = "uploaded_file_name",
) -> None:
    """
    Make sure st.session_state[session_key] has loaded JSON data.

    - If it's already set, do nothing.
    - Otherwise, try to auto-load default_filename from disk.
    """
    if session_key not in st.session_state:
        st.session_state[session_key] = None
    if uploaded_name_key not in st.session_state:
        st.session_state[uploaded_name_key] = None

    if st.session_state[session_key] is None:
        try:
            with open(default_filename, "r") as f:
                payload = json.load(f)
            # Minimal schema check
            if "resorts" in payload:
                st.session_state[session_key] = payload
                st.session_state[uploaded_name_key] = default_filename
        except Exception:
            # Silently ignore if default file not present
            pass


def render_data_file_uploader(
    label: str = "📁 Upload Resort Data",
    *,
    session_key: str = "data",
    uploaded_name_key: str = "uploaded_file_name",
    uploader_key: str = "data_uploader",
    help_text: str = "Upload your resort data JSON file (MVC schema).",
    require_schema: bool = True,
) -> None:
    """
    Standard JSON file uploader for MVC data.

    - Loads JSON into st.session_state[session_key]
    - Stores file name in st.session_state[uploaded_name_key]
    - Optional schema validation: require 'resorts' (and 'schema_version')
    """
    uploaded_file = st.file_uploader(
        label,
        type="json",
        help=help_text,
        key=uploader_key,
    )

    if not uploaded_file:
        return

    if uploaded_file.name == st.session_state.get(uploaded_name_key):
        # Same file name; allow user to re-upload but avoid redundant work
        # (If you want to force reload even with same name, remove this guard.)
        pass

    try:
        payload = json.load(uploaded_file)

        if require_schema:
            if "resorts" not in payload or "schema_version" not in payload:
                st.error("❌ Invalid file format (missing 'schema_version' or 'resorts').")
                return

        st.session_state[session_key] = payload
        st.session_state[uploaded_name_key] = uploaded_file.name
        st.success(f"✅ Loaded {uploaded_file.name}")
        st.rerun()

    except Exception as e:
        st.error(f"❌ Error loading JSON: {e}")

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
