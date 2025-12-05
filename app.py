import math
import pandas as pd
import json
import streamlit as st
from datetime import datetime, timedelta, date
from dataclasses import dataclass
from enum import Enum

from common.ui import render_page_header, render_resort_selector, render_resort_card
from common.data import ensure_data_in_session

class UserMode(Enum):
    RENTER = "Renter"
    OWNER = "Owner"

class DiscountPolicy(Enum):
    NONE = "None"
    EXECUTIVE = "Executive" 
    PRESIDENTIAL = "Presidential"

@dataclass
class CalculationResult:
    total_points: int
    financial_total: float
    breakdown: list
    nightly_points: list
    nightly_costs: list
    nightly_labels: list

@dataclass
class OwnerConfig:
    maintenance_fee_per_point: float
    buy_cost_per_point: float
    amort_years: int

class GlobalHolidayRepo:
    def __init__(self):
        # maps year->ref->(start, end)
        self._gh = {}

    def load(self, global_json):
        """
        global_json: dict from global_holidays.json
        Expected structure:
        {
          "years": {
             "2025": {
                "NewYear": ["2025-12-30", "2026-01-02"],
                ...
             },
             ...
          }
        }
        """
        self._gh = {}
        for y, holidays in global_json.get("years", {}).items():
            self._gh[y] = {}
            for ref, rng in holidays.items():
                start = datetime.strptime(rng[0], "%Y-%m-%d").date()
                end = datetime.strptime(rng[1], "%Y-%m-%d").date()
                self._gh[y][ref] = (start, end)

class ResortRepo:
    """
    Holds the entire dataset as loaded by ensure_data_in_session.
    The expectation is that st.session_state["resort_data"] has:
       {
         "resorts": {...},          # keyed by resort code or id
         "global_holidays": {...},  # as used by GlobalHolidayRepo
       }
    """

    def __init__(self, data):
        self.data = data
        self._gh = GlobalHolidayRepo()
        self._gh.load(self.data.get("global_holidays", {}))

    def list_resorts(self):
        """
        Returns a list of resort dicts, each with at least:
            {
              "id": "...",
              "display_name": "...",
              "location": "...",
              ...
            }
        """
        return list(self.data.get("resorts", {}).values())

    def get_resort_by_id(self, rid):
        for r in self.list_resorts():
            if r.get("id") == rid:
                return r
        return None

    def get_resort_year_data(self, rid, year):
        r = self.get_resort_by_id(rid)
        if not r: 
            return None
        yrs = r.get("years", {})
        return yrs.get(str(year))

