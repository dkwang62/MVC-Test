import streamlit as st
import math
import json
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import traceback
from collections import defaultdict

# Load data.json
with open("data.json", "r") as f:
    data = json.load(f)

# Define constants
room_view_legend = {
    "GV": "Garden", "OV": "Ocean", "OF": "Oceanfront", "S": "Standard", "IS": "Island Side",
    "PS": "Pool Low Flrs", "PSH": "Pool High Flrs", "UF": "Gulf Front", "UV": "Gulf View",
    "US": "Gulf Side", "PH": "Penthouse", "PHGV": "Penthouse Garden", "PHOV": "Penthouse Ocean View",
    "PHOF": "Penthouse Ocean Front", "IV": "Island", "MG": "Garden", "PHMA": "Penthouse Mountain",
    "PHMK": "Penthouse Ocean", "PHUF": "Penthouse Gulf Front", "AP_Studio_MA": "AP Studio Mountain",
    "AP_1BR_MA": "AP 1BR Mountain", "AP_2BR_MA": "AP 2BR Mountain", "AP_2BR_MK": "AP 2BR Ocean",
    "LO": "Lock-Off", "CV": "City", "LV": "Lagoon", "PV": "Pool", "OS": "Oceanside",
    "K": "King", "DB": "Double Bed", "MA": "Mountain", "MK": "Ocean", "OF": "Front"
}
season_blocks = data.get("season_blocks", {})
reference_points = data.get("reference_points", {})
holiday_weeks = data.get("holiday_weeks", {})

# Initialize session state
if "debug_messages" not in st.session_state:
    st.session_state.debug_messages = []
if "data_cache" not in st.session_state:
    st.session_state.data_cache = {}

# Helper functions
def get_display_room_type(room_key):
    if room_key in room_view_legend:
        return room_view_legend[room_key]
    parts = room_key.split()
    if not parts:
        return room_key
    if room_key.startswith("AP_"):
        if room_key == "AP_Studio_MA": return "AP Studio Mountain"
        elif room_key == "AP_1BR_MA": return "AP 1BR Mountain"
        elif room_key == "AP_2BR_MA": return "AP 2BR Mountain"
        elif room_key == "AP_2BR_MK": return "AP 2BR Ocean"
    view = parts[-1]
    if len(parts) > 1 and view in room_view_legend:
        return f"{parts[0]} {room_view_legend[view]}"
    if room_key in ["2BR", "1BR", "3BR"]:
        return room_key
    return room_key

def get_internal_room_key(display_name):
    reverse_legend = {v: k for k, v in room_view_legend.items()}
    if display_name in reverse_legend:
        return reverse_legend[display_name]
    if display_name.startswith("AP "):
        if display_name == "AP Studio Mountain": return "AP_Studio_MA"
        elif display_name == "AP 1BR Mountain": return "AP_1BR_MA"
        elif display_name == "AP 2BR Mountain": return "AP_2BR_MA"
        elif display_name == "AP 2BR Ocean": return "AP_2BR_MK"
    parts = display_name.split()
    if not parts:
        return display_name
    base_parts, view_parts = [], []
    found_view = False
    for part in parts:
        if part in ["Mountain", "Ocean", "Penthouse", "Garden", "Front"] and not found_view:
            found_view = True
            view_parts.append(part)
        else:
            base_parts.append(part)
            if found_view:
                view_parts.append(part)
    base = " ".join(base_parts)
    view = reverse_legend.get(" ".join(view_parts), " ".join(view_parts))
    return f"{base} {view}".strip()

def adjust_date_range(resort, checkin_date, num_nights):
    year_str = str(checkin_date.year)
    stay_end = checkin_date + timedelta(days=num_nights - 1)
    holiday_ranges = []
    st.session_state.debug_messages.append(f"Checking holiday overlap for {checkin_date} to {stay_end} at {resort}")
    if "holiday_weeks" not in data or resort not in data["holiday_weeks"] or year_str not in data["holiday_weeks"][resort]:
        st.session_state.debug_messages.append(f"No holiday weeks defined for {resort} in {year_str}")
        return checkin_date, num_nights, False
    for h_name, holiday_data in data["holiday_weeks"][resort][year_str].items():
        try:
            if isinstance(holiday_data, str) and holiday_data.startswith("global:"):
                global_key = holiday_data.split(":", 1)[1]
                holiday_data = data["global_dates"].get(year_str, {}).get(global_key, [])
            if len(holiday_data) >= 2:
                h_start = datetime.strptime(holiday_data[0], "%Y-%m-%d").date()
                h_end = datetime.strptime(holiday_data[1], "%Y-%m-%d").date()
                if h_start <= stay_end and h_end >= checkin_date:
                    holiday_ranges.append((h_start, h_end, h_name))
        except (IndexError, ValueError) as e:
            st.session_state.debug_messages.append(f"Invalid holiday range for {h_name} at {resort}: {e}")
    if holiday_ranges:
        earliest_start = min(h_start for h_start, _, _ in holiday_ranges)
        latest_end = max(h_end for _, h_end, _ in holiday_ranges)
        adjusted_start = min(checkin_date, earliest_start)
        adjusted_end = max(stay_end, latest_end)
        adjusted_nights = (adjusted_end - adjusted_start).days + 1
        holiday_names = [h_name for _, _, h_name in holiday_ranges]
        st.session_state.debug_messages.append(f"Adjusted to {adjusted_start} to {adjusted_end} ({adjusted_nights} nights) for {holiday_names}")
        return adjusted_start, adjusted_nights, True
    return checkin_date, num_nights, False

