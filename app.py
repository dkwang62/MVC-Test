import math
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, date
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any

# ----------------------------
# Demo data: inlined resort + season + holiday info
# ----------------------------

RESORT_DATA: Dict[str, Any] = {
    "resorts": {
        "SAMPLE": {
            "id": "SAMPLE",
            "display_name": "Sample Beach Resort",
            "location": "Hawaii, USA",
            "description": "A demo resort used to illustrate the MVC-style points calculator.",
            "years": {
                "2025": {
                    "seasons": [
                        {
                            "name": "Value",
                            "periods": [
                                {
                                    "start": "2025-01-05",
                                    "end": "2025-05-31",
                                    "rate_code": "VALUE",
                                },
                                {
                                    "start": "2025-09-01",
                                    "end": "2025-12-15",
                                    "rate_code": "VALUE",
                                },
                            ],
                            "rates": {
                                "VALUE": {
                                    "rooms": {
                                        "2BR-OF": {"sun_thu": 2500, "fri_sat": 3000},
                                        "2BR-MV": {"sun_thu": 2200, "fri_sat": 2700},
                                    }
                                }
                            },
                        },
                        {
                            "name": "Peak",
                            "periods": [
                                {
                                    "start": "2025-06-01",
                                    "end": "2025-08-31",
                                    "rate_code": "PEAK",
                                }
                            ],
                            "rates": {
                                "PEAK": {
                                    "rooms": {
                                        "2BR-OF": {"sun_thu": 3200, "fri_sat": 3800},
                                        "2BR-MV": {"sun_thu": 2800, "fri_sat": 3400},
                                    }
                                }
                            },
                        },
                        {
                            "name": "Holiday",
                            "periods": [
                                {
                                    "start": "2025-12-16",
                                    "end": "2025-12-27",
                                    "rate_code": "HOLIDAY",
                                }
                            ],
                            "rates": {
                                "HOLIDAY": {
                                    "rooms": {
                                        "2BR-OF": {"sun_thu": 4000, "fri_sat": 4500},
                                        "2BR-MV": {"sun_thu": 3600, "fri_sat": 4100},
                                    }
                                }
                            },
                        },
                    ],
                    "holidays": [
                        {
                            "name": "New Year Bundle",
                            "start": "2025-12-28",
                            "end": "2026-01-02",
                            "bundle_nights": 7,
                            "bundle_points": 30000,
                            "rooms": ["2BR-OF", "2BR-MV"],
                        }
                    ],
                }
            },
        }
    }
}


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
    breakdown: List[Dict[str, Any]]
    nightly_points: List[int]
    nightly_costs: List[float]
    nightly_labels: List[str]


@dataclass
class OwnerConfig:
    maintenance_fee_per_point: float
    buy_cost_per_point: float
    amort_years: int


class ResortRepo:
    """
    Simple in-memory repository around RESORT_DATA.
    """

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def list_resorts(self) -> List[Dict[str, Any]]:
        return list(self.data.get("resorts", {}).values())

    def get_resort_by_id(self, rid: str) -> Optional[Dict[str, Any]]:
        return self.data.get("resorts", {}).get(rid)

    def get_resort_year_data(self, rid: str, year: int) -> Optional[Dict[str, Any]]:
        resort = self.get_resort_by_id(rid)
        if not resort:
            return None
        return resort.get("years", {}).get(str(year))


