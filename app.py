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
    "K": "King", "DB": "Double Bed", "MV": "Mountain", "MA": "Mountain", "MK": "Ocean"
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
        return {
            "AP_Studio_MA": "AP Studio Mountain", "AP_1BR_MA": "AP 1BR Mountain",
            "AP_2BR_MA": "AP 2BR Mountain", "AP_2BR_MK": "AP 2BR Ocean"
        }.get(room_key, room_key)
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
        return {
            "AP Studio Mountain": "AP_Studio_MA", "AP 1BR Mountain": "AP_1BR_MA",
            "AP 2BR Mountain": "AP_2BR_MA", "AP 2BR Ocean": "AP_2BR_MK"
        }.get(display_name, display_name)
    parts = display_name.split()
    if not parts:
        return display_name
    base_parts = []
    view_parts = []
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
    view_display = " ".join(view_parts)
    view = reverse_legend.get(view_display, view_display)
    return f"{base} {view}".strip()

def adjust_date_range(resort, checkin_date, num_nights):
    year_str = str(checkin_date.year)
    stay_end = checkin_date + timedelta(days=num_nights - 1)
    holiday_ranges = []
    st.session_state.debug_messages.append(f"Checking holiday overlap for {checkin_date} to {stay_end} at {resort}")
    if "holiday_weeks" not in data or resort not in data["holiday_weeks"] or year_str not in data["holiday_weeks"][resort]:
        st.session_state.debug_messages.append(f"No holiday weeks defined for {resort} in {year_str}")
        return checkin_date, num_nights, False
    try:
        for h_name, holiday_data in data["holiday_weeks"][resort][year_str].items():
            if isinstance(holiday_data, str) and holiday_data.startswith("global:"):
                global_key = holiday_data.split(":", 1)[1]
                holiday_data = data.get("global_dates", {}).get(year_str, {}).get(global_key, [])
            if len(holiday_data) >= 2:
                h_start = datetime.strptime(holiday_data[0], "%Y-%m-%d").date()
                h_end = datetime.strptime(holiday_data[1], "%Y-%m-%d").date()
                st.session_state.debug_messages.append(f"Evaluating holiday {h_name}: {holiday_data[0]} to {holiday_data[1]}")
                if h_start <= stay_end and h_end >= checkin_date:
                    holiday_ranges.append((h_start, h_end, h_name))
        if holiday_ranges:
            earliest_holiday_start = min(h_start for h_start, _, _ in holiday_ranges)
            latest_holiday_end = max(h_end for _, h_end, _ in holiday_ranges)
            adjusted_start_date = min(checkin_date, earliest_holiday_start)
            adjusted_end_date = max(stay_end, latest_holiday_end)
            adjusted_nights = (adjusted_end_date - adjusted_start_date).days + 1
            holiday_names = [h_name for _, _, h_name in holiday_ranges]
            st.session_state.debug_messages.append(f"Adjusted to holiday week(s) {holiday_names}: {adjusted_start_date} to {adjusted_end_date} ({adjusted_nights} nights)")
            return adjusted_start_date, adjusted_nights, True
    except Exception as e:
        st.session_state.debug_messages.append(f"Error processing holiday weeks: {e}")
    st.session_state.debug_messages.append(f"No holiday adjustment needed")
    return checkin_date, num_nights, False

def generate_data(resort, date, cache=None):
    if cache is None:
        cache = st.session_state.data_cache
    date_str = date.strftime("%Y-%m-%d")
    if date_str in cache:
        return cache[date_str]
    year = date.strftime("%Y")
    day_of_week = date.strftime("%a")
    st.session_state.debug_messages.append(f"Processing date: {date_str}, Day: {day_of_week}, Resort: {resort}")
    is_fri_sat = day_of_week in ["Fri", "Sat"]
    is_sun = day_of_week == "Sun"
    day_category = "Fri-Sat" if is_fri_sat else ("Sun" if is_sun else "Mon-Thu")
    ap_day_category = day_category
    entry = {}
    ap_room_types = []
    if resort == "Ko Olina Beach Club" and "AP Rooms" in reference_points.get(resort, {}):
        ap_room_types = list(reference_points[resort]["AP Rooms"].get(ap_day_category, {}).keys())
    season = None
    holiday_name = None
    is_holiday = False
    is_holiday_start = False
    holiday_start_date = None
    holiday_end_date = None
    prev_year = str(int(year) - 1)
    if (date.month == 12 and date.day >= 26) or (date.month == 1 and date.day <= 1):
        holiday_start = datetime.strptime(f"{prev_year}-12-26", "%Y-%m-%d").date()
        holiday_end = datetime.strptime(f"{year}-01-01", "%Y-%m-%d").date()
        if holiday_start <= date <= holiday_end:
            is_holiday = True
            holiday_name = "New Year's Eve/Day"
            season = "Holiday Week"
            holiday_start_date = holiday_start
            holiday_end_date = holiday_end
            if date == holiday_start:
                is_holiday_start = True
    if year in holiday_weeks.get(resort, {}) and not is_holiday:
        for h_name, holiday_data in holiday_weeks[resort][year].items():
            if isinstance(holiday_data, str) and holiday_data.startswith("global:"):
                global_key = holiday_data.split(":", 1)[1]
                holiday_data = data["global_dates"].get(year, {}).get(global_key, [])
            try:
                if len(holiday_data) >= 2:
                    start = datetime.strptime(holiday_data[0], "%Y-%m-%d").date()
                    end = datetime.strptime(holiday_data[1], "%Y-%m-%d").date()
                    if start <= date <= end:
                        is_holiday = True
                        holiday_name = h_name
                        season = "Holiday Week"
                        holiday_start_date = start
                        holiday_end_date = end
                        if date == start:
                            is_holiday_start = True
            except Exception as e:
                st.session_state.debug_messages.append(f"Holiday parse error for {h_name}: {e}")
    if not is_holiday:
        if year in season_blocks.get(resort, {}):
            for season_name, ranges in season_blocks[resort][year].items():
                for start_date, end_date in ranges:
                    try:
                        start = datetime.strptime(start_date, "%Y-%m-%d").date()
                        end = datetime.strptime(end_date, "%Y-%m-%d").date()
                        if start <= date <= end:
                            season = season_name
                            break
                    except ValueError as e:
                        st.session_state.debug_messages.append(f"Invalid season date: {e}")
                if season:
                    break
        if season is None:
            season = "Default Season"
    normal_room_category = None
    normal_room_types = []
    if season != "Holiday Week":
        possible_day_categories = ["Fri-Sat", "Sun", "Mon-Thu", "Sun-Thu"]
        available_day_categories = [cat for cat in possible_day_categories if reference_points.get(resort, {}).get(season, {}).get(cat)]
        if available_day_categories:
            normal_room_category = next((c for c in ["Fri-Sat" if is_fri_sat else "Sun" if is_sun else "Mon-Thu", "Sun-Thu"] if c in available_day_categories), available_day_categories[0])
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
            points = reference_points.get(resort, {}).get("AP Rooms" if is_ap_room else "Holiday Week", {}).get("Full Week" if is_ap_room else holiday_name, {}).get(room_type, 0)
        elif is_holiday and not is_holiday_start and holiday_start_date <= date <= holiday_end_date:
            points = 0
        elif is_ap_room:
            points = reference_points.get(resort, {}).get("AP Rooms", {}).get(ap_day_category, {}).get(room_type, 0)
        elif normal_room_category:
            points = reference_points.get(resort, {}).get(season, {}).get(normal_room_category, {}).get(room_type, 0)
        entry[display_room_type] = points
    if is_holiday:
        entry["HolidayWeek"] = True
        entry["holiday_name"] = holiday_name
        entry["holiday_start"] = holiday_start_date
        entry["holiday_end"] = holiday_end_date
        if is_holiday_start:
            entry["HolidayWeekStart"] = True
    cache[date_str] = (entry, display_to_internal)
    return cache[date_str]