def generate_data(resort, date, cache=None):
    if cache is None:
        cache = st.session_state.data_cache
    date_str = date.strftime("%Y-%m-%d")
    if date_str in cache:
        return cache[date_str]
    year, day_of_week = date.strftime("%Y"), date.strftime("%a")
    is_fri_sat, is_sun = day_of_week in ["Fri", "Sat"], day_of_week == "Sun"
    day_category = "Fri-Sat" if is_fri_sat else "Sun" if is_sun else "Mon-Thu"
    ap_day_category = day_category
    entry, ap_room_types = {}, []
    if resort == "Ko Olina Beach Club" and "AP Rooms" in reference_points.get(resort, {}):
        ap_room_types = list(reference_points[resort]["AP Rooms"].get(ap_day_category, {}).keys())
    season, holiday_name, is_holiday, is_holiday_start = None, None, False, False
    holiday_start_date, holiday_end_date = None, None
    prev_year = str(int(year) - 1)
    if (date.month == 12 and date.day >= 26) or (date.month == 1 and date.day <= 1):
        holiday_start = datetime.strptime(f"{prev_year}-12-26", "%Y-%m-%d").date()
        holiday_end = datetime.strptime(f"{year}-01-01", "%Y-%m-%d").date()
        if holiday_start <= date <= holiday_end:
            is_holiday, holiday_name, season = True, "New Year's Eve/Day", "Holiday Week"
            holiday_start_date, holiday_end_date = holiday_start, holiday_end
            if date == holiday_start:
                is_holiday_start = True
    if year in holiday_weeks.get(resort, {}) and not is_holiday:
        for h_name, holiday_data in holiday_weeks[resort][year].items():
            if isinstance(holiday_data, str) and holiday_data.startswith("global:"):
                global_key = holiday_data.split(":", 1)[1]
                holiday_data = data["global_dates"].get(year, {}).get(global_key, [])
            if len(holiday_data) >= 2:
                start, end = datetime.strptime(holiday_data[0], "%Y-%m-%d").date(), datetime.strptime(holiday_data[1], "%Y-%m-%d").date()
                if start <= date <= end:
                    is_holiday, holiday_name, season = True, h_name, "Holiday Week"
                    holiday_start_date, holiday_end_date = start, end
                    if date == start:
                        is_holiday_start = True
    if not is_holiday and year in season_blocks.get(resort, {}):
        for season_name, ranges in season_blocks[resort][year].items():
            for start_date, end_date in ranges:
                if datetime.strptime(start_date, "%Y-%m-%d").date() <= date <= datetime.strptime(end_date, "%Y-%m-%d").date():
                    season = season_name
                    break
            if season:
                break
    if season is None:
        season = "Default Season"
    normal_room_category, normal_room_types = None, []
    if season != "Holiday Week":
        possible_categories = ["Fri-Sat", "Sun", "Mon-Thu", "Sun-Thu"]
        available_categories = [cat for cat in possible_categories if reference_points.get(resort, {}).get(season, {}).get(cat)]
        if available_categories:
            normal_room_category = "Fri-Sat" if is_fri_sat and "Fri-Sat" in available_categories else \
                                 "Sun" if is_sun and "Sun" in available_categories else \
                                 "Mon-Thu" if not is_fri_sat and "Mon-Thu" in available_categories else \
                                 "Sun-Thu" if "Sun-Thu" in available_categories else available_categories[0]
            normal_room_types = list(reference_points.get(resort, {}).get(season, {}).get(normal_room_category, {}).keys())
    else:
        if holiday_name in reference_points.get(resort, {}).get("Holiday Week", {}):
            normal_room_types = list(reference_points[resort]["Holiday Week"].get(holiday_name, {}).keys())
    all_room_types = normal_room_types + ap_room_types
    all_display_room_types = [get_display_room_type(rt) for rt in all_room_types]
    display_to_internal = dict(zip(all_display_room_types, all_room_types))
    for display_room_type, room_type in display_to_internal.items():
        points = 0
        is_ap_room = room_type in ap_room_types
        if is_holiday and is_holiday_start:
            points = reference_points.get(resort, {}).get("AP Rooms", {}).get("Full Week", {}).get(room_type, 0) if is_ap_room else \
                     reference_points.get(resort, {}).get("Holiday Week", {}).get(holiday_name, {}).get(room_type, 0)
        elif is_holiday and not is_holiday_start and holiday_start_date <= date <= holiday_end_date:
            points = 0
        elif is_ap_room:
            points = reference_points.get(resort, {}).get("AP Rooms", {}).get(ap_day_category, {}).get(room_type, 0)
        elif normal_room_category:
            points = reference_points.get(resort, {}).get(season, {}).get(normal_room_category, {}).get(room_type, 0)
        entry[display_room_type] = points
    if is_holiday:
        entry.update({"HolidayWeek": True, "holiday_name": holiday_name, "holiday_start": holiday_start_date, "holiday_end": holiday_end_date})
        if is_holiday_start:
            entry["HolidayWeekStart"] = True
    cache[date_str] = (entry, display_to_internal)
    st.session_state.data_cache = cache
    return entry, display_to_internal

