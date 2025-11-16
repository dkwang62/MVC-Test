import streamlit as st
import json
import re
from io import BytesIO
from typing import List, Dict, Any, Union
import pypdf 


# ---------- Configuration & Helpers ----------

DATE_RANGE_RE = re.compile(
    r"([A-Za-z]{3})\s+(\d{1,2})\s*[\u2013\-]\s*([A-Za-z]{3})\s+(\d{1,2})"
)
MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
}

# Keywords to identify lines containing resort names for auto-extraction
BRAND_NAMES = ["MARRIOTT", "SHERATON", "WESTIN", "THE RITZ-CARLTON", "GRAND RESIDENCES"]


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


@st.cache_data
def auto_extract_resorts(pdf_file_object: BytesIO) -> List[str]:
    """
    Scans the first few pages of the PDF to build a list of all resort names 
    by looking for common brand name keywords.
    """
    st.info("Attempting to auto-extract all resort names from the PDF...")
    resorts = set()
    pdf_file_object.seek(0)
    reader = pypdf.PdfReader(pdf_file_object)
    
    # We assume the resort list is on the first 10 pages, before the main tables start
    max_pages_to_scan = min(len(reader.pages), 10) 
    
    for i in range(1, max_pages_to_scan): # Start from page 2 (index 1)
        try:
            page_text = reader.pages[i].extract_text()
            if not page_text:
                continue
                
            norm_text = normalize(page_text)
            
            # Split into lines and filter
            for line in norm_text.splitlines():
                line = line.strip()
                if not line:
                    continue

                # Rule: The line must start with one of the brand names
                if any(line.startswith(brand) for brand in BRAND_NAMES):
                    
                    # Heuristic to filter out short headings (like STATE names)
                    # Resort names are typically long and mixed case/symbols in the source text.
                    if len(line.split()) < 3 and all(c.isupper() or not c.isalpha() for c in line):
                        # Skip if it looks like a short, all-caps heading (e.g., "FLORIDA")
                        continue
                        
                    # Clean the name (remove trailing symbols like '®' or 'SM')
                    clean_name = re.sub(r'[\u00AE\u2122\u00A9\u2120]', '', line).strip()
                    
                    # Convert to Title Case for cleaner output and add to set
                    resorts.add(clean_name.title()) 
                    
        except Exception as e:
            st.warning(f"Error processing page {i+1} for resorts: {e}")
            
    # Remove "Marriott Vacation Club" which often gets picked up as a generic heading
    generic_term = "Marriott Vacation Club"
    final_resorts = [r for r in list(resorts) if generic_term.upper() not in r.upper()]
    
    return sorted(final_resorts)


def extract_resort_blocks_from_page_text(text: str) -> List[Dict[str, Any]]:
    """
    From a single resort-page text, extract a list of raw data rows.
    (Parsing logic retained from original script)
    """
    norm = normalize(text)

    # Find the main table chunk between “2025 2026 DAY*UNIT TYPE” and “HOLIDAY WEEKS”
    anchor = "2025 2026 DAY*UNIT TYPE"
    idx = norm.find(anchor)
    if idx == -1:
        return []

    # Try to cut off at "HOLIDAY WEEKS" (first one on page)
    hw_idx = norm.find("HOLIDAY WEEKS", idx)
    table_text = norm[idx: hw_idx if hw_idx != -1 else None]

    lines = [ln.strip() for ln in table_text.splitlines() if ln.strip()]

    rows = []
    current_date_lines = []

    i = 0
    while i < len(lines):
        ln = lines[i]

        if ln.startswith("FRI-SAT") or ln.startswith("FRI–SAT"):
            # close date block & parse
            date_block = " ".join(current_date_lines)
            current_date_lines = []

            # parse all date ranges in that block
            ranges = DATE_RANGE_RE.findall(date_block)
            
            date_pairs_2025 = []
            date_pairs_2026 = []
            for idx2, (m1, d1, m2, d2) in enumerate(ranges):
                # Assuming 2025 is left column (idx2 is even) and 2026 is right (idx2 is odd)
                year = 2025 if idx2 % 2 == 0 else 2026 
                start_iso = month_day_to_iso(year, m1, d1)
                end_iso = month_day_to_iso(year, m2, d2)
                
                if year == 2025:
                    date_pairs_2025.append([start_iso, end_iso])
                else:
                    date_pairs_2026.append([start_iso, end_iso])

            # Now read the points lines: Fri-Sat, Sun-Thu, Full Week
            fri_line = ln
            sun_line = ""
            full_line = ""

            # Check lines exist before accessing
            if i + 1 < len(lines):
                sun_line = lines[i + 1]
            if i + 2 < len(lines):
                full_line = lines[i + 2]

            def parse_points(line: str) -> List[int]:
                """Extracts integer points from a line."""
                parts = line.split()
                nums = []
                # skip the day-type label (e.g., "FRI-SAT")
                for p in parts[1:]:
                    p = p.replace(",", "").replace("-", "")
                    if p.isdigit():
                        nums.append(int(p))
                return nums

            fri_vals = parse_points(fri_line)
            sun_vals = parse_points(sun_line) if sun_line.upper().startswith("SUN-THU") else []
            full_vals = parse_points(full_line) if full_line.upper().startswith("FULL WEEK") else []

            rows.append({
                "2025": {
                    "date_ranges": date_pairs_2025,
                    "points": {
                        "Fri-Sat": fri_vals,
                        "Sun-Thu": sun_vals,
                        "Full Week": full_vals,
                    },
                },
                "2026": {
                    "date_ranges": date_pairs_2026,
                    "points": {
                        "Fri-Sat": fri_vals,  # same points per row
                        "Sun-Thu": sun_vals,
                        "Full Week": full_vals,
                    },
                }
            })

            # skip over Fri/Sun/Full lines
            i += 3
            continue

        else:
            # accumulate date line candidates 
            if any(mon in ln for mon in MONTHS.keys()):
                current_date_lines.append(ln)

        i += 1

    return rows


