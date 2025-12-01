import streamlit as st
import json
import pandas as pd
from datetime import datetime
from copy import deepcopy

from common.ui import render_page_header, render_resort_selector, render_resort_card
from common.charts import render_gantt, get_season_bucket
from common.data import ensure_data_in_session, save_data

# --- HELPER LOGIC ---
def sync_room_points(working: dict, base_year: str):
    """Ensures rooms exist in all years and points are synced."""
    years = working.get("years", {})
    if base_year not in years: return

    base_rooms = set()
    base_seasons = years[base_year].get("seasons", [])
    for s in base_seasons:
        for cat in s.get("day_categories", {}).values():
            base_rooms.update(cat.get("room_points", {}).keys())

    for y_str, y_data in years.items():
        if y_str == base_year: continue
        for s in y_data.get("seasons", []):
            base_match = next((bs for bs in base_seasons if bs["name"] == s["name"]), None)
            if base_match:
                s["day_categories"] = deepcopy(base_match["day_categories"])

def validate_dates(working: dict, year: str):
    y_data = working["years"].get(year, {})
    covered = []
    for s in y_data.get("seasons", []):
        for p in s.get("periods", []):
            try: covered.append((p["start"], p["end"]))
            except: pass
    if not covered: return ["No dates defined."]
    return []

# --- MAIN EDITOR ---
def run():
    ensure_data_in_session()
    
    # --- SIDEBAR: FILE OPS ---
    with st.sidebar:
        with st.expander("📂 File Operations", expanded=True):
            uploaded = st.file_uploader("Load JSON", type="json")
            
            # --- FIX FOR INVALID FILE ERROR ---
            if uploaded:
                # Check if this specific file has already been loaded to prevent re-read loop
                file_id = f"{uploaded.name}_{uploaded.size}"
                if st.session_state.get("last_loaded_file") != file_id:
                    try:
                        # Reset pointer to start of file (Fixes the "Invalid File" bug)
                        uploaded.seek(0) 
                        data = json.load(uploaded)
                        st.session_state.data = data
                        st.session_state.last_loaded_file = file_id
                        st.success(f"Loaded {len(data['resorts'])} resorts")
                        st.rerun()
                    except Exception as e:
                        st.error("Invalid JSON file")
                else:
                    st.success(f"Loaded: {uploaded.name}")
            
            if st.session_state.data:
                st.download_button("💾 Download", json.dumps(st.session_state.data, indent=2), "mvc_data.json", "application/json")

    if not st.session_state.data:
        st.info("Upload data to begin.")
        return

    render_page_header("Editor", "Modify Data", "📝", "#EF4444")
    
    resorts = st.session_state.data.get("resorts", [])
    if not resorts: return

    if "current_resort_id" not in st.session_state:
        st.session_state.current_resort_id = resorts[0]["id"]
    
    render_resort_selector(resorts, st.session_state.current_resort_id)
    
    # Locate working copy
    r_idx = next((i for i, r in enumerate(resorts) if r["id"] == st.session_state.current_resort_id), 0)
    working = resorts[r_idx]
    
    render_resort_card(working.get("resort_name", ""), working.get("timezone", ""), "")

    t_ov, t_date, t_pts = st.tabs(["Overview", "Dates", "Points"])

    with t_ov:
        c1, c2 = st.columns(2)
        working["display_name"] = c1.text_input("Display Name", working.get("display_name", ""))
        working["code"] = c1.text_input("Code", working.get("code", ""))
        working["timezone"] = c2.text_input("Timezone", working.get("timezone", ""))
        working["address"] = st.text_area("Address", working.get("address", ""), height=70)
        
        if st.button("Save Overview"):
            save_data(st.session_state.data)
            st.toast("Saved!")

    with t_date:
        years = sorted(working.get("years", {}).keys())
        sel_year = st.selectbox("Year", years) if years else None
        
        if sel_year:
            y_data = working["years"][sel_year]
            
            # Gantt
            g_rows = []
            for s in y_data.get("seasons", []):
                for p in s.get("periods", []):
                    g_rows.append({"Task": s["name"], "Start": p["start"], "Finish": p["end"], "Type": get_season_bucket(s["name"])})
            st.plotly_chart(render_gantt(g_rows), use_container_width=True)

            # Warnings
            issues = validate_dates(working, sel_year)
            if issues: st.warning(f"Issues: {', '.join(issues)}")

            # Season Editor
            seasons = y_data.get("seasons", [])
            for s in seasons:
                with st.expander(f"{s['name']}", expanded=False):
                    p_df = pd.DataFrame(s.get("periods", []))
                    if not p_df.empty:
                        edited_p = st.data_editor(
                            p_df, num_rows="dynamic", 
                            key=f"p_{working['id']}_{sel_year}_{s['name']}",
                            use_container_width=True
                        )
                        s["periods"] = edited_p.to_dict("records")

    with t_pts:
        if sel_year:
            st.info("Edit points directly in the table below.")
            y_data = working["years"][sel_year]
            seasons = y_data.get("seasons", [])
            
            for s_idx, season in enumerate(seasons):
                st.markdown(f"**{season['name']}**")
                day_cats = season.get("day_categories", {})
                
                for dc_key, dc_val in day_cats.items():
                    days = ", ".join(dc_val.get("day_pattern", []))
                    st.caption(f"{dc_key} ({days})")
                    rp = dc_val.get("room_points", {})
                    pts_data = [{"Room Type": k, "Points": v} for k, v in rp.items()]
                    df_pts = pd.DataFrame(pts_data)
                    
                    edited_df = st.data_editor(
                        df_pts,
                        key=f"de_{working['id']}_{sel_year}_{s_idx}_{dc_key}",
                        use_container_width=True,
                        num_rows="dynamic",
                        hide_index=True
                    )
                    
                    if not edited_df.empty:
                        new_rp = dict(zip(edited_df["Room Type"], edited_df["Points"]))
                        dc_val["room_points"] = new_rp
            
            if st.button("Save & Sync Points"):
                sync_room_points(working, sel_year)
                save_data(st.session_state.data)
                st.toast("Points Saved & Synced!")
