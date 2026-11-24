"""
Going Concern Audit - Streamlit app (entry point)

Start with:   streamlit run app.py

The app guides an auditor through the going concern procedure of ISA 570:
    1. Company profile       - engagement data, industry, size, group (user input)
    2. Financial statements  - upload, AI standardisation, review
    3. Ratio analysis        - legal thresholds (Swiss CO), ratios, trends
    4. ISA 570 questionnaire - qualitative events and conditions
    5. Liquidity planner     - 12-month plan incl. restructuring measures (CO Art. 725)
    6. Bankruptcy model      - machine learning on the Polish bankruptcy dataset
    7. Assessment & report   - combined result, auditor's conclusion, PDF export
    +  Audit files           - saved engagements (SQLite database)

Folders:  pages/ = what the user sees (one file per step)
          logic/ = calculations (data input, analysis, assessment, ML, documentation)
"""

# Entry point: sets up the session state, loads the GoCon design for all pages,
# defines the navigation and shows the progress of the engagement in the sidebar.
# Use of generative AI:
# - Code: parts of the code in this file were written with the help of Claude (Anthropic). We reviewed, tested and adjusted them.
# - Comments: Claude was used as support for writing the comments and making sure that the structure fits. We checked and partly adjusted them.

from pathlib import Path

import streamlit as st

import shared

st.set_page_config(page_title="GoCon · Going Concern Audit", page_icon="assets/logo_gc.png",
                   layout="wide")
shared.init()

# The CSS file is read and passed as text, which works in every Streamlit version.
CSS_FILE = Path(__file__).parent / "assets" / "gocon.css"
st.html(f"<style>{CSS_FILE.read_text(encoding='utf-8')}</style>")
st.logo("assets/logo_gc.png", size="large")

# --- Navigation ---
pages = {
    "Overview": [
        st.Page("pages/0_home.py", title="Home", icon=":material/home:", default=True),
    ],
    "Audit procedure": [
        st.Page("pages/1_company_profile.py", title="1 · Company profile", icon=":material/domain:"),
        st.Page("pages/2_financial_statements.py", title="2 · Financial statements", icon=":material/upload_file:"),
        st.Page("pages/3_ratio_analysis.py", title="3 · Ratio analysis", icon=":material/monitoring:"),
        st.Page("pages/4_questionnaire.py", title="4 · ISA 570 questionnaire", icon=":material/checklist:"),
        st.Page("pages/5_liquidity_planner.py", title="5 · Liquidity planner", icon=":material/savings:"),
        st.Page("pages/6_bankruptcy_model.py", title="6 · Bankruptcy model", icon=":material/model_training:"),
        st.Page("pages/7_assessment_report.py", title="7 · Assessment & report", icon=":material/gavel:"),
    ],
    "Records": [
        st.Page("pages/8_audit_files.py", title="Audit files", icon=":material/folder_open:"),
    ],
}
nav = st.navigation(pages)

# --- Sidebar: current engagement and progress ---
with st.sidebar:
    eng = st.session_state.engagement
    st.markdown(f"**Client:** {eng['client'] or '–'}  \n**Financial year:** {eng['fiscal_year'] or '–'}  \n"
                f"**Industry:** {st.session_state.profile['industry']}")
    ys = shared.years()
    # a step counts as done as soon as its data exists in the session state
    steps = [
        ("Company profile", st.session_state.profile_confirmed),
        ("Financial statements", bool(ys)),
        ("Questionnaire", len(st.session_state.answers) > 0),
        ("Liquidity plan", st.session_state.liquidity_inputs is not None),
        ("Auditor's conclusion", bool(st.session_state.conclusion)),
    ]
    st.caption("Progress")
    for label, done in steps:
        st.markdown(f"{':material/check_circle:' if done else ':material/radio_button_unchecked:'} {label}")

nav.run()
