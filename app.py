import streamlit as st
import json
from datetime import datetime, date
from typing import Any, Dict, List

st.set_page_config(page_title="Marriott Abound Editor", layout="wide")

# ---------------------------- SESSION STATE ----------------------------
if "data" not in st.session_state:
    st.session_state.data = None
if "uploaded" not in st.session_state:
    st.session_state.uploaded = False

# ---------------------------- HELPERS ----------------------------
def save_data():
    """Write current session_state back to the downloadable JSON."""
    st.session_state.download_json = json.dumps(st.session_state.data, indent=2)

def iso(d: date) -> str:
    return d.isoformat()

def to_date(s: str):
    return datetime.fromisoformat(s).date()

# ---------------------------- SIDEBAR ----------------------------
with st.sidebar:
    st.title("Marriott Abound Editor")
    st.write(f"**Time:** {datetime.now().strftime('%I:%M %p')}")

    uploaded = st.file_uploader("Upload data.json", type="json")

    if uploaded and not st.session_state.uploaded:
        try:
            raw = json.load(uploaded)
            # Normalise missing top-level keys
            for key in ["resorts_list", "reference_points", "season_blocks",
                        "global_dates", "maintenance_rates"]:
                raw.setdefault(key, {} if key != "resorts_list" else [])

            # Build resort list if missing
            if not raw["resorts_list"]:
                keys = (set(raw.get("reference_points", {}).keys()) |
                        set(raw.get("season_blocks", {}).keys()))
                raw["resorts_list"] = sorted(keys)

            st.session_state.data = raw
            st.session_state.uploaded = True
            save_data()
            st.success(f"Loaded {len(raw['resorts_list'])} resorts")
            st.rerun()
        except Exception as e:
            st.error(f"Upload error: {e}")

    if st.session_state.data:
        save_data()
        st.download_button(
            "Download Updated JSON",
            data=st.session_state.download_json,
            file_name="data-updated.json",
            mime="application/json"
        )

# ---------------------------- MAIN APP ----------------------------
if not st.session_state.data:
    st.title("Marriott Abound Editor")
    st.info("Upload your `data.json` to start editing")
    st.stop()

data = st.session_state.data
resorts = data["resorts_list"]

st.title("Marriott Abound Editor")

# ---------- Resort selector ----------
cols = st.columns(6)
for i, r in enumerate(resorts):
    if cols[i % 6].button(r, key=f"res_{i}"):
        st.session_state.current_resort = r
        st.rerun()

if "current_resort" not in st.session_state:
    st.info("↑ Select a resort")
    st.stop()

resort = st.session_state.current_resort
st.header(resort)

# ========================= REFERENCE POINTS =========================
st.subheader("Reference Points (nightly)")

ref = data["reference_points"].setdefault(resort, {})

for season, content in ref.items():
    with st.expander(season, expanded=True):
        # ---------- Normal nightly blocks (Fri-Sat / Sun-Thu) ----------
        day_groups = {k: v for k, v in content.items() if k in ("Fri-Sat", "Sun-Thu", "Mon-Thu")}
        if day_groups:
            for day_name, rooms in day_groups.items():
                st.write(f"**{day_name}**")
                df = st.data_editor(
                    pd.DataFrame.from_dict(rooms, orient="index", columns=["Points"]),
                    use_container_width=True,
                    hide_index=False,
                    column_config={"Points": st.column_config.NumberColumn("Points", step=25)},
                    key=f"nightly_{resort}_{season}_{day_name}"
                )
                content[day_name] = df["Points"].to_dict()

        # ---------- Holiday Week blocks ----------
        holiday_weeks = {k: v for k, v in content.items() if k not in ("Fri-Sat", "Sun-Thu", "Mon-Thu")}
        if holiday_weeks:
            for hol_name, rooms in holiday_weeks.items():
                st.markdown(f"**{hol_name}** (full week)")
                df = st.data_editor(
                    pd.DataFrame.from_dict(rooms, orient="index", columns=["Points"]),
                    use_container_width=True,
                    hide_index=False,
                    column_config={"Points": st.column_config.NumberColumn("Points", step=25)},
                    key=f"holiday_{resort}_{season}_{hol_name}"
                )
                content[hol_name] = df["Points"].to_dict()

# ========================= SEASON DATES =========================
st.subheader("Season Date Ranges")

season_blocks = data["season_blocks"].setdefault(resort, {})

for year in ("2025", "2026"):
    with st.expander(f"{year} Seasons", expanded=True):
        year_data = season_blocks.setdefault(year, {})
        for s_name, ranges in year_data.items():
            st.markdown(f"### {s_name}")
            # Ensure ranges is a list of lists
            if not isinstance(ranges, list):
                ranges = []
                year_data[s_name] = ranges

            # Edit existing ranges
            for idx, (start, end) in enumerate(ranges[:]):
                c1, c2, c3 = st.columns([3, 3, 1])
                with c1:
                    ns = st.date_input("Start", to_date(start), key=f"start_{year}_{s_name}_{idx}")
                with c2:
                    ne = st.date_input("End", to_date(end), key=f"end_{year}_{s_name}_{idx}")
                with c3:
                    if st.button("Delete", key=f"del_{year}_{s_name}_{idx}"):
                        ranges.pop(idx)
                        st.rerun()

                if iso(ns) != start or iso(ne) != end:
                    ranges[idx] = [iso(ns), iso(ne)]

            # Add new range
            if st.button(f"Add new range for {s_name} ({year})", key=f"add_{year}_{s_name}"):
                today = date.today()
                ranges.append([iso(today), iso(today)])
                st.rerun()

# ========================= GLOBAL DATES (Holidays) =========================
st.subheader("Global Holiday Weeks")

global_dates = data.get("global_dates", {})

for year in ("2025", "2026"):
    with st.expander(f"{year} Global Holidays", expanded=True):
        year_hols = global_dates.setdefault(year, {})
        for hol_name, dates in year_hols.items():
            st.markdown(f"### {hol_name}")
            for idx, d_str in enumerate(dates[:]):
                c1, c2 = st.columns([4, 1])
                with c1:
                    new_d = st.date_input("Date", to_date(d_str), key=f"gh_{year}_{hol_name}_{idx}")
                with c2:
                    if st.button("Delete", key=f"ghdel_{year}_{hol_name}_{idx}"):
                        dates.pop(idx)
                        st.rerun()
                if iso(new_d) != d_str:
                    dates[idx] = iso(new_d)

            if st.button(f"Add date to {hol_name} ({year})", key=f"ghadd_{year}_{hol_name}"):
                dates.append(iso(date.today()))
                st.rerun()

# ========================= MAINTENANCE FEES =========================
st.subheader("Maintenance Fee per Point (USD)")

mf = data.get("maintenance_rates", {})

for year in ("2025", "2026", "2027", "2028"):
    cur = mf.get(year, 0.0)
    new = st.number_input(
        f"{year} fee per point",
        value=float(cur),
        step=0.0001,
        format="%.4f",
        key=f"mf_{year}"
    )
    if round(new, 4) != round(float(cur), 4):
        mf[year] = round(new, 4)

# ========================= AUTO-SAVE =========================
save_data()
st.success("All changes are saved automatically – use the Download button in the sidebar whenever you’re ready.")