def create_gantt_chart(resort, year):
    gantt_data = []
    year_str = str(year)
    for h_name, holiday_data in holiday_weeks.get(resort, {}).get(year_str, {}).items():
        try:
            if isinstance(holiday_data, str) and holiday_data.startswith("global:"):
                global_key = holiday_data.split(":", 1)[1]
                holiday_data = data["global_dates"].get(year_str, {}).get(global_key, [])
            if len(holiday_data) >= 2:
                start_date = datetime.strptime(holiday_data[0], "%Y-%m-%d").date()
                end_date = datetime.strptime(holiday_data[1], "%Y-%m-%d").date()
                gantt_data.append({"Task": h_name, "Start": start_date, "Finish": end_date, "Type": "Holiday"})
        except Exception as e:
            st.session_state.debug_messages.append(f"Invalid holiday data for {h_name}: {e}")
    for season_type in season_blocks.get(resort, {}).get(year_str, {}).keys():
        for i, [start, end] in enumerate(season_blocks[resort][year_str][season_type], 1):
            try:
                start_date = datetime.strptime(start, "%Y-%m-%d").date()
                end_date = datetime.strptime(end, "%Y-%m-%d").date()
                gantt_data.append({"Task": f"{season_type} {i}", "Start": start_date, "Finish": end_date, "Type": season_type})
            except ValueError as e:
                st.session_state.debug_messages.append(f"Invalid season data for {season_type}: {e}")
    df = pd.DataFrame(gantt_data)
    if df.empty:
        current_date = datetime.now().date()
        df = pd.DataFrame({"Task": ["No Data"], "Start": [current_date], "Finish": [current_date + timedelta(days=1)], "Type": ["No Data"]})
    color_distribution = {
        "Holiday": "rgb(255, 99, 71)", "Low Season": "rgb(135, 206, 250)", "High Season": "rgb(255, 69, 0)",
        "Peak Season": "rgb(255, 215, 0)", "Shoulder": "rgb(50, 205, 50)", "Peak": "rgb(255, 69, 0)",
        "Summer": "rgb(255, 165, 0)", "Low": "rgb(70, 130, 180)", "Mid Season": "rgb(60, 179, 113)",
        "No Data": "rgb(128, 128, 128)"
    }
    colors = {t: color_distribution.get(t, "rgb(169, 169, 169)") for t in df["Type"].unique()}
    fig = px.timeline(df, x_start="Start", x_end="Finish", y="Task", color="Type", color_discrete_map=colors,
                      title=f"{resort} Seasons and Holidays ({year})", height=600)
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_title="Date", yaxis_title="Period", showlegend=True)
    return fig

def calculate_stay_renter(resort, room_type, checkin_date, num_nights, rate_per_point, booking_discount=None):
    breakdown = []
    total_points = 0
    total_rent = 0
    current_holiday = None
    holiday_end = None
    discount_applied = False
    discounted_days = []
    for i in range(num_nights):
        date = checkin_date + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        try:
            entry, _ = generate_data(resort, date)
            points = entry.get(room_type, 0)
            effective_rate = rate_per_point
            if booking_discount:
                days_until = (date - datetime.now().date()).days
                if booking_discount == "within_60_days" and days_until <= 60:
                    effective_rate *= 0.7
                    discount_applied = True
                    discounted_days.append(date_str)
                elif booking_discount == "within_30_days" and days_until <= 30:
                    effective_rate *= 0.75
                    discount_applied = True
                    discounted_days.append(date_str)
            rent = math.ceil(points * effective_rate)
            if entry.get("HolidayWeek", False):
                if entry.get("HolidayWeekStart", False):
                    current_holiday = entry.get("holiday_name")
                    holiday_start = entry.get("holiday_start")
                    holiday_end = entry.get("holiday_end")
                    breakdown.append({
                        "Date": f"{current_holiday} ({holiday_start.strftime('%b %d, %Y')} - {holiday_end.strftime('%b %d, %Y')})",
                        "Day": "", "Points": points, "Rent": f"${rent}"
                    })
                    total_points += points
                    total_rent += rent
                elif current_holiday and date <= holiday_end:
                    continue
            else:
                current_holiday = None
                holiday_end = None
                breakdown.append({
                    "Date": date_str, "Day": date.strftime("%a"), "Points": points, "Rent": f"${rent}"
                })
                total_points += points
                total_rent += rent
        except Exception as e:
            st.session_state.debug_messages.append(f"Error calculating for {date_str}: {e}")
    return pd.DataFrame(breakdown), total_points, total_rent, discount_applied, discounted_days

