import streamlit as st
import json
import pandas as pd
from copy import deepcopy

from common.ui import render_page_header, render_resort_selector, render_resort_card
from common.charts import render_gantt, get_season_bucket
from common.data import ensure_data_in_session, save_data

def sync_room_points(working: dict, base_year: str):
    years = working.get("years", {})
    if base_year not in years: return
    base_seasons = years[base_year].get("seasons", [])
    for y_str, y_data in years.items():
        if y_str == base_year: continue
        for s in y_data.get("seasons", []):
            base_match = next((bs for bs in base_seasons if bs["name"] == s["name"]), None)
            if base_match: s["day_categories"] = deepcopy(base_match["day_categories"])

def run():
    ensure_data_in_session()
    
    with st.sidebar:
        with st.expander("📂 Load Data File (data_v2.json)", expanded=True):
            uploaded = st.file_uploader("Upload Master Data", type="json", key="data_uploader")
            
            # --- ROBUST FILE LOADING ---
            if uploaded:
                file_sig = f"{uploaded.name}_{uploaded.size}"
                
                # Check if we need to read it (New file OR Data is missing)
                if st.session_state.get("last_loaded_data_sig") != file_sig or not st.session_state.data:
                    try:
                        uploaded.seek(0) # RESET POINTER
                        raw = json.load(uploaded)
                        if "resorts" in raw:
                            st.session_state.data = raw
                            st.session_state.last_loaded_data_sig = file_sig
                            st.success(f"✅ Loaded {len(raw['resorts'])} resorts")
                            st.rerun()
                        else: st.error("❌ Invalid Schema")
                    except Exception as e: st.error(f"Error: {e}")
                else:
                    # Already loaded, just show status
                    cnt = len(st.session_state.data.get('resorts', []))
                    st.success(f"Active: {uploaded.name} ({cnt} resorts)")

            if st.session_state.data:
                st.download_button("💾 Download Data", json.dumps(st.session_state.data, indent=2), "data_v2.json", "application/json")

    if not st.session_state.data:
        render_page_header("Editor", "Waiting for Data...", "📝", "#9CA3AF")
        st.info("Please upload your 'data_v2.json' file in the sidebar to begin.")
        return

    render_page_header("Editor", "Modify Master Data", "📝", "#EF4444")
    
    resorts = st.session_state.data.get("resorts", [])
    if not resorts: return

    if "current_resort_id" not in st.session_state:
        st.session_state.current_resort_id = resorts[0]["id"]
    
    render_resort_selector(resorts, st.session_state.current_resort_id)
    
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
            g_rows = []
            for s in y_data.get("seasons", []):
                for p in s.get("periods", []):
                    g_rows.append({"Task": s["name"], "Start": p["start"], "Finish": p["end"], "Type": get_season_bucket(s["name"])})
            st.plotly_chart(render_gantt(g_rows), use_container_width=True)

            seasons = y_data.get("seasons", [])
            for s in seasons:
                with st.expander(f"{s['name']}", expanded=False):
                    p_df = pd.DataFrame(s.get("periods", []))
                    if not p_df.empty:
                        edited_p = st.data_editor(p_df, num_rows="dynamic", key=f"p_{working['id']}_{sel_year}_{s['name']}", use_container_width=True)
                        s["periods"] = edited_p.to_dict("records")

    with t_pts:
        if sel_year:
            st.info("Edit points below. 'Save & Sync' will update other years.")
            y_data = working["years"][sel_year]
            seasons = y_data.get("seasons", [])
            
            for s_idx, season in enumerate(seasons):
                st.markdown(f"**{season['name']}**")
                day_cats = season.get("day_categories", {})
                for dc_key, dc_val in day_cats.items():
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
