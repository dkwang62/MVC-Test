# ----------------------------------------------------------------------
# CHANGE ROOM NAME FUNCTIONALITY - COMPLETELY REWRITTEN
# ----------------------------------------------------------------------
def handle_room_name_change(data: Dict, resort: str):
    """Handle changing room names across all seasons and categories."""
    st.subheader("✏️ Change Room Name")
    st.caption("Change a room name everywhere it appears in this resort")
    
    rooms = get_all_room_types(data, resort)
    
    if not rooms:
        st.info("No room types found. Add room types first.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        old_room_name = st.selectbox(
            "Select Room to Rename",
            [""] + rooms,
            key="change_room_old_select"
        )
    
    with col2:
        new_room_name = st.text_input(
            "New Room Name",
            placeholder="Enter new room name",
            key="change_room_new_input"
        )
    
    if old_room_name and new_room_name:
        new_room_name_clean = new_room_name.strip()
        
        # Validation
        if not new_room_name_clean:
            st.error("New room name cannot be empty")
            return
            
        if new_room_name_clean == old_room_name:
            st.error("New room name must be different from old name")
            return
            
        if any(r.lower() == new_room_name_clean.lower() for r in rooms if r != old_room_name):
            st.error("❌ Room name already exists")
            return
        
        # Show preview and confirmation
        st.info(f"**Preview:** Change **{old_room_name}** → **{new_room_name_clean}**")
        
        # Show where changes will be made
        changes_summary = analyze_room_name_changes(data, resort, old_room_name)
        st.info(f"**Changes will be made in:** {changes_summary}")
        
        st.warning("This will change the room name in ALL seasons, day types, and categories.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirm Change", type="primary", key="confirm_room_name_change"):
                change_room_name_global(data, resort, old_room_name, new_room_name_clean)
        with col2:
            if st.button("❌ Cancel", key="cancel_room_name_change"):
                st.rerun()

def analyze_room_name_changes(data: Dict, resort: str, old_room_name: str) -> str:
    """Analyze where room name changes will be applied."""
    locations = []
    
    # Check reference points
    ref_points = data["reference_points"].get(resort, {})
    for season_name, season_data in ref_points.items():
        if season_name == HOLIDAY_SEASON_KEY:
            # Holiday season structure
            for holiday_name, holiday_data in season_data.items():
                if isinstance(holiday_data, dict) and old_room_name in holiday_data:
                    locations.append(f"Reference Points > {season_name} > {holiday_name}")
        else:
            # Regular season structure
            for day_type, day_data in season_data.items():
                if isinstance(day_data, dict) and old_room_name in day_data:
                    locations.append(f"Reference Points > {season_name} > {day_type}")
    
    # Check point costs
    point_costs = data["point_costs"].get(resort, {})
    for season_name, season_data in point_costs.items():
        if season_name == HOLIDAY_SEASON_KEY:
            # Holiday season structure
            for holiday_name, holiday_data in season_data.items():
                if isinstance(holiday_data, dict) and old_room_name in holiday_data:
                    locations.append(f"Point Costs > {season_name} > {holiday_name}")
        else:
            # Regular season structure
            for day_type, day_data in season_data.items():
                if isinstance(day_data, dict) and old_room_name in day_data:
                    locations.append(f"Point Costs > {season_name} > {day_type}")
    
    return ", ".join(locations) if locations else "No locations found (room name may not exist in data)"

def change_room_name_global(data: Dict, resort: str, old_name: str, new_name: str):
    """Change room name across all data structures in the resort - COMPLETELY REWRITTEN."""
    changes_made = False
    
    # Debug: Show current data structure
    st.write("🔍 Debug: Current data structure for reference points:")
    st.json(data["reference_points"].get(resort, {}))
    
    # Update reference points - Handle ALL possible structures
    ref_points = data["reference_points"].get(resort, {})
    for season_name, season_data in ref_points.items():
        st.write(f"🔍 Processing season: {season_name}")
        st.write(f"🔍 Season data type: {type(season_data)}")
        st.write(f"🔍 Season data: {season_data}")
        
        if season_name == HOLIDAY_SEASON_KEY:
            # Holiday season has nested holiday structure
            st.write("🔍 Detected holiday season structure")
            for holiday_name, holiday_data in season_data.items():
                st.write(f"🔍 Processing holiday: {holiday_name}")
                st.write(f"🔍 Holiday data: {holiday_data}")
                if isinstance(holiday_data, dict):
                    if old_name in holiday_data:
                        st.write(f"✅ Found room '{old_name}' in holiday '{holiday_name}'")
                        holiday_data[new_name] = holiday_data.pop(old_name)
                        changes_made = True
                        st.success(f"✅ Updated Reference Points > {season_name} > {holiday_name}")
        else:
            # Regular season has day_type structure
            st.write("🔍 Detected regular season structure")
            for day_type, day_data in season_data.items():
                st.write(f"🔍 Processing day type: {day_type}")
                st.write(f"🔍 Day data: {day_data}")
                if isinstance(day_data, dict):
                    if old_name in day_data:
                        st.write(f"✅ Found room '{old_name}' in day type '{day_type}'")
                        day_data[new_name] = day_data.pop(old_name)
                        changes_made = True
                        st.success(f"✅ Updated Reference Points > {season_name} > {day_type}")
    
    # Update point costs - Handle ALL possible structures
    point_costs = data["point_costs"].get(resort, {})
    for season_name, season_data in point_costs.items():
        if season_name == HOLIDAY_SEASON_KEY:
            # Holiday season has nested holiday structure
            for holiday_name, holiday_data in season_data.items():
                if isinstance(holiday_data, dict) and old_name in holiday_data:
                    holiday_data[new_name] = holiday_data.pop(old_name)
                    changes_made = True
                    st.success(f"✅ Updated Point Costs > {season_name} > {holiday_name}")
        else:
            # Regular season has day_type structure
            for day_type, day_data in season_data.items():
                if isinstance(day_data, dict) and old_name in day_data:
                    day_data[new_name] = day_data.pop(old_name)
                    changes_made = True
                    st.success(f"✅ Updated Point Costs > {season_name} > {day_type}")
    
    if changes_made:
        save_data(data)
        st.success(f"✅ Successfully changed **{old_name}** → **{new_name}** everywhere!")
        st.balloons()
        st.rerun()
    else:
        st.error(f"❌ No changes made - room name '{old_name}' not found in any data structures")
        st.info("💡 Check the debug output above to see the actual data structure")