class Calc:
    """
    Central calculator for nightly points and cost for both renters and owners.
    It expects resort data in a structure like:

    resort = {
      "id": "KOOL",
      "display_name": "...",
      "years": {
         "2025": {
            "seasons": [
               {
                  "name": "Holiday",
                  "periods": [
                     {"start": "2025-12-20", "end": "2026-01-05", "rate_code": "HOL"}
                  ],
                  "rates": {
                     "HOL": {
                        "rooms": {
                           "2BR-OF": {
                              "sun_thu": 4000, 
                              "fri_sat": 5000
                           },
                           ...
                        }
                     }
                  }
               },
               ...
            ],
            "holidays": [
               {
                 "name": "New Year",
                 "global_reference": "NewYear",
                 "bundle_nights": 7,
                 "bundle_points": 30000,
                 "rooms": ["2BR-OF", ...]
               },
               ...
            ]
         },
         ...
      }
    }
    """

    def __init__(self, repo: ResortRepo, owner_cfg: OwnerConfig):
        self.repo = repo
        self.owner_cfg = owner_cfg

    # ---------- Utility methods ----------

    @staticmethod
    def _parse_date(d):
        if isinstance(d, date):
            return d
        if isinstance(d, datetime):
            return d.date()
        return datetime.strptime(d, "%Y-%m-%d").date()

    def _find_season_rate(self, resort_year_data, day, room_type):
        """
        Return (points, season_name) for the given date & room, ignoring holidays.
        """
        d = day
        for s in resort_year_data.get("seasons", []):
            season_name = s.get("name", "Unknown")
            for p in s.get("periods", []):
                start = self._parse_date(p["start"])
                end = self._parse_date(p["end"])
                if start <= d <= end:
                    rate_code = p.get("rate_code")
                    if not rate_code:
                        continue
                    rates = s.get("rates", {}).get(rate_code, {})
                    room_obj = rates.get("rooms", {}).get(room_type)
                    if not room_obj:
                        continue
                    # Fri-Sat vs Sun-Thu:
                    weekday = d.weekday()  # 0=Mon .. 6=Sun
                    if weekday in (4, 5):  # Fri, Sat
                        pts = room_obj.get("fri_sat", 0)
                    else:
                        pts = room_obj.get("sun_thu", 0)
                    return pts, season_name
        return 0, "Unknown"

    def get_points(self, resort_data, day):
        y = str(day.year)
        if y not in resort_data.get("years", {}): 
            return {}, None
        yd = resort_data["years"][y]
        
        # 1. Holiday Check
        for h in yd.get("holidays", []):
            ref = h.get("global_reference")
            start, end = None, None
            if ref and ref in self.repo._gh.get(y, {}):
                start, end = self.repo._gh._gh[y][ref]
            
            if start and end and start <= day <= end:
                # This day belongs to that holiday bundle
                return {}, h
        
        # 2. Normal Season
        pts_map = {}
        for s in yd.get("seasons", []):
            season_name = s.get("name", "Unknown")
            for p in s.get("periods", []):
                start = self._parse_date(p["start"])
                end = self._parse_date(p["end"])
                if start <= day <= end:
                    rate_code = p.get("rate_code")
                    if not rate_code:
                        continue
                    rates = s.get("rates", {}).get(rate_code, {})
                    for room, room_obj in rates.get("rooms", {}).items():
                        weekday = day.weekday()
                        if weekday in (4, 5):
                            pts = room_obj.get("fri_sat", 0)
                        else:
                            pts = room_obj.get("sun_thu", 0)
                        pts_map[room] = {
                            "points": pts,
                            "season": season_name
                        }
        return pts_map, None

    def _owner_cost_per_point(self):
        """
        Owner's effective cost per point:
          maintenance (annual) + amortized buy-in, divided by annual points.
        For simplicity, we do:
           cost_per_point = maintenance_fee_per_point + (buy_cost_per_point / amort_years)
        where each is already "per point".
        """
        if self.owner_cfg.amort_years <= 0:
            return self.owner_cfg.maintenance_fee_per_point + self.owner_cfg.buy_cost_per_point
        return (
            self.owner_cfg.maintenance_fee_per_point +
            self.owner_cfg.buy_cost_per_point / self.owner_cfg.amort_years
        )

    def calculate(
        self, 
        resort_name,
        resort_id, 
        checkin: date, 
        nights: int, 
        mode: UserMode, 
        renter_ppp: float, 
        discount: DiscountPolicy,
        owner_cfg: OwnerConfig | None = None,
        room_type: str | None = None,
    ) -> CalculationResult | None:
        """
        Calculate total points & cost for a stay.
        If room_type is None, this method is not used for direct booking but for
        comparison data, and we only compute total points & cost for that room type.
        """
        r_obj = None
        for r in self.repo.list_resorts():
            if r.get("id") == resort_id:
                r_obj = r
                break
        if not r_obj:
            return None
        
        # We assume all nights are in same year or we cross years (simplistic).
        total_pts = 0
        nightly_points = []
        nightly_costs = []
        nightly_labels = []
        rows = []
        
        # For owners
        if owner_cfg is None:
            owner_cfg = self.owner_cfg

        cpp_owner = self._owner_cost_per_point()
        renter_ppp_eff = renter_ppp

        # Discount multiplier:
        discount_multiplier = 1.0
        if discount == DiscountPolicy.EXECUTIVE:
            discount_multiplier = 0.8
        elif discount == DiscountPolicy.PRESIDENTIAL:
            discount_multiplier = 0.6

        total_money = 0.0            # will be overridden at the end based on total_pts
        tot_m = tot_c = tot_d = 0.0  # will also be overridden for owners
        disc_hit = False
        processed_holidays = set()
        
        mul = discount_multiplier

        i = 0
        while i < nights:
            d = checkin + timedelta(days=i)
            pts_map, holiday_obj = self.get_points(r_obj, d)
            
            # --- HOLIDAY BUNDLE LOGIC ---
            if holiday_obj:
                if holiday_obj["name"] not in processed_holidays and room_type in holiday_obj.get("rooms", []):
                    processed_holidays.add(holiday_obj["name"])
                    bundle_nights = holiday_obj.get("bundle_nights", 0)
                    bundle_points = holiday_obj.get("bundle_points", 0)
                    # apply the bundle across the next `bundle_nights` nights, 
                    # or until end of stay, whichever is earlier
                    nights_left = nights - i
                    applied_nights = min(bundle_nights, nights_left)
                    
                    per_night_pts = math.ceil(bundle_points / applied_nights) if applied_nights > 0 else 0
                    for j in range(applied_nights):
                        d2 = checkin + timedelta(days=i+j)
                        nightly_points.append(per_night_pts)
                        if mode == UserMode.RENTER:
                            cost = per_night_pts * renter_ppp_eff
                        else:
                            cost = per_night_pts * cpp_owner
                        nightly_costs.append(cost)
                        nightly_labels.append(f"{d2} - Holiday Bundle ({holiday_obj['name']})")
                        rows.append({
                            "Date": d2,
                            "Room Type": room_type,
                            "Type": "Holiday Bundle",
                            "Points": per_night_pts,
                            "Cost": cost,
                        })
                    total_pts += per_night_pts * applied_nights
                    i += applied_nights
                    continue
                else:
                    # We are inside a holiday bundle that has already been processed;
                    # treat as zero additional points (or you may choose to treat differently).
                    nightly_points.append(0)
                    nightly_costs.append(0)
                    nightly_labels.append(f"{d} - Holiday (Already Bundled)")
                    rows.append({
                        "Date": d,
                        "Room Type": room_type,
                        "Type": "Holiday (Bundled)",
                        "Points": 0,
                        "Cost": 0,
                    })
                    i += 1
                    continue

            # --- NON-HOLIDAY NORMAL NIGHT ---
            if room_type not in pts_map:
                # If that room is not defined for that day, we record 0 points
                nightly_points.append(0)
                nightly_costs.append(0)
                nightly_labels.append(f"{d} - Not Available")
                rows.append({
                    "Date": d,
                    "Room Type": room_type,
                    "Type": "Not Available",
                    "Points": 0,
                    "Cost": 0,
                })
                i += 1
                continue

            base_pts = pts_map[room_type]["points"]
            season = pts_map[room_type]["season"]

            # Do not apply discount on Holidays; discount only on regular seasons
            eff_pts = base_pts
            if season.lower() != "holiday":
                eff_pts = int(base_pts * mul)
                if mul < 1.0:
                    disc_hit = True

            nightly_points.append(eff_pts)
            if mode == UserMode.RENTER:
                cost = eff_pts * renter_ppp_eff
            else:
                cost = eff_pts * cpp_owner
            nightly_costs.append(cost)
            nightly_labels.append(f"{d} - {season}")
            rows.append({
                "Date": d,
                "Room Type": room_type,
                "Type": season,
                "Points": eff_pts,
                "Cost": cost,
            })
            total_pts += eff_pts

            i += 1

        # End while

        # Final money total:
        if mode == UserMode.RENTER:
            total_money = total_pts * renter_ppp_eff
        else:
            total_money = total_pts * cpp_owner

        return CalculationResult(
            total_points=total_pts,
            financial_total=total_money,
            breakdown=rows,
            nightly_points=nightly_points,
            nightly_costs=nightly_costs,
            nightly_labels=nightly_labels,
        )

