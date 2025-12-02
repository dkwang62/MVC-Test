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

def get_all_room_types_for_resort(working: dict):
    rooms = set()
    for year_data in working.get("years", {}).values():
        for season in year_data.get("seasons", []):
            for cat in season.get("day_categories", {}).values():
                rooms.update(cat.get("room_points", {}).keys())
        for holiday in year_data.get("holidays", []):
            rooms.update(holiday.get("room_points", {}).keys())
    return sorted(rooms)

def render_points_summary(working: dict):
    years = sorted(working.get("years", {}).keys())
    resort_years = working.get("years", {})
    room_types = get_all_room_types_for_resort(working)
    rows = []

    # For seasons (use the most recent year with seasons)
    last_season_year = None
    for y in reversed(years):
        if resort_years.get(y, {}).get("seasons"):
            last_season_year = y
            break

    if last_season_year:
        seasons = resort_years[last_season_year].get("seasons", [])
        for season in seasons:
            weekly_totals = {}
            for cat in season.get("day_categories", {}).values():
                days_in_cat = len(cat.get("day_pattern", []))
                for room, points in cat.get("room_points", {}).items():
                    weekly_totals[room] = weekly_totals.get(room, 0) + days_in_cat * points
            row = {"Season": season["name"]}
            for room in room_types:
                total = weekly_totals.get(room)
                row[room] = (total if total else "—")
            rows.append(row)

    # For holidays (use the most recent year with holidays)
    last_holiday_year = None
    for y in reversed(years):
        if resort_years.get(y, {}).get("holidays"):
            last_holiday_year = y
            break

    if last_holiday_year:
        for h in resort_years[last_holiday_year].get("holidays", []):
            hname = h.get("name", "").strip() or "(Unnamed)"
            rp = h.get("room_points", {}) or {}
            row = {"Season": f"Holiday – {hname}"}
            for room in room_types:
                val = rp.get(room)
                row[room] = (val if isinstance(val, (int, float)) and val not in (0, None) else "—")
            rows.append(row)

    if rows:
        df = pd.DataFrame(rows, columns=["Season"] + room_types)
        st.caption(
            "Season rows show 7-night totals computed from nightly rates. "
            "Holiday rows show weekly totals directly from holiday points (no extra calculations)."
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("💡 No rate or holiday data available")

def run():
    ensure_data_in_session()
    
    # --- SIDEBAR: ONLY FILES ---
    with st.sidebar:
        with st.expander("📂 Load Data File (data_v2.json)", expanded=True):
            uploaded = st.file_uploader("Upload Master Data", type="json", key="data_uploader")
            if uploaded:
                file_sig = f"{uploaded.name}_{uploaded.size}"
                # Read only if new signature or data is missing
                if st.session_state.get("last_loaded_data_sig") != file_sig or not st.session_state.data:
                    try:
                        uploaded.seek(0)
                        raw = json.load(uploaded)
                        if "resorts" in raw:
                            st.session_state.data = raw
                            st.session_state.last_loaded_data_sig = file_sig
                            st.success(f"✅ Loaded {len(raw['resorts'])} resorts")
                            st.rerun()
                        else: st.error("❌ Invalid Schema")
                    except Exception as e: st.error(f"Error: {e}")
                else:
                    cnt = len(st.session_state.data.get('resorts', []))
                    st.success(f"Active: {uploaded.name} ({cnt} resorts)")

            if st.session_state.data:
                st.download_button("💾 Download Data", json.dumps(st.session_state.data, indent=2), "data_v2.json", "application/json")

    # --- MAIN CONTENT ---
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
    
    render_resort_card(working.get("resort_name", ""), working.get("timezone", ""), working.get("address", ""))

    years = sorted(working.get("years", {}).keys())

    t_ov, t_date, t_pts, t_hol, t_sum = st.tabs(["Overview", "Season Dates", "Room Points", "Holidays", "Points Summary"])

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
        sel_year = st.selectbox("Year", years, key="date_year_select") if years else None
        if sel_year:
            y_data = working["years"][sel_year]
            global_holidays = st.session_state.data.get("global_holidays", {})
            g_rows = []
            for s in y_data.get("seasons", []):
                for p in s.get("periods", []):
                    g_rows.append({"Task": s["name"], "Start": p["start"], "Finish": p["end"], "Type": get_season_bucket(s["name"])})
            
            # Add holidays
            for h in y_data.get("holidays", []):
                h_name = h.get("name", "(Unnamed Holiday)")
                global_ref = h.get("global_reference") or h_name
                gh_data = global_holidays.get(sel_year, {}).get(global_ref, {})
                start = gh_data.get("start_date")
                end = gh_data.get("end_date")
                if start and end:
                    g_rows.append({"Task": h_name, "Start": start, "Finish": end, "Type": "Holiday"})
            
            fig = render_gantt(g_rows)
            st.pyplot(fig, use_container_width=True)

            seasons = y_data.get("seasons", [])
            for s in seasons:
                with st.expander(f"{s['name']}", expanded=False):
                    p_df = pd.DataFrame(s.get("periods", []))
                    if not p_df.empty:
                        edited_p = st.data_editor(p_df, num_rows="dynamic", key=f"p_{working['id']}_{sel_year}_{s['name']}", use_container_width=True)
                        s["periods"] = edited_p.to_dict("records")

    with t_pts:
        sel_year = st.selectbox("Year", years, key="pts_year_select") if years else None
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
                    edited_df = st.data_editor(df_pts, key=f"de_{working['id']}_{sel_year}_{s_idx}_{dc_key}", use_container_width=True, num_rows="dynamic", hide_index=True)
                    if not edited_df.empty:
                        new_rp = dict(zip(edited_df["Room Type"], edited_df["Points"]))
                        dc_val["room_points"] = new_rp
            
            if st.button("Save & Sync Points"):
                sync_room_points(working, sel_year)
                save_data(st.session_state.data)
                st.toast("Points Saved & Synced!")

    with t_hol:
        sel_year = st.selectbox("Year", years, key="hol_year_select") if years else None
        if sel_year:
            y_data = working["years"][sel_year]
            holidays = y_data.get("holidays", [])
            for h_idx, h in enumerate(holidays):
                with st.expander(f"{h['name']}", expanded=False):
                    h["name"] = st.text_input("Name", h["name"], key=f"h_name_{working['id']}_{sel_year}_{h_idx}")
                    h["global_reference"] = st.text_input("Global Reference", h.get("global_reference", ""), key=f"h_ref_{working['id']}_{sel_year}_{h_idx}")
                    rp = h.get("room_points", {})
                    pts_data = [{"Room Type": k, "Points": v} for k, v in rp.items()]
                    df_pts = pd.DataFrame(pts_data)
                    edited_df = st.data_editor(df_pts, key=f"h_de_{working['id']}_{sel_year}_{h_idx}", use_container_width=True, num_rows="dynamic", hide_index=True)
                    if not edited_df.empty:
                        new_rp = dict(zip(edited_df["Room Type"], edited_df["Points"]))
                        h["room_points"] = new_rp
                    if st.button("Delete Holiday", key=f"h_del_{working['id']}_{sel_year}_{h_idx}"):
                        del holidays[h_idx]
                        save_data(st.session_state.data)
                        st.rerun()
            new_name = st.text_input("New Holiday Name", key=f"new_h_name_{working['id']}_{sel_year}")
            new_ref = st.text_input("Global Reference", key=f"new_h_ref_{working['id']}_{sel_year}")
            if st.button("Add Holiday") and new_name:
                holidays.append({"name": new_name, "global_reference": new_ref, "room_points": {}})
                save_data(st.session_state.data)
                st.rerun()

    with t_sum:
        render_points_summary(working)
