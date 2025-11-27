# ============================================================
# Cloud-Safe Theme System (fixes blank screen)
# ============================================================

def apply_app_theme():
    theme = st.session_state.ui_theme

    # DARK MODE
    if theme == "Dark":
        css = """
        <script>
        window.addEventListener('DOMContentLoaded', function() {
            document.body.style.backgroundColor = "#0f172a";
            document.body.style.color = "#e5e7eb";
            var app = document.querySelector('.stApp');
            if (app) {
                app.style.backgroundColor = "#0f172a";
                app.style.color = "#e5e7eb";
            }
        });
        </script>
        """
        pio.templates.default = "plotly_dark"

    # LIGHT MODE
    elif theme == "Light":
        css = """
        <script>
        window.addEventListener('DOMContentLoaded', function() {
            document.body.style.backgroundColor = "#ffffff";
            document.body.style.color = "#111827";
            var app = document.querySelector('.stApp');
            if (app) {
                app.style.backgroundColor = "#ffffff";
                app.style.color = "#111827";
            }
        });
        </script>
        """
        pio.templates.default = "plotly"

    # AUTO MODE
    else:
        css = """
        <script>
        window.addEventListener('DOMContentLoaded', function() {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

            if (prefersDark) {
                document.body.style.backgroundColor = "#0f172a";
                document.body.style.color = "#e5e7eb";
            } else {
                document.body.style.backgroundColor = "#ffffff";
                document.body.style.color = "#111827";
            }

            var app = document.querySelector('.stApp');
            if (app) {
                if (prefersDark) {
                    app.style.backgroundColor = "#0f172a";
                    app.style.color = "#e5e7eb";
                } else {
                    app.style.backgroundColor = "#ffffff";
                    app.style.color = "#111827";
                }
            }
        });
        </script>
        """
        pio.templates.default = "plotly"

    st.markdown(css, unsafe_allow_html=True)
