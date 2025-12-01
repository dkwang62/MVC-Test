import streamlit as st

def render_page_header(title: str, sub: str, icon: str, badge_color: str):
    """Minimal header optimized for mobile."""
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
    Mobile-friendly resort selector (Dropdown instead of Grid).
    """
    if not resorts:
        st.warning("No resorts loaded.")
        return

    # Create a map for the selectbox
    resort_map = {r['id']: r.get('display_name', r['id']) for r in resorts}
    resort_ids = list(resort_map.keys())
    
    # Find current index safely
    try:
        curr_index = resort_ids.index(current_id) if current_id in resort_ids else 0
    except ValueError:
        curr_index = 0

    selected_id = st.selectbox(
        "Select Resort",
        options=resort_ids,
        format_func=lambda x: resort_map[x],
        index=curr_index,
        label_visibility="collapsed" # Save space
    )

    if selected_id != current_id:
        st.session_state.current_resort_id = selected_id
        st.rerun()

def render_resort_card(name: str, timezone: str, address: str):
    """Minimal text info."""
    st.caption(f"📍 **{name}**")
    if timezone != "UTC":
        st.caption(f"🕒 {timezone}")
