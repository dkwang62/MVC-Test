# ============================================================
# Theme Application Function
# ============================================================

def apply_app_theme():
    choice = st.session_state.ui_theme

    # AUTO → follow browser preference
    if choice == "Auto":
        css = '''
        <style>
        @media (prefers-color-scheme: dark) {
            :root {
                --bg-color: #0f172a;
                --card-color: #1e293b;
                --text-color: #e5e7eb;
            }
        }
        @media (prefers-color-scheme: light) {
            :root {
                --bg-color: #ffffff;
                --card-color: #f5f5f5;
                --text-color: #111827;
            }
        }
        .stApp {
            background-color: var(--bg-color);
            color: var(--text-color);
        }
        </style>
        '''
        pio.templates.default = "plotly"

    # DARK MODE
    elif choice == "Dark":
        css = '''
        <style>
        :root {
            --bg-color: #0f172a;
            --card-color: #1e293b;
            --text-color: #e5e7eb;
        }
        .stApp {
            background-color: var(--bg-color);
            color: var(--text-color);
        }
        </style>
        '''
        pio.templates.default = "plotly_dark"

    # LIGHT MODE
    else:
        css = '''
        <style>
        :root {
            --bg-color: #ffffff;
            --card-color: #f5f5f5;
            --text-color: #111827;
        }
        .stApp {
            background-color: var(--bg-color);
            color: var(--text-color);
        }
        </style>
        '''
        pio.templates.default = "plotly"

    st.markdown(css, unsafe_allow_html=True)
