            for s_idx, season in enumerate(seasons):
                # === FULLY ISOLATED SEASON BLOCK ===
                season_container = st.container()
                with season_container:
                    # Header with reordering
                    header_cols = st.columns([7, 1, 1])
                    with header_cols[0]:
                        st.markdown(f"**{season}**")
                    with header_cols[1]:
                        if st.button("Up", key=f"up_date_{year}_{s_idx}", disabled=(s_idx == 0)):
                            data["season_blocks"][current_resort][year] = reorder_dict(year_data, season, "up")
                            save_data()
                            st.rerun()
                    with header_cols[2]:
                        if st.button("Down", key=f"down_date_{year}_{s_idx}", disabled=(s_idx == len(seasons) - 1)):
                            data["season_blocks"][current_resort][year] = reorder_dict(year_data, season, "down")
                            save_data()
                            st.rerun()

                # === EXPANDER OUTSIDE THE COLUMN CONTEXT ===
                ranges = year_data[season]
                with st.expander("Edit Date Ranges", expanded=True, key=f"range_exp_{year}_{s_idx}"):
                    for i, (s, e) in enumerate(ranges):
                        c1, c2, c3 = st.columns([3, 3, 1])
                        with c1:
                            ns = st.date_input("Start", safe_date(s), key=f"ds_{year}_{s_idx}_{i}")
                        with c2:
                            ne = st.date_input("End", safe_date(e), key=f"de_{year}_{s_idx}_{i}")
                        with c3:
                            if st.button("X", key=f"dx_{year}_{s_idx}_{i}"):
                                ranges.pop(i)
                                save_data()
                                st.rerun()

                        if ns.isoformat() != s or ne.isoformat() != e:
                            ranges[i] = [ns.isoformat(), ne.isoformat()]
                            save_data()

                    if st.button("+ Add Range", key=f"ar_{year}_{s_idx}"):
                        ranges.append([f"{year}-01-01", f"{year}-01-07"])
                        save_data()
                        st.rerun()