class Calc:
    """
    Central calculator for nightly points and cost for both renters and owners.
    The structure expected in RESORT_DATA mirrors the Marriott chart logic:
    - seasons with date ranges and Sun–Thu / Fri–Sat rates
    - holidays with optional bundle logic (fixed points over fixed nights)
    """

    def __init__(self, repo: ResortRepo, owner_cfg: OwnerConfig):
        self.repo = repo
        self.owner_cfg = owner_cfg

    # ---------- Utility methods ----------

    @staticmethod
    def _parse_date(d: Any) -> date:
        if isinstance(d, date):
            return d
        if isinstance(d, datetime):
            return d.date()
        return datetime.strptime(d, "%Y-%m-%d").date()

    def _owner_cost_per_point(self, owner_cfg: OwnerConfig) -> float:
        """
        Owner's effective cost per point:
          maintenance (annual) + amortised buy-in, divided by years.
        For simplicity, treat inputs as already 'per point' values:
           cost_per_point = maintenance_fee_per_point
                            + (buy_cost_per_point / amort_years)
        """
        if owner_cfg.amort_years <= 0:
            return owner_cfg.maintenance_fee_per_point + owner_cfg.buy_cost_per_point
        return (
            owner_cfg.maintenance_fee_per_point
            + owner_cfg.buy_cost_per_point / owner_cfg.amort_years
        )

    def _find_season_points(
        self, resort_year_data: Dict[str, Any], day: date, room_type: str
    ) -> Dict[str, Any]:
        """
        Return {"points": int, "season": str} for the given date & room,
        ignoring any holiday bundle.
        """
        d = day
        for season in resort_year_data.get("seasons", []):
            season_name = season.get("name", "Unknown")
            for period in season.get("periods", []):
                start = self._parse_date(period["start"])
                end = self._parse_date(period["end"])
                if start <= d <= end:
                    rate_code = period.get("rate_code")
                    if not rate_code:
                        continue
                    rates_for_code = season.get("rates", {}).get(rate_code, {})
                    room_obj = rates_for_code.get("rooms", {}).get(room_type)
                    if not room_obj:
                        continue
                    weekday = d.weekday()  # 0=Mon..6=Sun
                    if weekday in (4, 5):  # Fri, Sat
                        pts = room_obj.get("fri_sat", 0)
                    else:
                        pts = room_obj.get("sun_thu", 0)
                    return {"points": pts, "season": season_name}
        return {"points": 0, "season": "Unknown"}

    def _find_holiday_bundle(
        self, resort_year_data: Dict[str, Any], day: date, room_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        If the given day falls in a holiday bundle that covers the given room type,
        return that holiday dict; otherwise None.
        """
        for h in resort_year_data.get("holidays", []):
            if room_type not in h.get("rooms", []):
                continue
            start = self._parse_date(h["start"])
            end = self._parse_date(h["end"])
            if start <= day <= end:
                return h
        return None

    def calculate(
        self,
        resort_id: str,
        checkin: date,
        nights: int,
        mode: UserMode,
        renter_ppp: float,
        discount: DiscountPolicy,
        owner_cfg: Optional[OwnerConfig],
        room_type: str,
    ) -> Optional[CalculationResult]:
        """
        Calculate points and cost for a stay in a specific room type.
        """
        resort = self.repo.get_resort_by_id(resort_id)
        if not resort:
            return None

        # Year data (simple assumption: stay does not cross into two different season-data years)
        year_data = resort.get("years", {}).get(str(checkin.year))
        if not year_data:
            return None

        if owner_cfg is None:
            owner_cfg = self.owner_cfg

        cpp_owner = self._owner_cost_per_point(owner_cfg)

        discount_multiplier = 1.0
        if discount == DiscountPolicy.EXECUTIVE:
            discount_multiplier = 0.8
        elif discount == DiscountPolicy.PRESIDENTIAL:
            discount_multiplier = 0.6

        nightly_points: List[int] = []
        nightly_costs: List[float] = []
        nightly_labels: List[str] = []
        breakdown_rows: List[Dict[str, Any]] = []

        total_points = 0
        processed_holidays = set()

        i = 0
        while i < nights:
            current_day = checkin + timedelta(days=i)

            # 1) Check if the night is within a holiday bundle
            holiday = self._find_holiday_bundle(year_data, current_day, room_type)

            if holiday and holiday["name"] not in processed_holidays:
                # First encounter of this holiday: apply bundle.
                processed_holidays.add(holiday["name"])
                bundle_nights = holiday.get("bundle_nights", 0)
                bundle_points = holiday.get("bundle_points", 0)

                nights_left = nights - i
                applied_nights = min(bundle_nights, nights_left)

                per_night_pts = (
                    math.ceil(bundle_points / applied_nights) if applied_nights > 0 else 0
                )

                for j in range(applied_nights):
                    d2 = checkin + timedelta(days=i + j)

                    nightly_points.append(per_night_pts)
                    cost_per_point = renter_ppp if mode == UserMode.RENTER else cpp_owner
                    cost = per_night_pts * cost_per_point
                    nightly_costs.append(cost)
                    nightly_labels.append(f"{d2} – Holiday Bundle ({holiday['name']})")

                    breakdown_rows.append(
                        {
                            "Date": d2,
                            "Room Type": room_type,
                            "Type": "Holiday Bundle",
                            "Points": per_night_pts,
                            "Cost": cost,
                        }
                    )

                total_points += per_night_pts * applied_nights
                i += applied_nights
                continue

            if holiday and holiday["name"] in processed_holidays:
                # Inside a holiday range that was already bundled earlier in the stay.
                nightly_points.append(0)
                nightly_costs.append(0.0)
                nightly_labels.append(f"{current_day} – Holiday (bundled earlier)")
                breakdown_rows.append(
                    {
                        "Date": current_day,
                        "Room Type": room_type,
                        "Type": "Holiday (Bundled)",
                        "Points": 0,
                        "Cost": 0.0,
                    }
                )
                i += 1
                continue

            # 2) Regular season night
            season_info = self._find_season_points(year_data, current_day, room_type)
            base_pts = season_info["points"]
            season_name = season_info["season"]

            if base_pts == 0:
                nightly_points.append(0)
                nightly_costs.append(0.0)
                nightly_labels.append(f"{current_day} – Not Available")
                breakdown_rows.append(
                    {
                        "Date": current_day,
                        "Room Type": room_type,
                        "Type": "Not Available",
                        "Points": 0,
                        "Cost": 0.0,
                    }
                )
                i += 1
                continue

            effective_pts = base_pts
            if season_name.lower() != "holiday":
                effective_pts = int(base_pts * discount_multiplier)

            cost_per_point = renter_ppp if mode == UserMode.RENTER else cpp_owner
            cost = effective_pts * cost_per_point

            nightly_points.append(effective_pts)
            nightly_costs.append(cost)
            nightly_labels.append(f"{current_day} – {season_name}")
            breakdown_rows.append(
                {
                    "Date": current_day,
                    "Room Type": room_type,
                    "Type": season_name,
                    "Points": effective_pts,
                    "Cost": cost,
                }
            )

            total_points += effective_pts
            i += 1

        total_cost = sum(nightly_costs)

        return CalculationResult(
            total_points=total_points,
            financial_total=total_cost,
            breakdown=breakdown_rows,
            nightly_points=nightly_points,
            nightly_costs=nightly_costs,
            nightly_labels=nightly_labels,
        )


# ----------------------------
# Streamlit App
# ----------------------------

def main() -> None:
    st.set_page_config(page_title="MVC-style Points Calculator (Demo)", layout="wide")

    repo = ResortRepo(RESORT_DATA)

    st.title("MVC-style Points Calculator (Demo)")
    st.caption(
        "Fully inlined, self-contained example. Adjust the demo data in RESORT_DATA to "
        "match your real resorts, seasons, and holidays."
    )

    resorts = repo.list_resorts()
    if not resorts:
        st.error("No resorts defined in RESORT_DATA.")
        return

    # Resort selector
    resort_names = [r["display_name"] for r in resorts]
    selected_name = st.selectbox("Resort", resort_names)
    resort = next(r for r in resorts if r["display_name"] == selected_name)

    st.subheader(resort["display_name"])
    st.write(resort.get("location", ""))
    if resort.get("description"):
        st.write(resort["description"])

    # Inputs
    col1, col2, col3 = st.columns(3)
    with col1:
        mode_label = st.radio("User Type", [m.value for m in UserMode], index=0)
        mode = UserMode(mode_label)
    with col2:
        checkin = st.date_input("Check-in date", value=date(2025, 6, 1))
    with col3:
        nights = st.number_input("Nights", min_value=1, max_value=30, value=7, step=1)

    # Room types derived from selected year
    current_year_data = resort.get("years", {}).get(str(checkin.year))
    room_types: List[str] = []
    if current_year_data:
        for season in current_year_data.get("seasons", []):
            for rate in season.get("rates", {}).values():
                for r_name in rate.get("rooms", {}).keys():
                    if r_name not in room_types:
                        room_types.append(r_name)

    if not room_types:
        st.error(
            f"No room types defined for year {checkin.year} in RESORT_DATA "
            f"for resort {resort['display_name']}."
        )
        return

    col4, col5 = st.columns(2)
    with col4:
        room_type = st.selectbox("Room type", sorted(room_types))
    with col5:
        renter_ppp = st.number_input(
            "Renter – cost per point ($)", min_value=0.0, value=0.60, step=0.01
        )

    # Owner configuration
    st.markdown("### Owner Configuration")
    oc1, oc2, oc3 = st.columns(3)
    with oc1:
        mfpp = st.number_input(
            "Maintenance fee per point ($)", min_value=0.0, value=0.20, step=0.01
        )
    with oc2:
        bcpp = st.number_input(
            "Buy cost per point ($)", min_value=0.0, value=5.00, step=0.10
        )
    with oc3:
        amort_years = st.number_input(
            "Amortisation (years)", min_value=1, max_value=50, value=20, step=1
        )

    owner_cfg = OwnerConfig(
        maintenance_fee_per_point=mfpp,
        buy_cost_per_point=bcpp,
        amort_years=amort_years,
    )

    # Discount
    st.markdown("### Discount")
    d1, d2 = st.columns(2)
    with d1:
        disc_label = st.radio(
            "Discount policy", [d.value for d in DiscountPolicy], index=0
        )
        discount = DiscountPolicy(disc_label)
    with d2:
        st.caption("Discount applies only to regular seasons, not holiday bundles.")

    calc = Calc(repo, owner_cfg)

    # Main calculation
    result = calc.calculate(
        resort_id=resort["id"],
        checkin=checkin,
        nights=nights,
        mode=mode,
        renter_ppp=renter_ppp,
        discount=discount,
        owner_cfg=owner_cfg,
        room_type=room_type,
    )

    if not result:
        st.error("Calculation failed – check your data / inputs.")
        return

    # Output
    st.markdown("## Summary")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Total points", f"{result.total_points:,}")
    with c2:
        st.metric("Total cost", f"${result.financial_total:,.0f}")

    st.markdown("### Nightly breakdown")
    df = pd.DataFrame(result.breakdown)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("### Nightly points and cost")
    g1, g2 = st.columns(2)
    with g1:
        st.bar_chart(
            pd.DataFrame({"Points": result.nightly_points}, index=result.nightly_labels)
        )
    with g2:
        st.bar_chart(
            pd.DataFrame({"Cost": result.nightly_costs}, index=result.nightly_labels)
        )

    # Comparison
    st.markdown("## Compare other room types")
    other_rooms = [r for r in room_types if r != room_type]
    selected_comps = st.multiselect("Additional room types", other_rooms)

    if selected_comps:
        comp_rows = []
        for rt in selected_comps:
            res2 = calc.calculate(
                resort_id=resort["id"],
                checkin=checkin,
                nights=nights,
                mode=mode,
                renter_ppp=renter_ppp,
                discount=discount,
                owner_cfg=owner_cfg,
                room_type=rt,
            )
            if not res2:
                continue
            comp_rows.append(
                {
                    "Room": rt,
                    "Total points": f"{res2.total_points:,}",
                    "Total cost": f"${res2.financial_total:,.0f}",
                }
            )
        if comp_rows:
            st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
