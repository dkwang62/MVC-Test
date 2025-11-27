# ============================================================
# Safe Theme System (No blank screens)
# ============================================================

def apply_app_theme():
    theme = st.session_state.ui_theme

    # SAFEST CSS: only override text + background, nothing else.
    if theme == "Dark":
        css = """
        <style>
        body, .stApp {
            background-color: #0f172a !important;
            color: #e5e7eb !important;
        }
        </style>
        """
        pio.templates.default = "plotly_dark"

    elif theme == "Light":
        css = """
        <style>
        body, .stApp {
            background-color: #ffffff !important;
            color: #111827 !important;
        }
        </style>
        """
        pio.templates.default = "plotly"

    else:  # AUTO mode
        css = """
        <style>
        @media (prefers-color-scheme: dark) {
            body, .stApp {
                background-color: #0f172a !important;
                color: #e5e7eb !important;
            }
        }
        @media (prefers-color-scheme: light) {
            body, .stApp {
                background-color: #ffffff !important;
                color: #111827 !important;
            }
        }
        </style>
        """
        pio.templates.default = "plotly"

    st.markdown(css, unsafe_allow_html=True)