def create_gantt_chart(resort, year):
    gantt_data = []
    year_str = str(year)
    for h_name, holiday_data in holiday_weeks.get(resort, {}).get(year_str, {}).items():
        try:
            if isinstance(holiday_data, str) and holiday_data.startswith("global:"):
                global_key = holiday_data.split(":", 1)[1]
                holiday_data = data["global_dates"].get(year_str, {}).get(global_key, [])
            if len(holiday_data) >= 2:
                start_date, end_date = datetime.strptime(holiday_data[0], "%Y-%m-%d").date(), datetime.strptime(holiday_data[1], "%Y-%m-%d").date()
                gantt_data.append({"Task": h_name, "Start": start_date, "Finish": end_date, "Type": "Holiday"})
        except (IndexError, ValueError) as e:
            st.session_state.debug_messages.append(f"Invalid holiday data for {h_name} at {resort}: {e}")
    season_types = list(season_blocks.get(resort, {}).get(year_str, {}).keys())
    for season_type in season_types:
        for i, (start, end) in enumerate(season_blocks[resort][year_str][season_type], 1):
            try:
                start_date, end_date = datetime.strptime(start, "%Y-%m-%d").date(), datetime.strptime(end, "%Y-%m-%d").date()
                gantt_data.append({"Task": f"{season_type} {i}", "Start": start_date, "Finish": end_date, "Type": season_type})
            except ValueError as e:
                st.session_state.debug_messages.append(f"Invalid season data for {season_type} at {resort}: {e}")
    df = pd.DataFrame(gantt_data) if gantt_data else pd.DataFrame({"Task": ["No Data"], "Start": [datetime.now().date()], "Finish": [datetime.now().date() + timedelta(days=1)], "Type": ["No Data"]})
    color_distribution = {"Holiday": "rgb(255, 99, 71)", "Low Season": "rgb(135, 206, 250)", "High Season": "rgb(255, 69, 0)", "Peak Season": "rgb(255, 215, 0)", "Shoulder": "rgb(50, 205, 50)", "Peak": "rgb(255, 69, 0)", "Summer": "rgb(255, 165, 0)", "Low": "rgb(70, 130, 180)", "Mid Season": "rgb(60, 179, 113)", "No Data": "rgb(128, 128, 128)"}
    colors = {t: color_distribution.get(t, "rgb(169, 169, 169)") for t in df["Type"].unique()}
    fig = px.timeline(df, x_start="Start", x_end="Finish", y="Task", color="Type", color_discrete_map=colors, title=f"{resort} Seasons and Holidays ({year})", height=600)
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_title="Date", yaxis_title="Period", showlegend=True)
    return fig

def calculate_stay_renter(resort, room_type, checkin_date, num_nights, rate_per_point, booking_discount=None):
    breakdown, total_points, total_rent = [], 0, 0
    current_holiday, holiday_end = None, None
    for i in range(num_nights):
        date = checkin_date + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        try:
            entry, _ = generate_data(resort, date)
            points = entry.get(room_type, 0)
            effective_points = points
            if booking_discount:
                days_until = (date - datetime.now().date()).days
                if booking_discount == "within_60_days" and days_until <= 60:
                    effective_points = math.floor(points * 0.7)
                elif booking_discount == "within_30_days" and days_until <= 30:
                    effective_points = math.floor(points * 0.75)
            rent = math.ceil(effective_points * rate_per_point)
            if entry.get("HolidayWeek", False):
                if entry.get("HolidayWeekStart", False):
                    current_holiday = entry.get("holiday_name")
                    holiday_start, holiday_end = entry.get("holiday_start"), entry.get("holiday_end")
                    breakdown.append({"Date": f"{current_holiday} ({holiday_start.strftime('%b %d, %Y')} - {holiday_end.strftime('%b %d, %Y')})", "Day": "", "Points": effective_points, "Rent": f"${rent}"})
                    total_points += effective_points
                    total_rent += rent
                elif current_holiday and date <= holiday_end:
                    continue
            else:
                current_holiday, holiday_end = None, None
                breakdown.append({"Date": date_str, "Day": date.strftime("%a"), "Points": effective_points, "Rent": f"${rent}"})
                total_points += effective_points
                total_rent += rent
        except Exception as e:
            st.session_state.debug_messages.append(f"Error calculating for {resort}, {date_str}: {str(e)}")
    return pd.DataFrame(breakdown), total_points, total_rent