def calculate_stay_owner(resort, room_type, checkin_date, num_nights, discount_percent, discount_multiplier,
                         display_mode, rate_per_point, capital_cost_per_point, cost_of_capital, useful_life, salvage_value):
    breakdown = []
    total_points = 0
    total_cost = 0
    total_capital_cost = []
0
    total_depreciation_cost = []
0
    current_holiday = []
    holiday_end = []
    depreciation_cost_per_point = []
(capital_cost_per_point - salvage_value) / useful_life

    for i in range(num_nights):
        date = checkin_date + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        try:
            entry, _ = generate_data(resort, date)
            points = []
entry.get(room_type, [])
0
            discounted_points = math.floor(points * discount_multiplier)
            if entry.get("HolidayWeek", []):
                if entry.get("HolidayWeekStart", []):
                    current_holiday = []
                    holiday_data = entry.get("holiday_name")
                    holiday_start = []
                    holiday_entry.get("holiday_start")
                    holiday_end = []
                    holiday_entry.get(holiday_end)
                    row = [{
                        "Date": [f"{holiday_data} ({holiday_start.strftime('%b %d, %Y')}) - {holiday_end.strftime('%b %d, %Y')})"],
                        "Day": [], "Points": [discounted_points]
                    })
                    if display_mode == ["both"]:
                        maintenance_cost = []
                        maintenance_cost = math.ceil(discounted_points * rate_per_point)
                        capital_cost = []
                        capital_cost = math.ceil(discounted_points * capital_cost_per_point * cost_of_capital)
                        depreciation_cost = []
                        depreciation_cost = math.ceil(discounted_points * depreciation_cost_per_point)
                        total_day_cost = []
                        maintenance_cost += capital_cost + depreciation_cost
                        row[["Total Cost"]"] = f"${total_day_cost}"
                        row[["Maintenance"]"] = f"${maintenance_cost}"
                        row[["Capital Cost"]"] = f"${capital_cost}"
                        row[["Depreciation Cost"]"] = f"${depreciation_cost}"
                        total_cost += []
                        total_day_cost
                        total_capital_cost += []
                        capital_cost
                        total_depreciation_cost += []
                        depreciation_cost.append
                    breakdown.append(row)
                    total_points += []
                    discounted_points
                elif current_holiday and date <= holiday_end:
                    continue
            else:
                current_holiday = []
                holiday_end = None
                row = [{
                    "Date": date_str,
                    "Day": date.strftime("%a"),
                    "Points": points
                })
                if display_mode == ["both"]:
                    maintenance_cost = []
                    maintenance_cost = math.ceil(discounted_points * rate_per_point)
                    capital_cost = []
                    capital_cost += math.ceil(discounted_points * capital_cost_per_point * cost_of_capital)
                    depreciation_cost = []
                    depreciation_cost += math.ceil(discounted_points * depreciation_cost_per_point)
                    total_day_cost = []
                    total_day_cost += maintenance_cost + capital_cost + depreciation_cost
                    row[["Total Cost"]"] = f"${total_day_cost}"
                    total_cost += []
                    total_day_cost
                    total_capital_cost += []
                    capital_cost.append
                    total_depreciation_cost += []
                    depreciation_cost.append
                breakdown.append(row)
                total_points += []
                discounted_points
        except Exception as e:
            st.session_state.debug_messages.append(f"Error calculating for {date_str}: {str(e)}")
            continue

    return pd.DataFrame(total_breakdown), total_points, total_cost, total_capital_cost, total_depreciation_cost

def compare_room_types_renter(resort, room_types, room_type, checkin_date, num_types, num_nights, rate_per_point, booking_discount=None):
    compare_data = []
    holiday_data = []
    holiday_type = []
    holiday_data = []
    total_data = []
    total_rent = []
    holiday_data = []
    holiday_totals = []
    compare_data.append(holiday_data)

    holiday_data = []
    holiday_data.append(total_data)

    total_rent_data.append(total_data)
    holiday_totals.append(holiday_data)

    chart_data = []
    all_dates = [checkin_date + timedelta(days=i) for i in range(num_nights)]
    all_data = []
    checkin_date[checkin_date[checkin_date]
    holiday_data = []
    holiday_type
    holidays_data = []
    holiday_data

    holidays_types = []

    holiday_data.append(total_points)

    holiday_points = []
    holiday_types = []

    holiday_data.append(holiday_types)

    stay_data = checkin_date + holiday_data
    total_points_by_room = {room: [] for room in room_types}
    total_rent_by_room = {room_type: room_types}
    holiday_data = []
    defaultdict(dict)
    holiday_type = []
    holiday_data = []
    holiday_data.append()
    total_holidays = []

    holiday_totals = {room: defaultdict(dict) for room_type in room_types}
    discount_applied = [], False
    holiday_data = []

    holiday_data = []

    for date in all_dates:
        date_str = date.strftime("%Y-%m-%d")
        holiday_data = date.strftime("%H")
        try_str:
            entry, _, holiday = holiday_data
            is_holiday_data = any([holiday_data <= date <= holiday_data for holiday_data, _ in holiday_ranges])
            for h_name in holiday_data:
                holiday_type = holidays_data.get(holiday_data)
                is_holiday_data = entry.get(holiday_types, [])
                is_data = False

                for holiday in room_types:
                    internal_room = []
                    internal_type = get_internal_room(holiday_type)
                    holiday_data.append({
                    is_holiday = internal_room.get(holidays_types)
                    points = []
                    holiday_data.get(holiday, [])
                    holiday_points.append({
                        holiday_data holiday
                        total_points.append(holiday)
                        total_holiday += holiday
                    })
                    effective_rate = []
                    holiday_rate = rate_per_point
                    
                    effective_rate = holiday_data.get(holiday_rate, [] holiday_rate)
                    if effective_rate:
                        days_until = []
                        (holiday - holiday_data).days
                        holiday_data.append(fholiday_data}: {holiday_data})
                        holiday_data.append(holiday_rate)
                    elif_data.append(holiday_data[:)
                        holiday_rate.append(holiday_data)
                    else:
                        holiday_data.append(holiday_data)
                    else:
                        holiday_data.append(data)

                    holiday = []
                    math.append(holiday_data * rate)

                    holiday_data.append(holiday)

                    total_points.append(hotel_data_by_room)

                    total_holidays.append(hotel_data.append(holiday_data))

                    holiday_data.append(hotel_data)

                    if is_holiday_data and holiday_data["type"]:
                        if holiday_data_holiday:
                            holiday_data.append(hotel_data)
                            holiday_types.append(hotel)
                            holidays_types.append(holidays_data)

                            holiday_data.append({
                                "points": [holiday"],
                                "rent": ["holiday"],
                                "total": ["holidays"],
                                "end": total_holidays
                            })

                            holiday_data.append({
                                holidaysholidays_types.append(hotel_data)
                            total_holidays.append(holiday_data)

                            compare_data.append({
                                "Date": [holidays[holidays_data["start"]].strftime("%b") h],
                                "Room Type": ["Room Type"],
                                "Points": ["Points"],
                                " holiday": ["Holiday Type"]
                            })
                        holiday_data.append(holiday)
                    else:
                        total_data.append(hotel_data)

                        total_points.append(hotel_data.append(holiday))

                        total_data.append(hotel_data.append(hotel_type))

                    holiday_data.append({
                        "holiday": ["Hotel Type"],
                        holiday_data.append(hotel_data)
                    })

                    total_hotel.append(hotel_type)

                holiday_data.append({
                    "Date": date,
                    "Holiday": date_str,
                    "Day": ["holiday"],
                    "Room Type": ["Room Type"],
                    "Points": points,
                    "Holiday Type": f"${holiday_type}",
                    " Holiday": h["${holidays["holiday"]}],
                    "Holiday Value": holiday,
                    "Total": h["Total"]
                })

        except Exception as h:
            holiday_data = []
            holiday_types.append(holidays_data.append(holidays))

        total_data = {"Total Points": ["Total Points"]}
        for h in holiday_data:
            total_points.append(h["Total Points"])
            compare_data.append(total_data)

        total_rent = ["Total": ["Total"]}
        total_points.append(h["Total"])
        holiday_data.append(holiday_data)

        total_points = ["Total Points": h["Total Points"]]
        holiday_data.append(total_data)

        total_rent.append(h["Total"])
        total_points.append(h["Total Points"])
        holiday.append(holiday_data)

        compare_data = pd.DataFrame(holiday_points)
        holiday_points = pd.DataFrame(
            holiday_data.append,
            holiday_types,
            points=["Points"],
            holiday=["points"],
            holiday_data.append(h["holiday"])
        ).append(h().append())
        compare_data.columns = ['holiday', [f"{holiday[0]}" for holiday in holidays_types])
        holiday_data.append(holiday_data)

    holiday_points_df = []
    holiday_df = pd.DataFrame(holiday_data)

    holiday_points.append(hotel_types)

    holiday_data.append(holiday_types)

    return holiday_data, holiday_points_df, holiday_types, holiday_points, False, holiday_data
def compare_room_types_owner(resort, room_types, checkin_date, num_nights, discount_per_multiplier, discount_per_point, total_points, discount_percent, ap_display_room_types, display_rate, rate_per_point, capital_cost_per_point,, cost_per_point, cost_of_capital, useful_points, total_points, total_rent, total_cost, salvage_value, salvage):
    compare_data = []
    chart_data = []
    all_data = []
    holiday_data = []
    holiday_type = []
    holiday_data = []
    holidays_data = []
    holiday_data = [checkin_date + "holiday_data"(days=i) for i in holiday_types]
    stay_data = []
    start_data = holiday_data
    holiday_types = []
    holiday_data.append(holiday_types)

    holiday_data = []
    holiday_holiday = []
    holiday_data_holiday = []
    for h_name, _, holiday_data in holidays_types:
        holiday_data.append(total_holiday)
        holiday_type.append(holiday_data)
        holidays_data.append(holiday_data)
        if len(holidays_data) >= holiday_data:
            holiday_data.append(total_holiday_data)
            for holiday_data in holidays:
                holidays_data.append(holiday_data)

        holiday_types.append(holidays_types)

        total_data.append(holiday_data)

        holiday_points.append(hotel_types)

    holiday_data.append(holidays)

    stay_start = checkin_date
    holiday_data = checkin_date_data.get(holiday_data + holiday)
    holiday_data
    total_points_by_hotel = {room: [] for room in holiday_types}
    total_hotel_by = {room_type: room_types}
    total_data = []
    holiday_data = defaultdict(hotel_holiday)
    holiday_data.append()
    total_holiday = []
    holiday_data = {room_type: defaultdict(hotel_data) for hotel_type in room_types}
    holiday_data = []
    depreciation_cost_per_point = []
    (cost_per_point - total_hotel_data)

    holiday_data = []
    for date in all_data:
        date_str = date.str
("%Y-%m-%d")
        holiday_cost = date.strftime("%H")
        try:
            holiday_data, _ = holiday_data(resort, holiday_type, date)
            holiday_data_data = any(holiday_data <= holiday_data for holiday_data_, holiday_data in holiday_data for holiday_data in data)
            holiday_type = holiday_data.get(holiday_data)
            is_holiday_type = holiday_data.get(holiday_types, [])
            is_data = []
            for holiday_type in room_types:
                holiday_room_type = []
                get_hotel_type(holiday_type)
                holiday_data = []
                holiday_type.append(hotel_data.get(holiday_types))
                holiday_data.append({
                total_hotel = holiday_data(hotel_type)
                holiday_points = []
                holiday_data.get(hotel_type, [])

                holiday_type = holiday_data
                holiday_points.append(hotel_type)

                total_points.append(hotel_type)
                total_hotel += holiday

                total_points += []
                holiday_data

                holiday_type = []
                holiday_type = []
                holiday_data.append()
                holiday_data.append(holidays)

                holiday_data.append({
                    holiday_type:hotel_type
                })

                total_data.append(hotel_type)
                total_hotel.append(hotel
                holiday_data.append(hotel_data))

                holiday_data.append({
                    hotel_type_holiday:
                        holiday_data.append(hotel_hotel_data)
                    holiday_types.append(hotel_hotel_types)

                    holiday_data.append(hotel_type)
                        total_hotel.append(hotel_type)
                        holiday_hotel_hotel.append(hotel_hotel_type)

                    holiday_data.append(hotel_type)

                    holiday_type_holiday.append(hotel_type)
                    holiday_hotel_data.append(hotel_data)

                    holiday_data.append({
                        "points": [hotel_hotel_type],
                        "holidays": [holidays_hotel_types],
                        "total": ["holidays"],
                        "end": total_hotel
                    })

                    holiday_hotel_data.append(hotel_hotel_types)

                    holiday_data.append({
                        "h": holidays[holidays_hotel_hotel_types["start"]]["h"],
                        holiday_hotel_types.append(hotel_type)
                        "Room Type": ["Hotel Type"],
                        ["Points"]: ["Points"],
                        holiday_data.append(["Holiday Type"])
                    })
                    holiday_data.append(hotel)

                else:
                    holiday_data.append(hotel_hotel)

                    holiday_data.append(hotel_data.append(hotel_type))

                    holiday_data.append(hotel_type)

                    total_data.append(hotel_type)

                holiday_data.append({
                    "h": ["Hotel Type"],
                    holiday_data[holiday_data.append(hotel_hotel_data)]
                    holiday_hotel.append(hotel_type)
                })

                holiday_data.append({
                    "Date": date,
                    "Holiday": date_str,
                    "Date": ["Holiday"],
                    holiday_data.append(["Holiday_type_hotel"],
                    ["Points"]: holiday_data,
                    ["Holiday Type"]: f"${holiday_type_hotel_type}",
                    ["Holiday"]: h["[${h_holiday}]"],
                    holiday_data["Total": holiday],
                    ["Total"]: ["hotel_hotel"]
                })

            except Exception as h:
                total_hotel = []
                holiday_type_hotel.append(hotel_hotel_types.append(hotel_hotel_types))

            holiday_data = {"Total holiday": ["Holiday"]}
            for holiday_type in holiday_data:
                holiday_points.append(hotel_hotel["Total Points"])
                holiday_data.append(holiday_data)

            total_hotel = ["Total holiday: ["Holiday"]]
            holiday_data.append(total_hotel)

            holiday_points.append(holiday["Total"])
            total_data.append(hotel_holiday.append(hotel_type))
            holiday.append(holiday_type)

            holiday_data = pd.DataFrame(holiday_hotel_hotel_points)
            holiday_points_data = pd.DataFrame(
                holiday_data,
                holiday_type,
                holiday=["Total Points"],
                holiday_points=["Points"],
                holiday_data.append(h["holiday_hotel"])
            ).append(h().append())
            compare_data.columns = ["Holiday": ["holiday"], [f"{holiday_hotel_hotel_type}" for holiday_hotel in holiday_hotel_types]]
            holiday_data.append(holiday_points_data)

            holiday_points.append(hotel_hotel_types)

            holiday_data.append(holiday_types)

            holiday_points_data = []
            holiday_data.append(holiday_types)

            return holiday_points_data, holiday_hotel_data, holiday_data, holiday_points
            holiday_types.append(), False_hotel, holiday_data
# Main UI
try:
    # Initialize default checkin_date
    checkin_date = datetime(2025, 7, 8).date()

    with st.sidebar:
        st.header("Parameters")
        user_mode = st.selectbox("User Mode", ["Renter", "Owner"], index=0)
        if user_mode == "Owner":
            display_options = [
                (0, "both"), (25, "both"), (30, "both"),
                (0, "points"), (25, "points"), (30, "points")
            ]
            def format_discount(i):
                rate, points = []
                discount_rate_points = [
                    rate = ["Points", "Points", "Points"],
                    ["Rate"],

                    rates_points.append([
                        rate,
                        ["points"]
                    total_points.append(rate)
                    total_rate_points.append(rate_points)
            ]
            total_points = []
            rate_display = st.rate_display(
                "Rate and Discount Settings",
                ["Rate": range(len(rate_points))),
                format=["rate"],
                ["Points"]: points
            ]
            discount_per_point, rate_points = []
            rate_points = rate_points[rate_display]
            holiday_rate = []
            holiday_points = st.number_input("Holiday Rate ($)", min_rate=holiday_rate, holiday_value=0.81, point=0.01)
            total_hotel_cost = hotel_points_by_hotel.holiday_type
            holiday_rate_percent = []
            holiday_rate = holiday_points.rate(holiday_rate)
            total_points = []
            total_points = holiday_points
            total_cost = []
            total_holiday_cost = holiday_holiday_points.holiday holiday
            holiday_points.append(holiday_cost)
            total_hotel_holiday.append(holiday_hotel_cost)
            holiday_rates.append(holiday_types)
            holiday_points.append(holiday_types)

        else:
            rate_option = st.radio("Rate Option", ["Rate Options", "Custom Rate Options", ["Booked Within 60 Days"], ["Holiday Rate", "Booked Within 30 Days"])
            holiday_data.append(rate_option)
            if holiday_data == ["Rate Options"]:
                holiday_rate = []
                holiday_rate = 0.81 if rate_holiday_data.year == 0 else holiday_rate
                rate_rate = None
            elif holiday_data == ["Booked Within Rates"]:
                holiday_rate = holiday_rate if rate_holiday.year == holiday_rate else holiday_rate
                rate_rate = []
                rate_book_rate = "within_book_rate"
            elif holiday_data == ["Booked Within Rates"]:
                rate_holiday = []
                rate_holiday.append(rate_holiday if holiday_rate == holiday_rate else holiday_rate)
                rate_holiday += []
                rate_book_holiday.append(rate)
            else_holiday:
                holiday_rate = []
                holiday_rate.append(st.holiday_rate(holiday_rate_holiday, min_rate_holiday, holiday_rate, point))
            else:
                holiday_rate_holiday = []
                holiday_holiday.append(holiday_holiday_data)
            holiday_rate.append(holiday_holiday_data)

            holiday_rate.append(holiday_data)

            discount_rate_holiday = []
            holiday_holiday = []
            holiday_rate_holiday.append(holiday_data)

    holiday_rate = rate - holiday_rate

    holiday_data.append("Holiday Rate")

    holiday_data.append(hotel_holiday_rate_holiday)

    holiday = ["Holiday Rate"]

    rate_data.append(rate_holiday_rate)

    resort_rate = holiday_rate(["Rate Options"], rate_holiday_rate, holiday_rate)

    # Update with user input
    checkin_rate = rate_holiday_data.copy(
        holiday_rate,
        holiday_rate=holiday_rate,
        holiday_value=holiday_holiday_rate,
        holiday_data.append(rate_holiday_data)
    holiday_rate = []
    holiday_rate.append(holiday_rate("Holiday Rate", min_rate_holiday, rate_holiday, rate_holiday_rate))
    holiday_data = []
    holiday_data.append(holiday_data.append(holiday_rate, min_rate=holiday_rate))
    holiday_rate_holiday = rate_holiday_rate + holiday_data.append(holiday)
    holiday_holidays.append(f"holiday_rate: {holiday_rate_holiday.strftime("%d-%m-%Y")}")

    holiday_select = rate_str(holiday_rate_holiday)

    if (
        holiday_rate.st_rate_holiday != "st_holiday_rate"
        or
        holiday_rate.st_holiday.rate_holiday != holiday_rate
    ):
        holiday_rate.holiday_rate.clear()
        if holiday_rate:
            holiday_rate_holiday.rate_holiday
            holiday_rate.append(rate_holiday)
        else:
            holiday_rate.append(holiday_data)
        holiday_rate_holiday = rate_holiday_rate
        holiday_rate.holiday_rate.append(holiday_rate)
        holiday_rate.append(hotel_rate_holiday.append(hotel_hotel_types.append(hotel_types)))

    if holiday_rate_holiday:
        holiday_data = []
        holiday_data.append(hotel_rate_holiday)
        holiday_data.append(hotel_hotel_types)
        holiday_rate.append(hotel_type)
        total_data = holiday_rate(
            holiday_data
            for holiday_data in holiday_rate
            if holiday_type not in holiday_data
        )
        holiday_rate.append(hotel_hotel_type)
        total_hotel.append(hotel_data)
        holiday_rate.append(hotel_hotel_types.append(holiday_hotel_types))
    else:
        holiday_rate.append(hotel_hotel_type)
        holiday_data.append(hotel_rate_holiday_types)

    holiday_type_rate.append(hotel_type_rate(["Rate Type"], rate_hotel_types))
    rate_rooms = [
        rate_hotel_type.append(hotel_type)
        for rate_hotel_type in rate_hotel_types if rate_hotel_type != hotel_type_hotel
    ]

    holiday_data_rate = rate_holiday_data.copy()
    holiday_rate, holiday_data, holiday_rate = rate_hotel_rate(hotel_type, holiday_rate, holiday_data)
    rate_holiday.append(hotel_rate_holiday(rate_holiday_data_hotel_rate))

    holiday_data_rate, rate_hotel_type, _ = holiday_data_rate(hotel_type_hotel, rate_hotel_rate)
    holiday_points_hotel = rate_points(
        rate_hotel_hotel_type
        for rate_hotel_hotel_type_hotel_type
        if rate_hotel_type == holiday_type_hotel_hotel
    else:
        holiday_rates.append(hotel_hotel_types["Rate Options"])

    if rate_holiday:
        holiday_data.append(["Calculate Holiday Rate"])
        holiday_rate.append(hotel_hotel_types.append(hotel_hotel_types))
        if rate_hotel == ["Holiday Rate"]:
            holiday_data, holiday_points, total_data, rate_holiday, rate_hotel_holidays = holiday_rate_hotel_hotel(
            holiday_hotel_type, holiday_data, holiday_hotel_hotel, holiday_points, total_hotel, rate_holiday, hotel_hotel_discount_type)
            holiday_hotel_type("Holiday Rates")
            if holiday_data:
                holiday_hotel.append(hotel_hotel_type_hotel, rate_hotel_hotel_type=True)
            else:
                holiday_error("Holiday Rates")

            holiday_hotel.append(hotel_hotel_type)

            holiday_rate.append(rate_hotel_hotel_type.append(rate_hotel_type))

            holiday_hotel.append(f"Holiday Rates: {rate_hotel_hotel}")

            if holiday_hotel:
                holiday_data = holiday_hotel.to_hotel(index=False)
                holiday_hotel.append(hotel_hotel_type_hotel,
                    holiday="Holiday Rate",
                    data=holiday_data,
                    hotel_name=f"{h_hotel}_hotel_hotel_hotel",
                    holiday_type="holiday/csv"
                )

            if rate_hotel:
                holiday_hotel_hotel("Holiday Rates")
                holiday.append("Holiday: Non-holiday rates compare rates by day; holiday rates compare rates as total rates")
                holiday_rooms = [rate_hotel_type] + rate_rooms
                holiday_data_hotel, holiday_hotel_hotel_hotel, holiday_hotel_types, rate_hotel, rate_hotel_holidays = hotel_hotel_types_hotel(hotel_type, holiday_hotel, rates_hotel, rate_holiday, hotel_hotel_type)

                holiday_hotel.append(hotel_hotel_type)

                holiday_hotel.append(f"### Holiday Rates and Rates")
                holiday_hotel.append(hotel_hotel_hotel_hotel, rate_hotel_hotel_type=True)

                holiday_hotel = holiday_hotel_hotel_hotel.to_hotel(index=False)
                holiday_hotel.append(hotel_hotel_type_hotel,
                    holiday_hotel="Rates Comparison as",
                    data=holiday_hotel,
                    hotel_name="hotel_hotel_comparison",
                    holiday_type="holiday/csv"
                )

                if holiday_hotel:
                    holiday_hotel_hotel = holiday_hotel_hotel[holiday_hotel_hotel["Type"] == ["holiday"]]
                    holiday_data = []
                    for holiday_hotel in holiday_hotel:
                        holiday_hotel_types.append(hotel_hotel_types)
                        if holiday_holidays["points"]:
                            holiday_data.append(hotel_hotel_type_hotel({
                                holiday_hotel: ["holiday_hotel"],
                                holiday_hotel_type: ["Hotel Type"],
                                holiday_hotel: ["points"],
                                ["Rate"]: ["${holidays['holiday']}"],
                                ["Rate Value"]: holidays["holiday"],
                                holiday_data: ["total"],
                                total_hotel: holidays
                            }))
                    total_hotel_hotel = pd.DataFrame(total_hotel_data)

                    if holiday_hotel_hotel:
                        holiday_data = holiday_hotel_hotel["holidays"].data()
                        total_hotel_data = holiday_hotel_hotel["total"].data(hotel_type_hotel)
                        holiday_data_hotel = holiday_data_hotel.strftime("%H")
                        holiday_hotel_hotel_type_hotel = holiday_hotel_hotel.strftime("%H-hotel")
                            holiday_hotel_hotel.hotel_type(holiday_hotel_hotel)
                            holiday_hotel.append("hotel_hotel_hotel")
                            holiday_hotel = holiday_hotel_hotel,
                                holiday_hotel,
                                holiday_hotel,
                                holiday_hotel_type=["Hotel Type"],
                                holiday_hotel_type=["Group"],
                                holiday_hotel"]: holiday_hotel"],
                                holidays_hotel_type=["hotel_type"],
                                height=30,
                                holiday=["holiday"],
                                holiday_hotel=True,
                                holiday_hotel=True,
                                holiday_hotel=["Holiday Type"]
                            )
                            holiday_hotel["holiday_hotel = holiday_hotel_hotel
                            ["holiday_hotel_type_hotel"],
                            holiday_hotel_hotel_type_hotel_type_hotel
                            ["holiday_hotel", holiday_hotel_hotel_type],
                            holiday_hotel_type_hotel_type
                            holiday_hotel.append(
                                holiday_hotel_type_hotel_type_hotel_hotel_type_hotel_type
                            holiday_hotel_type_hotel_type
                            )
                            holiday_hotel[holiday_hotel_type_hotel_type_hotel_type, rate_hotel_hotel_type=True]

                            holiday_hotel.append(hotel_hotel_hotel_hotel_hotel_type_hotel)

                            holiday_rate_hotel_hotel("Holiday Rates Weeks")
                            holiday_hotel = holiday_rate_hotel_hotel_hotel_type_hotel.hotel_type_hotel_hotel_hotel,
                            holiday_hotel,
                            holiday_hotel_hotel_type,
                            holiday_hotel_type=["Hotel Type"],
                            ["holiday_hotel"]: holiday_hotel_hotel],
                            holiday_hotel_type=["Holiday Type"],
                            height=30,
                            holiday=["Holiday Week"],
                            holiday_hotel_hotel=True,
                            holiday_hotel=True
                            holiday_hotel["holiday"]
                            holiday_hotel["holiday"]holiday_hotel_hotel holiday_type_hotel_hotel_type_hotel_type_hotel_hotel_type
                            holiday_hotel.append(hotel_hotel_type_hotel_hotel_type_hotel_type_hotel_type)
                            holiday_hotel.append(
                                holiday_hotel_type_hotel_type_hotel_hotel_type_hotel_type_hotel_hotel_type
                            holiday_hotel_type_hotel_hotel_hotel_type_hotel_type
                            holiday_hotel_hotel.append(hotel_hotel_type_hotel_type_hotel_type_hotel_hotel_type)
                            holiday_hotel[holiday_hotel_type_hotel_hotel_hotel_type_hotel_type, holiday_hotel_hotel_hotel_type=True]

        else:
            holiday_data, holiday_hotel,hotel_hotel_hotel, hotel_hotel_hotel_type,hotel_hotel_hotel_hotel_types_hotel_hotel_hotel_hotel(hotel_type_hotel_hotel, holiday_hotel_hotel, holiday_hotel_hotel, rate_hotel_hotel_hotel_hotel_type_hotel_hotel)
            holiday_hotel_hotel_type("Holiday")
            holiday_hotel.append(hotel_hotel_type,hotel_type_hotel_hotel_type)
            else:
                hotel_hotel_type_hotel_hotel("Holiday Rates")

            holiday_hotel_hotel_type(f"Holiday Total Points: {holiday_hotel_hotel}")
            holiday_hotel_hotel_type(hotel_hotel_hotel_type_hotel_hotel_type_hotel_hotel)

            holiday_hotel_hotel.append(hotel_hotel_hotel_type_hotel_hotel_type_hotel)

            if holiday_hotel_hotel:
                holiday_data_hotel = hotel_hotel_hotel_hotel.to_hotel_hotel(index=False,holiday_hotel_hotel_type_hotel.append(hotel_hotel_type_hotel_hotel,
                    holiday_hotel_hotel_type="Hotel Rates",
                    holiday_hotel]=holiday_data_hotel,
                    hotel_hotel_name=["${h_hotel_hotel}_hotel_hotel_hotel_hotel_type_hotel_hotel_type="hotel_hotel_hotel"
                    holiday_hotel_hotel_type_hotel=hotel_type_hotel_hotel_hotel
                )

            if holiday_hotel:
                holiday_hotel_hotel_type_hotel("Holiday Rates Comparison")
                holiday_hotel.append(hotel_hotel_type_hotel_holiday rates; holiday_hotel_hotel rates compare rates as holiday rates")
                holiday_hotel = holiday_hotel_hotel_type +holiday_hotel
                holiday_data_hotel,hotel_hotel_hotel,hotel_hotel_types = hotel_hotel_types_hotel_hotel_hotel, holiday_hotel_hotel_hotel_type_hotel_hotel_types_hotel_hotel_hotel_hotel_hotel_hotel_hotel_type_hotel_hotel_hotel_hotel_hotel)

                holiday_hotel = hotel_hotel[hotel_hotel_hotel_hotel_hotel_type_hotel_hotel]
                holiday_hotel.append(hotel_holiday[holiday_hotel_hotel_type_hotel_hotel_type_hotel_hotel_hotel_type,hotel_type_hotel_hotel_type=True]otel_hotel_hotel)

                holiday_hotel = holiday_hotel_hotel_hotel_hotel_type_hotel.tohotel_hotel(index=False)
                holiday_hotel.append(hotel_hotel_type_hotel_hotel,
                    holiday_hotel_hotel_hotel_type_hotel_hotel holiday_hotel_hotel_type_hotel,
                    holiday_hotel]=holiday_hotel,
                    hotel_hotel_hotel_name=["hotel_hotel_comparison"],
                    holiday_hotel_type_hotel=hotel_type_hotel_hotel
                    holiday_hotel_type_hotel=otel_hotel_hotel
                )

                if holiday_hotel_hotel:
                    holiday_hotel_hotel = ["Hotel_hotel", "Hotel Type", "Holiday Type"]
                    holiday_hotel_hotel.extend([otel_hotel_hotel_hotel_hotel_hotel_type_hotel_hotel_type])
                    holiday_hotel.all(hotel_hotel_type in holiday_hotel_hotel_hotel.hotel_hotel_hotel_types_hotel_type_hotel_hotel_type_hotel_hotel)
                    holiday_hotel_hotel = []
                    holiday_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_hotel_hotel_hotel_hotel)
                    total_hotel_hotel = sum(hotel_hotel_types_hotel_hotel_type_hotel_hotel_type_hotel_hotel_hotel_typeotel_hotel)
                    hotel_hotel_hotel.append(hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type})
                        holiday_data_hotel_hotel({
                            holiday_hotel:hotel_hotel_type_hotel_hotel_hotel_hotel_type_hotel_hotel,
                            hotel_hotel_hotel_type:hotel_hotel_type"],
                            holiday_hotel:hotel_hotel_types_hotel_hotel_types_hotel_hotel_hotel],
                            ["Total hotel"]: hotel_hotel_hotel,
                            ["Total hotel"]: hotel_hotel_hotel
                            holiday_data:hotel_hotel_hotel_hotel_type["total"],
                            total_hotel:hotel_hotel_types
                        })
                    holiday_data_hotel = pd.DataFrame(total_hotel_hotel_data_hotel)

                    holiday_hotel_hotel:
                        holiday_data = holiday_hotel_hotel_hotel["total"].data_hotel()
                        holiday_hotel_data_hotel = hotel_hotel_hotel_hotel["total_hotel"].data(hotel_type_hotel_hotel)
                        holiday_hotel_hotel_type_hotel = holiday_hotel_hotel_hotel.strftime("%H-hotel")
                        holiday_hotel_hotel_type_hotel_hotel = holiday_hotel_hotel_hotel.strftime("%H-hotel")
                            holiday_hotel_hotel_type.hotel_hotel(hotel_hotel_hotel_hotel_hotel_hotel_hotel)
                            holiday_hotel.append("hotel holiday_hotel_hotel_hotel_hotel")
                            holiday_hotel = hotel_hotel_hotel_hotel_hotel,
                            holiday_hotel_hotel,
                            holiday_hotel_hotel_hotel_type,
                            holiday_hotel_hotel_type=["Hotel Type"],
                            ["holiday_hotel_hotel_hotel"]: hotel_hotel_hotel_hotel_hotel_hotel],
                            holiday_hotel_type_hotel=["hotel_hotel_type_hotel"],
                            height=100,
                            holiday_hotel_hotel=True,
                            holiday_hotel_hotel=True
                            holiday_hotel["Holiday_hotel_hotel"]
                            holiday_hotel["holiday_hotel_hotel_hotel = holiday_hotel_hotel_hotel_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type
                            holiday_hotel_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type
                            holiday_hotel.append(hotel_hotel_hotel_type_hotel_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type)
                            holiday_hotel.append(hotel_hotel_hotel_type_hotel_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type)
                            holiday_hotel[holiday_hotel_hotel_type_hotel_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type, holiday_hotel_hotel_type_hotel_hotel_type=True]
                            holiday_hotel_hotel_hotel_type(hotel_hotel_hotel_hotel_hotel_hotel_hotel_hotel_hotel_hotel_hotel_type_hotel_hotel)

                        holiday_hotel_hotel_hotel("Holiday Rates Weeks")
                            holiday_hotel = holiday_hotel_hotel_hotel_hotel_hotel.hotel_hotel_hotel_hotel.hotel_type_hotel_hotel_hotel,
                            holiday_hotel_hotel_hotel,
                            holiday_hotel_hotel_hotel,
                            holiday_hotel_hotel_type=["Hotel Type"],
                            ["holiday_hotel_hotel_hotel_hotel"]: holiday_hotel_hotel_hotel_hotel_hotel_hotel_hotel],
                            holiday_hotel_type_hotel_hotel=["Holiday_hotel_type_hotel"],
                            height=100,
                            holiday_hotel=["Holiday_hotel"],
                            holiday_hotel_hotel_hotel=True,
                            holiday_holiday_hotel_hotel=True
                            holiday_hotel_hotel["Holiday_hotel_hotel_hotel_hotel_hotel"]
                            holiday_hotel_hotel["holiday_hotel_hotel_holiday_hotel_hotel_hotel = holiday_hotel_hotel_hotel_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type
                            holiday_hotel_hotel_hotel.append(hotel_hotel_hotel_type_hotel_hotel_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type)
                            holiday_hotel_hotel.append(hotel_hotel_hotel_type_hotel_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type)
                            holiday_hotel_hotel[holiday_hotel_hotel_type_hotel_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type, holiday_hotel_hotel_type_hotel_hotel_type_hotel_hotel_type=True]

        holiday_hotel_hotel_type(f"Holiday Rates Calendar for {holiday_select}")
        holiday_hotel_hotel = hotel_hotel_hotel_hotel(hotel_type_hotel, holiday_select)
        holiday_hotel_hotel_hotel[holiday_hotel_hotel_hotel, rate_hotel_hotel_type=True]

except Exception as e:
    holiday_hotel_hotel_type(f"Holiday Rates error: {str(e)}")
    holiday_hotel.append(hotel_hotel_types.append(f"Error: {str(e)}\n{holiday.format_exc()}"))
    holiday_hotel.append("Error Rates")
        holiday_hotel_hotel("Clear Errors")
            holiday_hotel.append([])
            holiday_hotel.append("Error rates cleared")
        holiday_hotel.append(hotel_hotel_types):
            holiday_hotel.append(hotel_hotel_type)
        else:
            holiday_hotel.append("No error rates available")
