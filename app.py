import streamlit as st
import json
import re
from io import BytesIO
from typing import List, Dict, Any, Union
import pypdf 


# ---------- HARDCODED RESORT LIST ----------
# This list will be used for all extraction attempts.
RESORTS_LIST = [
    "Marriott Grand Residence Club, Lake Tahoe",
    "Marriott'S Aruba Ocean Club",
    "Marriott'S Aruba Surf Club",
    "Marriott'S Bali Nusa Dua Gardens",
    "Marriott'S Bali Nusa Dua Terrace",
    "Marriott'S Barony Beach Club",
    "Marriott'S Beachplace Towers",
    "Marriott'S Canyon Villas",
    "Marriott'S Club Son Antem",
    "Marriott'S Crystal Shores",
    "Marriott'S Cypress Harbour",
    "Marriott'S Desert Springs Villas (I & Ii)",
    "Marriott'S Fairway Villas",
    "Marriott'S Frenchman'S Cove",
    "Marriott'S Grand Chateau",
    "Marriott'S Grande Ocean",
    "Marriott'S Grande Vista",
    "Marriott'S Harbour Club",
    "Marriott'S Harbour Lake",
    "Marriott'S Harbour Point",
    "Marriott'S Heritage Club",
    "Marriott'S Imperial Palms",
    "Marriott'S Kaua'i Beach Club",
    "Marriott'S Kaua'i Lagoons",
    "Marriott'S Ko Olina Beach Club",
    "Marriott'S Lakeshore Reserve",
    "Marriott'S Legends Edge At Bay Point",
    "Marriott'S Mai Khao Resort - Phuket",
    "Marriott'S Manor Club At Ford'S Colony",
    "Marriott'S Marbella Beach Resort",
    "Marriott'S Maui Ocean Club",
    "Marriott'S Mountain Valley Lodge",
    "Marriott'S Newport Coast Villas",
    "Marriott'S Ocean Pointe",
    "Marriott'S Oceana Palms",
    "Marriott'S Oceanwatch At Grande Dunes",
    "Marriott'S Phuket Beach Club",
    "Marriott'S Phuket Beach Club 1",
    "Marriott'S Playa Andaluza",
    "Marriott'S Royal Palms",
    "Marriott'S Sabal Palms",
    "Marriott'S Shadow Ridge",
    "Marriott'S St. Kitts Beach Club",
    "Marriott'S Summit Watch",
    "Marriott'S Sunset Pointe",
    "Marriott'S Timber Lodge",
    "Marriott'S Village D'Ile-De-France",
    "Marriott'S Villas At Doral",
    "Marriott'S Waikoloa Ocean Club",
    "Marriott'S Waiohai Beach Club",
    "Marriott'S Willow Ridge Lodge",
    "Sheraton Broadway Plantation",
    "Sheraton Desert Oasis",
    "Sheraton Kaua'i Resort",
    "Sheraton Lakeside T Errace Villas At Mountain Vista",
    "Sheraton Mountain Vista",
    "Sheraton Pga Vacation Resort",
    "Sheraton Steamboat Resort Villas",
    "Sheraton Vistana Resort",
    "Sheraton Vistana Villages",
    "The Ritz-Carlton Club And Residences, San Francisco",
    "The Ritz-Carlton Club, Aspen Highlands",
    "The Ritz-Carlton Club, Lake T Ahoe",
    "The Ritz-Carlton Club, St. Thomas",
    "The Ritz-Carlton Club, Vail"
]

# ---------- Configuration & Helpers (Unchanged) ----------

# Regex to capture date ranges like "JAN 3 - FEB 2"
DATE_RANGE_RE = re.compile(
    r"([A-Za-z]{3})\s+(\d{1,2})\s*[\u2013\-]\s*([A-Za-z]{3})\s+(\d{1,2})"
)
MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
}

# Standardized list of season names to look for in the PDF text
SEASON_NAMES = ["PLATINUM", "HIGH", "GOLD", "SILVER", "LOW"]


def month_day_to_iso(year: int, mon_abbr: str, day: str) -> str:
    """Converts month abbreviation and day to ISO date string."""
    mon = MONTHS[mon_abbr.upper()]
    d = int(day)
    return f"{year:04d}-{mon:02d}-{d:02d}"


def normalize(text: str) -> str:
    """Uppercase and remove common accents/punctuation for matching."""
    text = text.upper()
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("–", "-").replace("—", "-")
    return text


def extract_season_blocks_from_page_text(text: str) -> Dict[str, Any]:
    """
    Extracts season names (e.g., Platinum) and their corresponding date ranges 
    for 2025 and 2026 from the resort page text, matching the season_blocks structure.
    """
    norm = normalize(text)
    result = {"2025": {}, "2026": {}}
    
    lines = [ln.strip() for ln in norm.splitlines() if ln.strip()]
    
    current_season = None
    
    for i, line in enumerate(lines):
        
        # 1. Check for a Season Name to start a new block
        season_found = False
        for s_name in SEASON_NAMES:
            if line.startswith(s_name):
                current_season = s_name.title()
                season_found = True
                break
        
        if season_found:
            # 2. Look for date ranges in the current line and the next few lines
            
            search_block = line
            # Combine the current line with the next line to handle wrapping
            if i + 1 < len(lines):
                search_block += " " + lines[i+1]
                
            ranges = DATE_RANGE_RE.findall(search_block)
            
            if not ranges:
                # If season header was found but no dates were immediately found, continue searching 
                # for the next line in case the season name is on a line by itself
                continue 

            # The date ranges typically alternate: [2025 range 1, 2026 range 1, 2025 range 2, 2026 range 2, ...]
            season_ranges_2025 = []
            season_ranges_2026 = []
            
            for idx, (m1, d1, m2, d2) in enumerate(ranges):
                # The PDF structure typically lists 2025 dates first, then 2026 dates.
                year = 2025 if idx % 2 == 0 else 2026
                start_iso = month_day_to_iso(year, m1, d1)
                end_iso = month_day_to_iso(year, m2, d2)
                
                if year == 2025:
                    season_ranges_2025.append([start_iso, end_iso])
                else:
                    season_ranges_2026.append([start_iso, end_iso])
            
            # 3. Commit the season data (using .get for appending if a season is split across pages/sections)
            if season_ranges_2025:
                result["2025"][current_season] = result["2025"].get(current_season, []) + season_ranges_2025
            if season_ranges_2026:
                result["2026"][current_season] = result["2026"].get(current_season, []) + season_ranges_2026

            current_season = None # Reset for the next season block

    # Clean up empty year dictionaries
    if not result["2025"]:
        del result["2025"]
    if not result["2026"]:
        del result["2026"]
        
    return result