def calculate_stay_owner(resort, room_type, checkin_date, num_nights, discount_percent, discount_multiplier, display_mode, rate_per_point, capital_cost_per_point, cost_of_capital, useful_life, salvage_value, cost_components):
    breakdown, total_points, total_cost = [], 0, 0
    total_maintenance_cost, total_capital_cost, total_depreciation_cost = 0, 0, 0
    current_holiday, holiday_end = None, None
    depreciation_cost_per_point = (capital_cost_per_point - salvage_value) / useful_life if useful_life > 0 and "depreciation" in cost_components else 0
    for i in range(num_nights):
        date = checkin_date + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        try:
            entry, _ = generate_data(resort, date)
            points = entry.get(room_type, 0)
            discounted_points = math.floor(points * discount_multiplier)
            if entry.get("HolidayWeek", False):
                if entry.get("HolidayWeekStart", False):
                    current_holiday = entry.get("holiday_name")
                    holiday_start, holiday_end = entry.get("holiday_start"), entry.get("holiday_end")
                    row = {"Date": f"{current_holiday} ({holiday_start.strftime('%b %d, %Y')} - {holiday_end.strftime('%b %d, %Y')})", "Day": "", "Points": discounted_points}
                    if display_mode == "both" and len(cost_components) > 1:
                        maintenance_cost = math.ceil(discounted_points * rate_per_point) if "maintenance" in cost_components else 0
                        capital_cost = math.ceil(discounted_points * capital_cost_per_point * cost_of_capital) if "capital" in cost_components else 0
                        depreciation_cost = math.ceil(discounted_points * depreciation_cost_per_point) if "depreciation" in cost_components else 0
                        total_day_cost = maintenance_cost + capital_cost + depreciation_cost
                        row.update({"Total Cost": f"${total_day_cost}", "Maintenance": f"${maintenance_cost}", "Capital Cost": f"${capital_cost}", "Depreciation": f"${depreciation_cost}"})
                        total_cost += total_day_cost
                        total_maintenance_cost += maintenance_cost
                        total_capital_cost += capital_cost
                        total_depreciation_cost += depreciation_cost
                    elif display_mode == "both" and len(cost_components) == 1:
                        if "maintenance" in cost_components:
                            maintenance_cost = math.ceil(discounted_points * rate_per_point)
                            row["Maintenance"] = f"${maintenance_cost}"
                            total_maintenance_cost += maintenance_cost
                        elif "capital" in cost_components:
                            capital_cost = math.ceil(discounted_points * capital_cost_per_point * cost_of_capital)
                            row["Capital Cost"] = f"${capital_cost}"
                            total_capital_cost += capital_cost
                        elif "depreciation" in cost_components:
                            depreciation_cost = math.ceil(discounted_points * depreciation_cost_per_point)
                            row["Depreciation"] = f"${depreciation_cost}"
                            total_depreciation_cost += depreciation_cost
                    breakdown.append(row)
                    total_points += discounted_points
                elif current_holiday and date <= holiday_end:
                    continue
            else:
                current_holiday, holiday_end = None, None
                row = {"Date": date_str, "Day": date.strftime("%a"), "Points": discounted_points}
                if display_mode == "both" and len(cost_components) > 1:
                    maintenance_cost = math.ceil(discounted_points * rate_per_point) if "maintenance" in cost_components else 0
                    capital_cost = math.ceil(discounted_points * capital_cost_per_point * cost_of_capital) if "capital" in cost_components else 0
                    depreciation_cost = math.ceil(discounted_points * depreciation_cost_per_point) if "depreciation" in cost_components else 0
                    total_day_cost = maintenance_cost + capital_cost + depreciation_cost
                    row.update({"Total Cost": f"${total_day_cost}", "Maintenance": f"${maintenance_cost}", "Capital Cost": f"${capital_cost}", "Depreciation": f"${depreciation_cost}"})
                    total_cost += total_day_cost
                    total_maintenance_cost += maintenance_cost
                    total_capital_cost += capital_cost
                    total_depreciation_cost += depreciation_cost
                elif display_mode == "both" and len(cost_components) == 1:
                    if "maintenance" in cost_components:
                        maintenance_cost = math.ceil(discounted_points * rate_per_point)
                        row["Maintenance"] = f"${maintenance_cost}"
                        total_maintenance_cost += maintenance_cost
                    elif "capital" in cost_components:
                        capital_cost = math.ceil(discounted_points * capital_cost_per_point * cost_of_capital)
                        row["Capital Cost"] = f"${capital_cost}"
                        total_capital_cost += capital_cost
                    elif "depreciation" in cost_components:
                        depreciation_cost = math.ceil(discounted_points * depreciation_cost_per_point)
                        row["Depreciation"] = f"${depreciation_cost}"
                        total_depreciation_cost += depreciation_cost
                breakdown.append(row)
                total_points += discounted_points
        except Exception as e:
            st.session_state.debug_messages.append(f"Error processing {date_str} for {resort}: {str(e)}")
    return pd.DataFrame(breakdown), total_points, total_cost, total_maintenance_cost, total_capital_cost, total_depreciation_cost

def compare_room_types_renter(resort, room_types, checkin_date, num_nights, rate_per_point, booking_discount=None):
    compare_data, chart_data = [], []
    all_dates = [checkin_date + timedelta(days=i) for i in range(num_nights)]
    stay_start, stay_end = checkin_date, checkin_date + timedelta(days=num_nights - 1)
    holiday_ranges, holiday_names = [], {}
    for h_name, holiday_data in holiday_weeks.get(resort, {}).get(str(checkin_date.year), {}).items():
        try:
            if isinstance(holiday_data, str) and holiday_data.startswith("global:"):
                global_key = holiday_data.split(":", 1)[1]
                holiday_data = data["global_dates"].get(str(checkin_date.year), {}).get(global_key, [])
            if len(holiday_data) >= 2:
                h_start, h_end = datetime.strptime(holiday_data[0], "%Y-%m-%d").date(), datetime.strptime(holiday_data[1], "%Y-%m-%d").date()
                if h_start <= stay_end and h_end >= stay_start:
                    holiday_ranges.append((h_start, h_end))
                    for d in [h_start + timedelta(days=x) for x in range((h_end - h_start).days + 1)]:
                        if d in all_dates:
                            holiday_names[d] = h_name
        except (IndexError, ValueError) as e:
            st.session_state.debug_messages.append(f"Invalid holiday data for {h_name} at {resort}: {e}")
    total_points_by_room, total_rent_by_room, holiday_totals = {room: 0 for room in room_types}, {room: 0 for room in room_types}, {room: defaultdict(dict) for room in room_types}
    for date in all_dates:
        date_str, day_of_week = date.strftime("%Y-%m-%d"), date.strftime("%a")
        try:
            entry, _ = generate_data(resort, date)
            is_holiday_date, holiday_name, is_holiday_start = any(h_start <= date <= h_end for h_start, h_end in holiday_ranges), holiday_names.get(date), entry.get("HolidayWeekStart", False)
            for room in room_types:
                internal_room, is_ap_room = get_internal_room_key(room), room in [get_display_room_type(rt) for rt in ap_room_types]
                points = entry.get(room, 0)
                effective_points = points
                if booking_discount and not is_ap_room:
                    days_until = (date - datetime.now().date()).days
                    if booking_discount == "within_60_days" and days_until <= 60:
                        effective_points = math.floor(points * 0.7)
                    elif booking_discount == "within_30_days" and days_until <= 30:
                        effective_points = math.floor(points * 0.75)
                rent = math.ceil(effective_points * rate_per_point)
                if is_holiday_date and not is_ap_room:
                    if is_holiday_start:
                        if holiday_name not in holiday_totals[room]:
                            h_start = min(h for h, _ in holiday_ranges if holiday_names.get(date) == holiday_name)
                            h_end = max(e for _, e in holiday_ranges if holiday_names.get(date) == holiday_name)
                            holiday_totals[room][holiday_name] = {"points": effective_points, "rent": rent, "start": h_start, "end": h_end}
                        start_str, end_str = holiday_totals[room][holiday_name]["start"].strftime("%b %d"), holiday_totals[room][holiday_name]["end"].strftime("%b %d, %Y")
                        compare_data.append({"Date": f"{holiday_name} ({start_str} - {end_str})", "Room Type": room, "Points": effective_points, "Rent": f"${rent}"})
                    continue
                compare_data.append({"Date": date_str, "Room Type": room, "Points": effective_points, "Rent": f"${rent}"})
                total_points_by_room[room] += effective_points
                total_rent_by_room[room] += rent
                chart_data.append({"Date": date, "DateStr": date_str, "Day": day_of_week, "Room Type": room, "Points": effective_points, "Rent": f"${rent}", "RentValue": rent, "Holiday": entry.get("holiday_name", "No")})
        except Exception as e:
            st.session_state.debug_messages.append(f"Error in compare for {date_str} at {resort}: {str(e)}")
    compare_data.extend([{"Date": "Total Points (Non-Holiday)", **{room: total_points_by_room[room] for room in room_types}}, {"Date": "Total Rent (Non-Holiday)", **{room: f"${total_rent_by_room[room]}" for room in room_types}}])
    compare_df, compare_df_pivot = pd.DataFrame(compare_data), pd.DataFrame(compare_data).pivot_table(index="Date", columns="Room Type", values=["Points", "Rent"], aggfunc="first").reset_index()
    compare_df_pivot.columns = ['Date'] + [f"{col[1]} {col[0]}" for col in compare_df_pivot.columns[1:]]
    return pd.DataFrame(chart_data), compare_df_pivot, holiday_totals