@st.cache_data
def find_resort_pages(pdf_file_object: BytesIO, resorts_list: List[str]) -> Dict[str, Union[int, None]]:
    """
    Finds the highest page index where each resort name appears.
    """
    pdf_file_object.seek(0)
    reader = pypdf.PdfReader(pdf_file_object)
    page_map = {}
    
    progress_bar = st.progress(0, text="Searching for resort pages...")
    
    for i, resort in enumerate(resorts_list):
        term = normalize(resort)
        # Remove common, non-unique parts to improve matching
        term = term.replace("MARRIOTT", "").replace("VACATION CLUB", "").strip()
        
        hits = []
        for idx, page in enumerate(reader.pages):
            text = normalize(page.extract_text() or "")
            if term in text:
                hits.append(idx)
        
        page_map[resort] = max(hits) if hits else None
        progress_bar.progress((i + 1) / len(resorts_list), text=f"Searching for **{resort}**...")
        
    progress_bar.empty()
    return page_map


@st.cache_data
def extract_all_resorts(pdf_file_object: BytesIO, resorts_list: List[str]) -> Dict[str, Any]:
    """Coordinates the full extraction process for all resorts."""
    
    # 1. Find the page index for each resort (This reads the file once)
    page_map = find_resort_pages(pdf_file_object, resorts_list) 

    # 2. Re-initialize the reader to ensure we start from the beginning for extraction
    pdf_file_object.seek(0)
    reader = pypdf.PdfReader(pdf_file_object)
    
    result = {}
    
    extraction_progress = st.progress(0, text="Extracting point data...")
    
    for i, resort in enumerate(resorts_list):
        page_idx = page_map.get(resort)
        
        if page_idx is None:
            st.warning(f"[WARN] No page found for resort: **{resort}**")
            continue

        # Extract text from the identified page index
        text = reader.pages[page_idx].extract_text() or ""
        
        # Parse the raw data rows
        rows = extract_resort_blocks_from_page_text(text)
        
        if not rows:
            st.warning(f"[WARN] No point chart data parsed for resort **{resort}** on page {page_idx + 1}.")
            
        result[resort] = {
            "page_index": page_idx + 1, # Display 1-based index
            "rows": rows,
        }
        
        extraction_progress.progress((i + 1) / len(resorts_list), text=f"Extracting data for **{resort}**...")

    extraction_progress.empty()
    return result


# ---------- Main Streamlit Application ----------

def app_main():
    st.set_page_config(page_title="MVC PDF Extractor", layout="wide")
    st.title("Marriott PDF Point Chart Data Extractor")
    st.markdown("This tool automatically extracts all 81+ resorts and their raw season/point data from the **MVC-2026.pdf** chart.")

    # --- File Uploader ---
    uploaded_pdf = st.file_uploader(
        "1. Upload MVC-2026.pdf", 
        type="pdf", 
        help="The Marriott Club Points Chart PDF (e.g., MVC-2026.pdf)"
    )

    st.markdown("---")

    # --- Processing Button ---
    if st.button("2. Start Full Data Extraction", type="primary", disabled=not uploaded_pdf):
        if uploaded_pdf is None:
            st.error("Please upload the PDF file first.")
            return

        # Read the file content into a memory buffer
        pdf_buffer = BytesIO(uploaded_pdf.read())

        with st.spinner("Step 1: Auto-detecting all resort names..."):
            # Auto-extract resort list from PDF
            resorts_list = auto_extract_resorts(pdf_buffer)
            
            if not resorts_list:
                st.error("❌ Failed to automatically detect any resort names. Please check the PDF format.")
                return

        st.success(f"✅ Auto-detection complete! Found **{len(resorts_list)}** potential resorts.")
        
        with st.expander("Review Auto-Detected Resort List", expanded=False):
            st.code('\n'.join(resorts_list), language='text')

        with st.spinner("Step 2: Processing PDF and extracting point data for all resorts..."):
            try:
                # The core logic
                raw_data = extract_all_resorts(pdf_buffer, resorts_list)

                output_dict = {
                    "source_pdf": uploaded_pdf.name,
                    "resorts_list": resorts_list,
                    "raw_rows": raw_data,
                }
                
                output_json_str = json.dumps(output_dict, indent=2)

                st.success("🎉 Extraction Complete! Data is ready for review and download.")
                
                st.subheader("Extracted Raw Data")
                
                # Download Button
                st.download_button(
                    label="Download mvc_2026_raw_rows.json",
                    data=output_json_str,
                    file_name="mvc_2026_raw_rows.json",
                    mime="application/json",
                    type="secondary",
                    help="Click to download the raw extracted JSON data."
                )
                
                # Display the data in an expander
                with st.expander("Review Raw JSON Output", expanded=False):
                    st.json(output_dict)

            except Exception as e:
                st.error("An unexpected error occurred during extraction.")
                st.exception(e) # Display full traceback for debugging


if __name__ == "__main__":
    app_main()
