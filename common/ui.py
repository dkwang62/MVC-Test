import streamlit as st

# Order definition for West -> East sorting
TZ_ORDER = {
    "Pacific/Honolulu": 0,
    "America/Anchorage": 1,
    "America/Los_Angeles": 2, "America/Tijuana": 2, "America/Vancouver": 2,
    "America/Phoenix": 3, "America/Denver": 4,
    "America/Costa_Rica": 5, "America/Chicago": 5, "America/Mexico_City": 5,
    "America/New_York": 6, "America/Toronto": 6, "America/Detroit": 6,
    "America/Bogota": 6, "America/Lima": 6,
    "America/Virgin": 7, "America/Aruba": 7, "America/Puerto_Rico": 7, "America/St_Kitts": 7,
    "Atlantic/Canary": 8,
    "Europe/London": 9, "UTC": 9,
    "Europe/Madrid": 10, "Europe/Paris": 10, "Europe/Rome": 10, "Europe/Berlin": 10,
    "Africa/Cairo": 11,
    "Asia/Dubai": 12,
    "Asia/Bangkok": 13,
    "Asia/Singapore": 14, "Asia/Hong_Kong": 14, "Asia/Shanghai": 14,
    "Asia/Tokyo": 15,
    "Australia/Perth": 16,
    "Australia/Brisbane": 17, "Australia/Sydney": 17,
    "Pacific/Fiji": 18
}

def get_resort_sort_key(resort):
    """Sorts by Timezone Index (West->East), then by Name."""
    tz = resort.get("timezone", "")
    # Default to 99 (end) if timezone unknown, otherwise use map
    tz_idx = TZ_ORDER.get(tz, 99) 
    return (tz_idx, resort.get("display_name", ""))

def render_page_header(title: str, sub: str, icon: str, badge_color: str):
    """Minimal header."""
    st.markdown(
        f"""
        <div style="padding-bottom: 10px; border-bottom: 1px solid #e5e7eb; margin-bottom: 15px;">
            <span style="font-size: 1.5rem;">{icon}</span> 
            <span style="font-size: 1.5rem; font-weight: 700; color: #111827;">{title}</span>
            <span style="background-color: {badge_color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; vertical-align: middle; margin-left: 8px;">{sub}</span>
        </div>
        """, 
        unsafe_allow_html=True
    )

def render_resort_selector(resorts: list, current_id: str):
    """
    Renders a West-to-East sorted dropdown with a helper label.
    """
    if not resorts:
        st.warning("No resorts loaded.")
        return

    # 1. SORT THE RESORTS
    sorted_resorts = sorted(resorts, key=get_resort_sort_key)

    # 2. Map IDs for the selectbox
    resort_map = {r['id']: r.get('display_name', r['id']) for r in sorted_resorts}
    resort_ids = list(resort_map.keys())
    
    # 3. Handle selection validation
    if current_id not in resort_ids:
        current_id = resort_ids[0]
        st.session_state.current_resort_id = current_id

    # Find index for the widget
    curr_index = resort_ids.index(current_id)

    # VISUAL CUE FOR SORTING
    st.caption("Select Resort (Ordered West ➡️ East)")

    selected_id = st.selectbox(
        "Select Resort",
        options=resort_ids,
        format_func=lambda x: resort_map[x],
        index=curr_index,
        label_visibility="collapsed"
    )

    if selected_id != current_id:
        st.session_state.current_resort_id = selected_id
        st.rerun()

def render_resort_card(name: str, timezone: str, address: str):
    """Minimal info card showing Address instead of Timezone."""
    st.markdown(f"**{name}**")
    if address:
        st.caption(f"🏠 {address}")
