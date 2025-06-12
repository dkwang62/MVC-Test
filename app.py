# Main UI
try:
    # Initialize variables outside the sidebar
    user_mode = st.sidebar.selectbox("User Mode", options=["Renter", "Owner"], index=0)
    rate_per_point = 0.81  # Default value
    discount_percent = 0
    display_mode = "both"
    capital_cost_per_point = 16.0
    cost_of_capital_percent = 7.0
    useful_life = 15
    salvage_value = 3.0
    booking_discount = None
    cost_components = ["maintenance", "capital", "depreciation"]

    # Add resort selection
    resorts_list = list(data.get("resorts_list", []))  # Assuming resorts_list is defined in data.json
    if not resorts_list:
        st.error("No resorts defined in data.json. Please ensure 'resorts_list' is populated.")
        st.stop()
    resort = st.selectbox("Select Resort", options=resorts_list)

    st.title("Marriott Vacation Club " + ("Rent Calculator" if user_mode == "Renter" else "Cost Calculator"))

    # Define checkin_date and num_nights first
    checkin_date = st.date_input(
        "Check-in Date",
        min_value=datetime(2025, 1, 3).date(),
        max_value=datetime(2026, 12, 31).date(),
        value=datetime(2025, 6, 12).date()  # Set to current date: June 12, 2025
    )
    num_nights = st.number_input("Number of Nights", min_value=1, max_value=30, value=7)
    checkout_date = checkin_date + timedelta(days=num_nights)
    st.write(f"Checkout Date: {checkout_date.strftime('%Y-%m-%d')}")

    with st.sidebar:
        st.header("Parameters")
        if user_mode == "Owner":
            display_options = [
                (0, "both"), (25, "both"), (30, "both"),
                (0, "points"), (25, "points"), (30, "points")
            ]

            def format_discount(i):
                discount, mode = display_options[i]
                level = (
                    "Presidential" if discount == 30 else
                    "Executive" if discount == 25 else
                    "Ordinary"
                )
                if mode == "points":
                    return f"{discount}% Discount ({level}, Points)"
                return f"{discount}% Discount ({level}, Cost)"

            display_mode_select = st.selectbox(
                "Display and Discount Settings",
                options=range(len(display_options)),
                format_func=format_discount,
                index=0
            )

            discount_percent, display_mode = display_options[display_mode_select]
            rate_per_point = st.number_input("Maintenance Rate per Point ($)", min_value=0.0, value=0.81, step=0.01)
            capital_cost_per_point = st.number_input("Purchase Price per Point ($)", min_value=0.0, value=16.0, step=0.1)
            if "capital" in cost_components:
                cost_of_capital_percent = st.number_input("Cost of Capital (%)", min_value=0.0, max_value=100.0, value=7.0, step=0.1)
            if "depreciation" in cost_components:
                useful_life = st.number_input("Useful Life (Years)", min_value=1, value=15, step=1)
                salvage_value = st.number_input("Salvage Value per Point ($)", min_value=0.0, value=3.0, step=0.1)
            cost_components = st.multiselect("Cost Components", options=["maintenance", "capital", "depreciation"], default=["maintenance", "capital", "depreciation"])
            depreciation_per_point = (capital_cost_per_point - salvage_value) / useful_life if useful_life > 0 and "depreciation" in cost_components else 0
            st.write(f"Depreciation: ${depreciation_per_point:.2f} per point" if "depreciation" in cost_components else "")
            st.caption(f"Cost calculation based on {discount_percent}% discount and selected components.")
        else:
            rate_option = st.radio("Rate Option", ["Based on Maintenance Rate", "Custom Rate", "Booked within 60 days", "Booked within 30 days"])
            if rate_option == "Based on Maintenance Rate":
                rate_per_point = 0.81 if checkin_date.year == 2025 else 0.86
                booking_discount = None
            elif rate_option == "Booked within 60 days":
                rate_per_point = 0.81 if checkin_date.year == 2025 else 0.86
                booking_discount = "within_60_days"
            elif rate_option == "Booked within 30 days":
                rate_per_point = 0.81 if checkin_date.year == 2025 else 0.86
                booking_discount = "within_30_days"
            else:
                rate_per_point = st.number_input("Custom Rate per Point ($)", min_value=0.0, value=0.81, step=0.01)
                booking_discount = None

    discount_multiplier = 1 - (discount_percent / 100)
    cost_of_capital = cost_of_capital_percent / 100 if "capital" in cost_components else 0

    # Dynamic expander content based on latest inputs
    with st.expander("\U0001F334 How " + ("Rent" if user_mode == "Renter" else "Cost") + " Is Calculated"):
        if user_mode == "Renter":
            st.markdown("""
            - Authored by Desmond Kwang https://www.facebook.com/dkwang62
            - Rental Rate per Point is based on MVC Abound maintenance fees or custom input
            - Default: $0.81 for 2025 stays (actual rate)
            - Default: $0.86 for 2026 stays (forecasted rate)
            - **Booked within 60 days**: 30% discount on points required, only for Presidential-level owners, applies to stays within 60 days from today
            - **Booked within 30 days**: 25% discount on points required, only for Executive-level owners, applies to stays within 30 days from today
            - Rent = (Points × Discount Multiplier) × Rate per Point
            """)
        else:
            depreciation_per_point = (capital_cost_per_point - salvage_value) / useful_life if useful_life > 0 and "depreciation" in cost_components else 0
            st.markdown(f"""
            - Authored by Desmond Kwang https://www.facebook.com/dkwang62
            - Maintenance rate: ${rate_per_point:.2f} per point
            - Purchase price: ${capital_cost_per_point:.2f} per point
            - Cost of capital: {cost_of_capital_percent:.1f}%{' (if capital selected)' if 'capital' in cost_components else ''}
            - Useful Life: {useful_life} years{' (if depreciation selected)' if 'depreciation' in cost_components else ''}
            - Salvage Value: ${salvage_value:.2f} per point{' (if depreciation selected)' if 'depreciation' in cost_components else ''}
            - Depreciation: ${depreciation_per_point:.2f} per point{' (if depreciation selected)' if 'depreciation' in cost_components else ''}
            - Selected discount: {discount_percent}%
            - Cost components: {', '.join(cost_components)}
            - Total cost is the sum of selected components (maintenance, capital, depreciation){' (shown only if multiple components selected)' if len(cost_components) > 1 else ''}
            """)

    # [Rest of the code continues with the existing logic, including the Calculate button and subsequent sections]

    if (
        "last_resort" not in st.session_state
        or st.session_state.last_resort != resort
        or "last_year" not in st.session_state
        or st.session_state.last_year != year_select
    ):
        st.session_state.data_cache.clear()
        if "room_types" in st.session_state:
            del st.session_state.room_types
        if "display_to_internal" in st.session_state:
            del st.session_state.display_to_internal
        st.session_state.last_resort = resort
        st.session_state.last_year = year_select
        st.session_state.debug_messages.append(
            f"Cleared cache and room data due to resort ({resort}) or year ({year_select}) change"
        )

    if "room_types" not in st.session_state:
        sample_date = checkin_date
        st.session_state.debug_messages.append(f"Generating room types for {resort} on {sample_date}")
        sample_entry, display_to_internal = generate_data(resort, sample_date)
        room_types = sorted(
            [
                k
                for k in sample_entry
                if k not in ["HolidayWeek", "HolidayWeekStart", "holiday_name", "holiday_start", "holiday_end"]
            ]
        )
        if not room_types:
            st.error(f"No room types found for {resort}. Please ensure reference_points data is available.")
            st.session_state.debug_messages.append(f"No room types for {resort}")
            st.stop()
        st.session_state.room_types = room_types
        st.session_state.display_to_internal = display_to_internal
        st.session_state.debug_messages.append(f"Room types for {resort}: {room_types}")
    else:
        room_types = st.session_state.room_types
        display_to_internal = st.session_state.display_to_internal

    room_type = st.selectbox("Select Room Type", options=room_types, key="room_type_select")
    compare_rooms = st.multiselect("Compare With Other Room Types", options=[r for r in room_types if r != room_type])

    original_checkin_date = checkin_date
    checkin_date, adjusted_nights, was_adjusted = adjust_date_range(resort, checkin_date, num_nights)
    if was_adjusted:
        st.info(
            f"Date range adjusted to include full holiday week: {checkin_date.strftime('%Y-%m-%d')} to "
            f"{(checkin_date + timedelta(days=adjusted_nights - 1)).strftime('%Y-%m-%d')} ({adjusted_nights} nights)."
        )
    st.session_state.last_checkin_date = checkin_date

    reference_entry, _ = generate_data(resort, checkin_date)
    reference_points_resort = {
        k: v for k, v in reference_entry.items()
        if k not in ["HolidayWeek", "HolidayWeekStart", "holiday_name", "holiday_start", "holiday_end"]
    }

    ap_room_types = []
    ap_display_room_types = []
    if resort == "Ko Olina Beach Club" and "AP Rooms" in reference_points.get(resort, {}):
        ap_room_types = list(reference_points[resort]["AP Rooms"].get("Fri-Sat", {}).keys())
        ap_display_room_types = [get_display_room_type(rt) for rt in ap_room_types]

    if st.button("Calculate"):
        st.session_state.debug_messages.append("Starting new calculation...")
        if user_mode == "Renter":
            # Placeholder for renter mode calculation (to be implemented)
            pass
        else:  # Owner mode
            breakdown, total_points, total_cost, total_maintenance_cost, total_capital_cost, total_depreciation_cost = calculate_stay_owner(
                resort, room_type, checkin_date, adjusted_nights, discount_percent, discount_multiplier, display_mode,
                rate_per_point, capital_cost_per_point, cost_of_capital, useful_life, salvage_value, cost_components
            )
            st.subheader("Stay Breakdown")
            if not breakdown.empty:
                st.dataframe(breakdown, use_container_width=True)
            else:
                st.error("No data available for the selected period.")

            st.success(f"Total Points Used: {total_points}")
            if display_mode == "both":
                if len(cost_components) > 1:
                    st.success(f"Estimated Total Cost: ${total_cost}" if total_cost > 0 else "Estimated Total Cost: $-")
                if "maintenance" in cost_components:
                    st.success(f"Total Maintenance Cost: ${total_maintenance_cost}")
                if "capital" in cost_components:
                    st.success(f"Total Capital Cost: ${total_capital_cost}")
                if "depreciation" in cost_components:
                    st.success(f"Total Depreciation Cost: ${total_depreciation_cost}")

            if not breakdown.empty:
                csv_data = breakdown.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Breakdown as CSV",
                    data=csv_data,
                    file_name=f"{resort}_stay_breakdown.csv",
                    mime="text/csv"
                )

            if compare_rooms:
                st.subheader("Room Type Comparison")
                st.info("Note: Non-holiday weeks are compared day-by-day; holiday weeks are compared as total points for the week.")
                all_rooms = [room_type] + compare_rooms
                chart_df, compare_df_pivot, holiday_totals = compare_room_types_owner(
                    resort, all_rooms, checkin_date, adjusted_nights, discount_multiplier,
                    discount_percent, ap_display_room_types, display_mode, rate_per_point,
                    capital_cost_per_point, cost_of_capital, useful_life, salvage_value, cost_components
                )

                display_columns = ["Date"] + [col for col in compare_df_pivot.columns if "Points" in col or (display_mode == "both" and "Total Cost" in col)]
                st.write(f"### {'Points' if display_mode == 'points' else 'Points and Total Cost'} Comparison")
                st.dataframe(compare_df_pivot[display_columns], use_container_width=True)

                compare_csv = compare_df_pivot.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Room Comparison as CSV",
                    data=compare_csv,
                    file_name=f"{resort}_room_comparison.csv",
                    mime="text/csv"
                )

                if not chart_df.empty:
                    required_columns = ["Date", "Room Type", "Points", "Holiday"]
                    if display_mode == "both":
                        required_columns.extend(["Total Cost", "TotalCostValue"])
                    if all(col in chart_df.columns for col in required_columns):
                        non_holiday_df = chart_df[chart_df["Holiday"] == "No"]
                        holiday_data = []
                        for room in all_rooms:
                            for holiday_name, totals in holiday_totals[room].items():
                                if totals["points"] > 0:
                                    row = {
                                        "Holiday": holiday_name,
                                        "Room Type": room,
                                        "Points": totals["points"],
                                        "Start": totals["start"],
                                        "End": totals["end"]
                                    }
                                    if display_mode == "both" and len(cost_components) > 1:
                                        maintenance_cost = math.ceil(totals["points"] * rate_per_point) if "maintenance" in cost_components else 0
                                        capital_cost = math.ceil(totals["points"] * capital_cost_per_point * cost_of_capital) if "capital" in cost_components else 0
                                        depreciation_cost = math.ceil(totals["points"] * ((capital_cost_per_point - salvage_value) / useful_life)) if "depreciation" in cost_components else 0
                                        total_holiday_cost = maintenance_cost + capital_cost + depreciation_cost
                                        row["Total Cost"] = f"${total_holiday_cost}" if total_holiday_cost > 0 else "-"
                                        row["TotalCostValue"] = total_holiday_cost
                                    holiday_data.append(row)
                        holiday_df = pd.DataFrame(holiday_data)

                        if not non_holiday_df.empty:
                            start_date = non_holiday_df["Date"].min()
                            end_date = non_holiday_df["Date"].max()
                            start_date_str = start_date.strftime("%b %d")
                            end_date_str = end_date.strftime("%b %d, %Y")
                            title = f"Points Comparison (Non-Holiday, {start_date_str} - {end_date_str})"
                            st.subheader(title)
                            day_order = ["Fri", "Sat", "Sun", "Mon", "Tue", "Wed", "Thu"]
                            fig = px.bar(
                                non_holiday_df,
                                x="Day",
                                y="Points",
                                color="Room Type",
                                barmode="group",
                                title=title,
                                labels={"Points": "Points", "Day": "Day of Week"},
                                height=600,
                                text="Points",
                                text_auto=True,
                                category_orders={"Day": day_order}
                            )
                            fig.update_traces(texttemplate="%{text}", textposition="auto")
                            fig.update_xaxes(
                                ticktext=day_order,
                                tickvals=[0, 1, 2, 3, 4, 5, 6],
                                tickmode="array"
                            )
                            fig.update_layout(
                                legend_title_text="Room Type",
                                bargap=0.2,
                                bargroupgap=0.1
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        if not holiday_df.empty:
                            start_date = holiday_df["Start"].min()
                            end_date = holiday_df["End"].max()
                            start_date_str = start_date.strftime("%b %d")
                            end_date_str = end_date.strftime("%b %d, %Y")
                            title = f"Points Comparison (Holiday Weeks, {start_date_str} - {end_date_str})"
                            st.subheader(title)
                            fig = px.bar(
                                holiday_df,
                                x="Holiday",
                                y="Points",
                                color="Room Type",
                                barmode="group",
                                title=title,
                                labels={"Points": "Points", "Holiday": "Holiday Week"},
                                height=600,
                                text="Points",
                                text_auto=True
                            )
                            fig.update_traces(texttemplate="%{text}", textposition="auto")
                            fig.update_layout(
                                legend_title_text="Room Type",
                                bargap=0.2,
                                bargroupgap=0.1
                            )
                            st.plotly_chart(fig, use_container_width=True)

        st.subheader(f"Season and Holiday Calendar for {year_select}")
        gantt_fig = create_gantt_chart(resort, year_select)
        st.plotly_chart(gantt_fig, use_container_width=True)

except Exception as e:
    st.error(f"Application error: {str(e)}")
    st.session_state.debug_messages.append(f"Error: {str(e)}\n{traceback.format_exc()}")
    with st.expander("Debug Information"):
        if st.button("Clear Debug Messages"):
            st.session_state.debug_messages = []
            st.session_state.debug_messages.append("Debug messages cleared.")
        if st.session_state.debug_messages:
            for msg in st.session_state.debug_messages:
                st.write(msg)
        else:
            st.write("No debug messages available.")