@st.cache_data
def find_resort_pages(pdf_file_object: BytesIO, resorts_list: List[str]) -> Dict[str, Union[int, None]]:
    """
    Finds the highest page index where each resort name appears.
    """
    pdf_file_object.seek(0)
    reader = pypdf.PdfReader(pdf_file_object)
    page_map = {}
    
    # Using a list comprehension for efficiency
    for resort in resorts_list:
        term = normalize(resort)
        # Remove common, non-unique parts to improve matching stability
        term = term.replace("MARRIOTT", "").replace("VACATION CLUB", "").strip()
        
        hits = []
        for idx, page in enumerate(reader.pages):
            text = normalize(page.extract_text() or "")
            if term in text:
                hits.append(idx)
        
        page_map[resort] = max(hits) if hits else None
        
    return page_map


@st.cache_data
def extract_all_resorts(pdf_file_object: BytesIO, resorts_list: List[str]) -> Dict[str, Any]:
    """Coordinates the full extraction process for the hardcoded resort list."""
    
    # 1. Find the page index for each resort
    page_map = find_resort_pages(pdf_file_object, resorts_list) 

    # 2. Re-initialize the reader to ensure we start from the beginning for extraction
    pdf_file_object.seek(0)
    reader = pypdf.PdfReader(pdf_file_object)
    
    season_blocks_result = {}
    
    extraction_progress = st.progress(0, text="Extracting season block data...")
    
    for i, resort in enumerate(resorts_list):
        page_idx = page_map.get(resort)
        
        # Log which resorts were skipped for transparency
        if page_idx is None:
            st.info(f"Page not found for resort: **{resort}**. Skipping.")
            continue

        # Extract text from the identified page index
        text = reader.pages[page_idx].extract_text() or ""
        
        # Parse the season block data
        blocks = extract_season_blocks_from_page_text(text)
        
        # Only add to the result if some data was found
        if blocks:
            season_blocks_result[resort] = blocks
        else:
             st.warning(f"No season data found for **{resort}** (Page {page_idx + 1}).")

        extraction_progress.progress((i + 1) / len(resorts_list), text=f"Extracting data for **{resort}**...")

    extraction_progress.empty()
    return season_blocks_result


# ---------- Main Streamlit Application ----------

def app_main():
    st.set_page_config(page_title="MVC PDF Extractor", layout="wide")
    st.title("Marriott PDF Season Block Extractor 📅")
    st.markdown(f"This tool extracts **Season Date Ranges** for **{len(RESORTS_LIST)} pre-defined resorts** from the uploaded **MVC-2026.pdf** chart.")

    # --- File Uploader ---
    uploaded_pdf = st.file_uploader(
        "1. Upload MVC-2026.pdf", 
        type="pdf", 
        help="The Marriott Club Points Chart PDF (e.g., MVC-2026.pdf)"
    )

    st.markdown("---")
    st.info(f"**Resorts to be Processed** ({len(RESORTS_LIST)}): Starting with *{', '.join(RESORTS_LIST[:3])}...*")
    st.markdown("---")

    # --- Processing Button ---
    if st.button("2. Start Full Season Block Extraction", type="primary", disabled=not uploaded_pdf):
        if uploaded_pdf is None:
            st.error("Please upload the PDF file first.")
            return

        # Read the file content into a memory buffer
        pdf_buffer = BytesIO(uploaded_pdf.read())
        
        with st.spinner("Processing PDF and extracting season blocks for all resorts..."):
            try:
                # The core extraction logic uses the hardcoded list
                season_blocks_data = extract_all_resorts(pdf_buffer, RESORTS_LIST)

                output_dict = {
                    "$schema": "./schema.json", 
                    "resorts_list": list(season_blocks_data.keys()), # List only resorts that returned data
                    "season_blocks": season_blocks_data,
                    "global_dates": {}, # Placeholder as this data is typically manual
                }
                
                output_json_str = json.dumps(output_dict, indent=2)

                st.success(f"🎉 Extraction Complete! Successfully found data for **{len(season_blocks_data)}** resorts.")
                
                st.subheader("Extracted Season Blocks Output")
                
                # Download Button
                st.download_button(
                    label="Download mvc_2026_season_blocks.json",
                    data=output_json_str,
                    file_name="mvc_2026_season_blocks.json",
                    mime="application/json",
                    type="secondary",
                    help="Click to download the extracted season block data."
                )
                
                # Display the data in an expander
                with st.expander("Review JSON Output Structure", expanded=False):
                    st.json(output_dict)

            except Exception as e:
                st.error("An unexpected error occurred during extraction.")
                st.exception(e) # Display full traceback for debugging


if __name__ == "__main__":
    app_main()