def compare_room_types_owner(resort, room_types, checkin_date, num_nights, discount_multiplier, discount_percent, ap_display_room_types, display_mode, rate_per_point, capital_cost_per_point, cost_of_capital, useful_life, salvage_value, cost_components):
    compare_data, chart_data = [], []
    all_dates = [checkin_date + timedelta(days=i) for i in range(num_nights)]
    stay_start, stay_end = checkin_date, checkin_date + timedelta(days=num_nights - 1)
    holiday_ranges, holiday_names = [], {}
    for h_name, holiday_data in holiday_weeks.get(resort, {}).get(str(checkin_date.year), {}).items():
        try:
            if isinstance(holiday_data, str) and holiday_data.startswith("global:"):
                global_key = holiday_data.split(":", 1)[1]
                holiday_data = data["global_dates"].get(str(checkin_date.year), {}).get(global_key, [])
            if len(holiday_data) >= 2:
                h_start, h_end = datetime.strptime(holiday_data[0], "%Y-%m-%d").date(), datetime.strptime(holiday_data[1], "%Y-%m-%d").date()
                if h_start <= stay_end and h_end >= stay_start:
                    holiday_ranges.append((h_start, h_end))
                    for d in [h_start + timedelta(days=x) for x in range((h_end - h_start).days + 1)]:
                        if d in all_dates:
                            holiday_names[d] = h_name
        except (IndexError, ValueError) as e:
            st.session_state.debug_messages.append(f"Invalid holiday date for {h_name} at {resort}: {e}")
    total_points_by_room, total_cost_by_room, holiday_totals = {room: 0 for room in room_types}, {room: 0 for room in room_types}, {room: defaultdict(dict) for room in room_types}
    depreciation_cost_per_point = (capital_cost_per_point - salvage_value) / useful_life if useful_life > 0 and "depreciation" in cost_components else 0
    for date in all_dates:
        date_str, day_of_week = date.strftime("%Y-%m-%d"), date.strftime("%a")
        try:
            entry, _ = generate_data(resort, date)
            is_holiday_date, holiday_name, is_holiday_start = any(h_start <= date <= h_end for h_start, h_end in holiday_ranges), holiday_names.get(date), entry.get("HolidayWeekStart", False)
            for room in room_types:
                internal_room, is_ap_room = get_internal_room_key(room), room in ap_display_room_types
                points = entry.get(room, 0)
                discounted_points = math.floor(points * discount_multiplier)
                if is_holiday_date and not is_ap_room:
                    if is_holiday_start:
                        if holiday_name not in holiday_totals[room]:
                            h_start = min(h for h, _ in holiday_ranges if holiday_names.get(date) == holiday_name)
                            h_end = max(e for _, e in holiday_ranges if holiday_names.get(date) == holiday_name)
                            holiday_totals[room][holiday_name] = {"points": discounted_points, "start": h_start, "end": h_end}
                        start_str, end_str = holiday_totals[room][holiday_name]["start"].strftime("%b %d"), holiday_totals[room][holiday_name]["end"].strftime("%b %d, %Y")
                        row = {"Date": f"{holiday_name} ({start_str} - {end_str})", "Room Type": room, "Points": discounted_points}
                        if display_mode == "both" and len(cost_components) > 1:
                            maintenance_cost = math.ceil(discounted_points * rate_per_point) if "maintenance" in cost_components else 0
                            capital_cost = math.ceil(discounted_points * capital_cost_per_point * cost_of_capital) if "capital" in cost_components else 0
                            depreciation_cost = math.ceil(discounted_points * depreciation_cost_per_point) if "depreciation" in cost_components else 0
                            total_holiday_cost = maintenance_cost + capital_cost + depreciation_cost
                            row["Total Cost"] = f"${total_holiday_cost}"
                        compare_data.append(row)
                    continue
                row = {"Date": date_str, "Room Type": room, "Points": discounted_points}
                if display_mode == "both" and len(cost_components) > 1:
                    maintenance_cost = math.ceil(discounted_points * rate_per_point) if "maintenance" in cost_components else 0
                    capital_cost = math.ceil(discounted_points * capital_cost_per_point * cost_of_capital) if "capital" in cost_components else 0
                    depreciation_cost = math.ceil(discounted_points * depreciation_cost_per_point) if "depreciation" in cost_components else 0
                    total_day_cost = maintenance_cost + capital_cost + depreciation_cost
                    row["Total Cost"] = f"${total_day_cost}"
                    total_cost_by_room[room] += total_day_cost
                compare_data.append(row)
                total_points_by_room[room] += discounted_points
                chart_row = {"Date": date, "DateStr": date_str, "Day": day_of_week, "Room Type": room, "Points": discounted_points, "Holiday": entry.get("holiday_name", "No")}
                if display_mode == "both" and len(cost_components) > 1:
                    maintenance_cost = math.ceil(discounted_points * rate_per_point) if "maintenance" in cost_components else 0
                    capital_cost = math.ceil(discounted_points * capital_cost_per_point * cost_of_capital) if "capital" in cost_components else 0
                    depreciation_cost = math.ceil(discounted_points * depreciation_cost_per_point) if "depreciation" in cost_components else 0
                    total_day_cost = maintenance_cost + capital_cost + depreciation_cost
                    chart_row.update({"Total Cost": f"${total_day_cost}", "TotalCostValue": total_day_cost})
                chart_data.append(chart_row)
        except Exception as e:
            st.session_state.debug_messages.append(f"Error in compare for {date_str} at {resort}: {str(e)}")
    compare_data.extend([{"Date": "Total Points (Non-Holiday)", **{room: total_points_by_room[room] for room in room_types}}])
    if display_mode == "both" and len(cost_components) > 1:
        compare_data.append({"Date": "Total Cost (Non-Holiday)", **{room: f"${total_cost_by_room[room]}" for room in room_types}})
    compare_df, compare_df_pivot = pd.DataFrame(compare_data), pd.DataFrame(compare_data).pivot_table(index="Date", columns="Room Type", values=["Points"] if display_mode == "points" else ["Points", "Total Cost"], aggfunc="first").reset_index()
    compare_df_pivot.columns = ['Date'] + [f"{col[1]} {col[0]}" for col in compare_df_pivot.columns[1:]]
    return pd.DataFrame(chart_data), compare_df_pivot, holiday_totals