# ---------- Streamlit UI ----------

def main():
    st.set_page_config(page_title="MVC Points Calculator", layout="wide")

    # 1. Ensure data is loaded
    ensure_data_in_session()
    data = st.session_state["resort_data"]
    repo = ResortRepo(data)

    # 2. Header
    render_page_header(
        title="Marriott Vacation Club – Points Calculator",
        subtitle="Estimate points and cost for your stay as a Renter or an Owner."
    )

    # 3. Resorts list
    resorts = repo.list_resorts()
    if not resorts:
        st.error("No resorts found in data.")
        return

    # 4. Resort selector
    resort = render_resort_selector(resorts)
    if not resort:
        st.warning("Please select a resort.")
        return

    render_resort_card(resort)

    # 5. Mode & basic inputs
    col1, col2, col3 = st.columns(3)
    with col1:
        mode_str = st.radio("Mode", [m.value for m in UserMode], index=0)
        mode = UserMode(mode_str)
    with col2:
        checkin = st.date_input("Check-in date", value=date.today())
    with col3:
        nights = st.number_input("Nights", min_value=1, max_value=30, value=7, step=1)

    # 6. Room & financial inputs
    r_year = resort.get("years", {})
    current_year = str(checkin.year)
    room_types = []
    if current_year in r_year:
        # gather room types from 1st season's 1st rate, etc, for convenience
        yd = r_year[current_year]
        for s in yd.get("seasons", []):
            for rate in s.get("rates", {}).values():
                for r_name in rate.get("rooms", {}).keys():
                    if r_name not in room_types:
                        room_types.append(r_name)
    room_types = sorted(room_types)

    if not room_types:
        st.error("No room types available for the selected resort/year.")
        return

    col4, col5 = st.columns(2)
    with col4:
        room_type = st.selectbox("Room Type", room_types)
    with col5:
        renter_ppp = st.number_input("Renter: cost per point ($)", min_value=0.0, value=0.60, step=0.01)

    # Owner configuration
    st.markdown("### Owner Configuration")
    oc1, oc2, oc3 = st.columns(3)
    with oc1:
        mfpp = st.number_input("Maintenance fee per point ($)", min_value=0.0, value=0.20, step=0.01)
    with oc2:
        bcpp = st.number_input("Buy cost per point ($)", min_value=0.0, value=5.00, step=0.10)
    with oc3:
        amort_years = st.number_input("Amortization (years)", min_value=1, max_value=50, value=20, step=1)
    
    owner_cfg = OwnerConfig(
        maintenance_fee_per_point=mfpp,
        buy_cost_per_point=bcpp,
        amort_years=amort_years
    )

    # Discount
    st.markdown("### Discount")
    dcol1, dcol2 = st.columns(2)
    with dcol1:
        disc_str = st.radio("Discount policy", [d.value for d in DiscountPolicy], index=0)
        discount = DiscountPolicy(disc_str)
    with dcol2:
        st.caption("Discount applies only to regular season nights, not holidays.")

    calc = Calc(repo, owner_cfg)

    # Compute primary result
    res = calc.calculate(
        resort_name=resort.get("display_name"),
        resort_id=resort.get("id"),
        checkin=checkin,
        nights=nights,
        mode=mode,
        renter_ppp=renter_ppp,
        discount=discount,
        owner_cfg=owner_cfg,
        room_type=room_type,
    )

    if not res:
        st.error("Unable to compute result for the selected inputs.")
        return

    # Summary
    st.markdown("## Summary")
    colA, colB = st.columns(2)
    with colA:
        st.metric("Total Points", f"{res.total_points:,}")
    with colB:
        st.metric("Total Cost", f"${res.financial_total:,.0f}")

    # Breakdown table
    st.markdown("### Nightly Breakdown")
    df = pd.DataFrame(res.breakdown)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Nightly chart (simple)
    st.markdown("### Nightly Points & Cost")
    c1, c2 = st.columns(2)
    with c1:
        st.bar_chart(
            pd.DataFrame(
                {"Points": res.nightly_points},
                index=res.nightly_labels
            )
        )
    with c2:
        st.bar_chart(
            pd.DataFrame(
                {"Cost": res.nightly_costs},
                index=res.nightly_labels
            )
        )

    # Comparison: other room types
    st.markdown("## Compare Other Room Types")
    comp_rooms = st.multiselect(
        "Select additional room types to compare", 
        [r for r in room_types if r != room_type]
    )
    if comp_rooms:
        comp_data = []
        for cr in comp_rooms:
            c_res = calc.calculate(
                resort_name=resort.get("display_name"),
                resort_id=resort.get("id"),
                checkin=checkin,
                nights=nights,
                mode=mode,
                renter_ppp=renter_ppp,
                discount=discount,
                owner_cfg=owner_cfg,
                room_type=cr,
            )
            if c_res:
                comp_data.append({
                    "Room": cr, 
                    "Points": f"{c_res.total_points:,}",
                    "Total Cost": f"${c_res.financial_total:,.0f}"
                })
        
        st.dataframe(pd.DataFrame(comp_data), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
