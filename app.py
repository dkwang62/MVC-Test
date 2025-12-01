import streamlit as st
import calculator
import editor

# Page Config MUST be first
st.set_page_config(
    page_title="MVC Tools",
    layout="wide",
    initial_sidebar_state="collapsed", # Better for mobile
    menu_items={"About": "MVC Tools Mobile"}
)

# Minimal CSS to fix padding on mobile
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 2rem; }
        [data-testid="stSidebar"] { min-width: 200px; max-width: 300px; }
    </style>
""", unsafe_allow_html=True)

def main():
    # Top Navigation (Segmented Control is cleaner than Sidebar for main switch)
    # Using columns to center it lightly
    
    with st.sidebar:
        st.markdown("### 🛠️ Menu")
        tool = st.radio("Select Tool", ["Calculator", "Editor"], label_visibility="collapsed")

    if tool == "Calculator":
        calculator.run()
    else:
        editor.run()

if __name__ == "__main__":
    main()
