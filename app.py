import streamlit as st
import calculator
import editor

# Page Config MUST be first
st.set_page_config(
    page_title="MVC Tools",
    layout="wide",
    initial_sidebar_state="collapsed", 
    menu_items={"About": "MVC Tools Mobile"}
)

# --- CSS FIXES ---
st.markdown("""
    <style>
        /* Increased padding-top to 3.5rem to clear iPhone Notch/Status Bar */
        .block-container { 
            padding-top: 3.5rem !important; 
            padding-bottom: 2rem !important; 
            max-width: 100% !important; /* Ensure full width on mobile */
        }
        [data-testid="stSidebar"] { min-width: 200px; max-width: 300px; }
    </style>
""", unsafe_allow_html=True)

def main():
    with st.sidebar:
        st.markdown("### 🛠️ Menu")
        tool = st.radio("Select Tool", ["Calculator", "Editor"], label_visibility="collapsed")

    if tool == "Calculator":
        calculator.run()
    else:
        editor.run()

if __name__ == "__main__":
    main()
