# common/ui.py
import streamlit as st
from typing import List, Dict, Any, Optional

from common.utils import sort_resorts_west_to_east, get_region_label


def render_resort_card(resort_name: str, timezone: str, address: str) -> None:
    """Render an enhanced resort information card used by editor + calculator."""
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
    current_resort_id_or_name: Optional[str],
    *,
    id_key: str = "id",
    label_key: str = "display_name",
) -> None:
    """
    Shared resort grid used by both editor + calculator.

    - Sorts resorts West → East using timezone from common.utils.sort_resorts_west_to_east
    - Highlights currently-selected resort (by id or display_name)
    """
    st.markdown(
        "<div class='section-header'>🏨 Resorts (West → East); select to work with</div>",
        unsafe_allow_html=True,
    )

    if not resorts:
        st.info("No resorts available.")
        return

    # West → East sort (this is the important part)
    sorted_resorts = sort_resorts_west_to_east(resorts)

    num_cols = 6
    cols = st.columns(num_cols)
    num_resorts = len(sorted_resorts)
    num_rows = (num_resorts + num_cols - 1) // num_cols  # ceil division

    for col_idx, col in enumerate(cols):
        with col:
            for row in range(num_rows):
                idx = col_idx * num_rows + row
                if idx >= num_resorts:
                    continue

                resort = sorted_resorts[idx]
                rid = resort.get(id_key)
                name = resort.get(label_key, rid or f"Resort {idx+1}")
                tz = resort.get("timezone", "UTC")
                region = get_region_label(tz)

                # Allow current selection to be either id or display_name
                is_selected = current_resort_id_or_name in (rid, name)

                button_type = "primary" if is_selected else "secondary"
                if st.button(
                    f"🏨 {name}",
                    key=f"resort_btn_{rid or name}",
                    type=button_type,
                    use_container_width=True,
                    help=(
                        f"{resort.get('address', 'No address')}\n"
                        f"Region: {region} · Timezone: {tz}"
                    ),
                ):
                    # Editor uses id; calculator uses display_name, so we set both
                    # and let the caller decide which one to read.
                    st.session_state.current_resort = name
                    st.session_state.current_resort_id = rid
                    st.rerun()