# Main UI
try:
    user_mode = st.sidebar.selectbox("User Mode", options=["Renter", "Owner"], index=0)
    rate_per_point = 0.81
    discount_percent, display_mode = 0, "both"
    capital_cost_per_point, cost_of_capital_percent, useful_life, salvage_value = 16.0, 7.0, 15, 3.0
    booking_discount, cost_components = None, ["maintenance", "capital", "depreciation"]

    st.title("Marriott Vacation Club " + ("Rent Calculator" if user_mode == "Renter" else "Cost Calculator"))

    with st.expander("\U0001F334 How " + ("Rent" if user_mode == "Renter" else "Cost") + " Is Calculated"):
        if user_mode == "Renter":
            st.markdown("""
            - Authored by Desmond Kwang https://www.facebook.com/dkwang62
            - Rental Rate per Point is based on MVC Abound maintenance fees or custom input
            - Default: $0.81 for 2025 stays (actual rate)
            - Default: $0.86 for 2026 stays (forecasted rate)
            - **Booked within 60 days**: 30% discount on points required, applies to stays within 60 days from today
            - **Booked within 30 days**: 25% discount on points required, applies to stays within 30 days from today
            - Rent = (Points × Discount Multiplier) × Rate per Point
            """)
        else:
            depreciation_per_point = (capital_cost_per_point - salvage_value) / useful_life if "depreciation" in cost_components else 0
            st.markdown(f"""
            - Authored by Desmond Kwang https://www.facebook.com/dkwang62
            - Maintenance rate: ${rate_per_point:.2f} per point
            - Purchase price: ${capital_cost_per_point:.2f} per point
            - Cost of capital: {cost_of_capital_percent:.1f}% (if capital selected)
            - Useful Life: {useful_life} years (if depreciation selected)
            - Salvage Value: ${salvage_value:.2f} per point (if depreciation selected)
            - Depreciation: ${depreciation_per_point:.2f} per point (if depreciation selected)
            - Selected discount: {discount_percent}%
            - Cost components: {', '.join(cost_components)}
            - Total cost is the sum of selected components (maintenance, capital, depreciation) (shown only if multiple components selected)
            """)

    checkin_date = st.date_input("Check-in Date", min_value=datetime(2025, 1, 3).date(), max_value=datetime(2026, 12, 31).date(), value=datetime(2025, 6, 12).date())
    num_nights = st.number_input("Number of Nights", min_value=1, max_value=30, value=7)
    checkout_date = checkin_date + timedelta(days=num_nights)
    st.write(f"Checkout Date: {checkout_date.strftime('%Y-%m-%d')}")

    with st.sidebar:
        st.header("Parameters")
        if user_mode == "Owner":
            display_options = [(0, "both"), (25, "both"), (30, "both"), (0, "points"), (25, "points"), (30, "points")]
            def format_discount(i): return f"{display_options[i][0]}% Discount ({'Presidential' if display_options[i][0] == 30 else 'Executive' if display_options[i][0] == 25 else 'Ordinary'}, {display_options[i][1]})"
            display_mode_select = st.selectbox("Display and Discount Settings", options=range(len(display_options)), format_func=format_discount, index=0)
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

    resort = st.selectbox("Select Resort", options=data["resorts_list"], index=data["resorts_list"].index("Ko Olina Beach Club"))
    year_select = str(checkin_date.year)

    if "last_resort" not in st.session_state or st.session_state.last_resort != resort or "last_year" not in st.session_state or st.session_state.last_year != year_select:
        st.session_state.data_cache.clear()
        if "room_types" in st.session_state: del st.session_state.room_types
        if "display_to_internal" in st.session_state: del st.session_state.display_to_internal
        st.session_state.last_resort, st.session_state.last_year = resort, year_select
        st.session_state.debug_messages.append(f"Cleared cache due to resort ({resort}) or year ({year_select}) change")

    if "room_types" not in st.session_state:
        sample_date = checkin_date
        st.session_state.debug_messages.append(f"Generating room types for {resort} on {sample_date}")
        sample_entry, display_to_internal = generate_data(resort, sample_date)
        room_types = sorted([k for k in sample_entry if k not in ["HolidayWeek", "HolidayWeekStart", "holiday_name", "holiday_start", "holiday_end"]])
        if not room_types:
            st.error(f"No room types found for {resort}. Ensure reference_points data is available.")
            st.session_state.debug_messages.append(f"No room types for {resort}")
            st.stop()
        st.session_state.room_types, st.session_state.display_to_internal = room_types, display_to_internal
        st.session_state.debug_messages.append(f"Room types for {resort}: {room_types}")
    else:
        room_types, display_to_internal = st.session_state.room_types, st.session_state.display_to_internal

    room_type = st.selectbox("Select Room Type", options=room_types, key="room_type_select")
    compare_rooms = st.multiselect("Compare With Other Room Types", options=[r for r in room_types if r != room_type])

    original_checkin_date = checkin_date
    checkin_date, adjusted_nights, was_adjusted = adjust_date_range(resort, checkin_date, num_nights)
    if was_adjusted:
        st.info(f"Date range adjusted to include full holiday week: {checkin_date.strftime('%Y-%m-%d')} to {(checkin_date + timedelta(days=adjusted_nights - 1)).strftime('%Y-%m-%d')} ({adjusted_nights} nights).")
    st.session_state.last_checkin_date = checkin_date

    reference_entry, _ = generate_data(resort, checkin_date)
    reference_points_resort = {k: v for k, v in reference_entry.items() if k not in ["HolidayWeek", "HolidayWeekStart", "holiday_name", "holiday_start", "holiday_end"]}
    ap_room_types, ap_display_room_types = [], []
    if resort == "Ko Olina Beach Club" and "AP Rooms" in reference_points.get(resort, {}):
        ap_room_types = list(reference_points[resort]["AP Rooms"].get("Fri-Sat", {}).keys())
        ap_display_room_types = [get_display_room_type(rt) for rt in ap_room_types]

    if st.button("Calculate"):
        st.session_state.debug_messages.append("Starting new calculation...")
        if user_mode == "Renter":
            breakdown, total_points, total_rent = calculate_stay_renter(resort, room_type, checkin_date, adjusted_nights, rate_per_point, booking_discount)
            st.subheader("Stay Breakdown")
            if not breakdown.empty:
                st.dataframe(breakdown, use_container_width=True)
            else:
                st.error("No data available for the selected period.")
            st.success(f"Total Points Used: {total_points}")
            st.success(f"Estimated Total Rent: ${total_rent}" if total_rent > 0 else "Estimated Total Rent: $-")
            if not breakdown.empty:
                csv_data = breakdown.to_csv(index=False).encode('utf-8')
                st.download_button(label="Download Breakdown as CSV", data=csv_data, file_name=f"{resort}_stay_breakdown.csv", mime="text/csv")
            if compare_rooms:
                st.subheader("Room Type Comparison")
                st.info("Note: Non-holiday weeks are compared day-by-day; holiday weeks are compared as total points for the week.")
                all_rooms = [room_type] + compare_rooms
                chart_df, compare_df_pivot, holiday_totals = compare_room_types_renter(resort, all_rooms, checkin_date, adjusted_nights, rate_per_point, booking_discount)
                st.write("### Points and Rent Comparison")
                st.dataframe(compare_df_pivot, use_container_width=True)
                compare_csv = compare_df_pivot.to_csv(index=False).encode('utf-8')
                st.download_button(label="Download Room Comparison as CSV", data=compare_csv, file_name=f"{resort}_room_comparison.csv", mime="text/csv")
                if not chart_df.empty:
                    non_holiday_df = chart_df[chart_df["Holiday"] == "No"]
                    holiday_data = []
                    for room in all_rooms:
                        for h_name, totals in holiday_totals[room].items():
                            if totals["points"] > 0:
                                holiday_data.append({"Holiday": h_name, "Room Type": room, "Points": totals["points"], "Rent": f"${totals['rent']}", "Start": totals["start"], "End": totals["end"]})
                    holiday_df = pd.DataFrame(holiday_data)
                    if not non_holiday_df.empty:
                        start_date, end_date = non_holiday_df["Date"].min(), non_holiday_df["Date"].max()
                        title = f"Points Comparison (Non-Holiday, {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')})"
                        st.subheader(title)
                        day_order = ["Fri", "Sat", "Sun", "Mon", "Tue", "Wed", "Thu"]
                        fig = px.bar(non_holiday_df, x="Day", y="Points", color="Room Type", barmode="group", title=title, labels={"Points": "Points", "Day": "Day of Week"}, height=600, text="Points", text_auto=True, category_orders={"Day": day_order})
                        fig.update_traces(texttemplate="%{text}", textposition="auto")
                        fig.update_xaxes(ticktext=day_order, tickvals=[0, 1, 2, 3, 4, 5, 6], tickmode="array")
                        fig.update_layout(legend_title_text="Room Type", bargap=0.2, bargroupgap=0.1)
                        st.plotly_chart(fig, use_container_width=True)
                    if not holiday_df.empty:
                        start_date, end_date = holiday_df["Start"].min(), holiday_df["End"].max()
                        title = f"Points Comparison (Holiday Weeks, {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')})"
                        st.subheader(title)
                        fig = px.bar(holiday_df, x="Holiday", y="Points", color="Room Type", barmode="group", title=title, labels={"Points": "Points", "Holiday": "Holiday Week"}, height=600, text="Points", text_auto=True)
                        fig.update_traces(texttemplate="%{text}", textposition="auto")
                        fig.update_layout(legend_title_text="Room Type", bargap=0.2, bargroupgap=0.1)
                        st.plotly_chart(fig, use_container_width=True)
        else:
            breakdown, total_points, total_cost, total_maintenance_cost, total_capital_cost, total_depreciation_cost = calculate_stay_owner(resort, room_type, checkin_date, adjusted_nights, discount_percent, discount_multiplier, display_mode, rate_per_point, capital_cost_per_point, cost_of_capital, useful_life, salvage_value, cost_components)
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
                st.download_button(label="Download Breakdown as CSV", data=csv_data, file_name=f"{resort}_stay_breakdown.csv", mime="text/csv")
            if compare_rooms:
                st.subheader("Room Type Comparison")
                st.info("Note: Non-holiday weeks are compared day-by-day; holiday weeks are compared as total points for the week.")
                all_rooms = [room_type] + compare_rooms
                chart_df, compare_df_pivot, holiday_totals = compare_room_types_owner(resort, all_rooms, checkin_date, adjusted_nights, discount_multiplier, discount_percent, ap_display_room_types, display_mode, rate_per_point, capital_cost_per_point, cost_of_capital, useful_life, salvage_value, cost_components)
                display_columns = ["Date"] + [col for col in compare_df_pivot.columns if "Points" in col or (display_mode == "both" and "Total Cost" in col)]
                st.write(f"### {'Points' if display_mode == 'points' else 'Points and Total Cost'} Comparison")
                st.dataframe(compare_df_pivot[display_columns], use_container_width=True)
                compare_csv = compare_df_pivot.to_csv(index=False).encode('utf-8')
                st.download_button(label="Download Room Comparison as CSV", data=compare_csv, file_name=f"{resort}_room_comparison.csv", mime="text/csv")
                if not chart_df.empty:
                    required_columns = ["Date", "Room Type", "Points", "Holiday"]
                    if display_mode == "both":
                        required_columns.extend(["Total Cost", "TotalCostValue"])
                    if all(col in chart_df.columns for col in required_columns):
                        non_holiday_df = chart_df[chart_df["Holiday"] == "No"]
                        holiday_data = []
                        for room in all_rooms:
                            for h_name, totals in holiday_totals[room].items():
                                if totals["points"] > 0:
                                    row = {"Holiday": h_name, "Room Type": room, "Points": totals["points"], "Start": totals["start"], "End": totals["end"]}
                                    if display_mode == "both" and len(cost_components) > 1:
                                        maintenance_cost = math.ceil(totals["points"] * rate_per_point) if "maintenance" in cost_components else 0
                                        capital_cost = math.ceil(totals["points"] * capital_cost_per_point * cost_of_capital) if "capital" in cost_components else 0
                                        depreciation_cost = math.ceil(totals["points"] * ((capital_cost_per_point - salvage_value) / useful_life)) if "depreciation" in cost_components else 0
                                        total_holiday_cost = maintenance_cost + capital_cost + depreciation_cost
                                        row.update({"Total Cost": f"${total_holiday_cost}", "TotalCostValue": total_holiday_cost})
                                    holiday_data.append(row)
                        holiday_df = pd.DataFrame(holiday_data)
                        if not non_holiday_df.empty:
                            start_date, end_date = non_holiday_df["Date"].min(), non_holiday_df["Date"].max()
                            title = f"Points Comparison (Non-Holiday, {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')})"
                            st.subheader(title)
                            day_order = ["Fri", "Sat", "Sun", "Mon", "Tue", "Wed", "Thu"]
                            fig = px.bar(non_holiday_df, x="Day", y="Points", color="Room Type", barmode="group", title=title, labels={"Points": "Points", "Day": "Day of Week"}, height=600, text="Points", text_auto=True, category_orders={"Day": day_order})
                            fig.update_traces(texttemplate="%{text}", textposition="auto")
                            fig.update_xaxes(ticktext=day_order, tickvals=[0, 1, 2, 3, 4, 5, 6], tickmode="array")
                            fig.update_layout(legend_title_text="Room Type", bargap=0.2, bargroupgap=0.1)
                            st.plotly_chart(fig, use_container_width=True)
                        if not holiday_df.empty:
                            start_date, end_date = holiday_df["Start"].min(), holiday_df["End"].max()
                            title = f"Points Comparison (Holiday Weeks, {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')})"
                            st.subheader(title)
                            fig = px.bar(holiday_df, x="Holiday", y="Points", color="Room Type", barmode="group", title=title, labels={"Points": "Points", "Holiday": "Holiday Week"}, height=600, text="Points", text_auto=True)
                            fig.update_traces(texttemplate="%{text}", textposition="auto")
                            fig.update_layout(legend_title_text="Room Type", bargap=0.2, bargroupgap=0.1)
                            st.plotly_chart(fig, use_container_width=True)

    st.subheader(f"Season and Holiday Calendar for {year_select}")
    gantt_fig = create_gantt_chart(resort, int(year_select))
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
