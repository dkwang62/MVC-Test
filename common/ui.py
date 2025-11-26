# common/ui.py
from typing import List, Dict, Any, Optional
import streamlit as st

from common.utils import sort_resorts_west_to_east, get_region_label


def render_resort_card(resort_name: str, timezone: str, address: str) -> None:
    """Shared resort info card for editor + calculator."""
    st.markdown(
        f"""
        <div style="
            background: var(--card-bg, #ffffff);
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
            margin-bottom: 20px;
            border-left: 4px solid var(--primary-color, #008080);
            transition: all 0.2s ease;
        ">
            <h2 style="margin:0; color: var(--primary-color, #008080); font-size: 28px; font-weight: 700;">
                🖖️ {resort_name}
            </h2>
            <p style="margin: 8px 0 0 0; color: #64748b; font-size: 16px;">
                🕒 Timezone: {timezone}
            </p>
            <p style="margin: 4px 0 0 0; color: #64748b; font-size: 14px;">
                📍 {address}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_resort_grid(
    resorts: List[Dict[str, Any]],
    current_resort_id: Optional[str],
) -> None:
    """
    Shared resort grid used by both editor + calculator.

    - Sorts resorts West → East using timezone
    - Fills **by column** (top-to-bottom, then left-to-right) to match editor
    - Uses `current_resort_id` for highlighting
    - Sets both `st.session_state.current_resort_id` and `st.session_state.current_resort`
      when a button is clicked so both apps can read it.
    """
    st.markdown(
        "<div class='section-header'>🏨 Resorts in Memory (West to East); Select a resort</div>",
        unsafe_allow_html=True,
    )

    if not resorts:
        st.info("No resorts available. Create or load a file first.")
        return

    # IMPORTANT: shared sort West → East
    sorted_resorts = sort_resorts_west_to_east(resorts)

    num_cols = 6
    cols = st.columns(num_cols)
    num_resorts = len(sorted_resorts)
    num_rows = (num_resorts + num_cols - 1) // num_cols  # ceil division (same as editor)

    # COLUMN-MAJOR FILL (this is what you liked in the editor)
    for col_idx, col in enumerate(cols):
        with col:
            for row in range(num_rows):
                idx = col_idx * num_rows + row
                if idx >= num_resorts:
                    continue

                resort = sorted_resorts[idx]
                rid = resort.get("id")
                name = resort.get("display_name", rid or f"Resort {idx+1}")
                tz = resort.get("timezone", "UTC")
                region = get_region_label(tz)

                button_type = "primary" if current_resort_id == rid else "secondary"

                if st.button(
                    f"🏨 {name}",
                    key=f"resort_btn_{rid or name}",
                    type=button_type,
                    use_container_width=True,
                    help=f"{resort.get('address', 'No address')} · {region} · {tz}",
                ):
                    # Make both apps happy: store both id and name
                    st.session_state.current_resort_id = rid
                    st.session_state.current_resort = name
                    # Editor uses delete_confirm; safe to clear for both
                    if "delete_confirm" in st.session_state:
                        st.session_state.delete_confirm = False
                    st.rerun()
