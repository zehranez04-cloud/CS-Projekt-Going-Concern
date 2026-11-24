"""Home page: problem statement and how the app works."""

# Landing page: logo, the problem the app solves, our solution and the seven-step workflow.
# Use of generative AI:
# - Code: parts of the code in this file were written with the help of Claude (Anthropic). We reviewed, tested and adjusted them.
# - Comments: Claude was used as support for writing the comments and making sure that the structure fits. We checked and partly adjusted them.

import streamlit as st

import shared

# style: .st-key-hero in assets/gocon.css
with st.container(key="hero"):
    st.image("assets/logo_gocon.png", width="stretch")

# "Bento" layout: every container with a key "panel-..." or "card-..." gets its
# background colour from assets/gocon.css
with st.container(key="panel-intro"):
    st.title("Going Concern Audit")
    st.markdown("##### Supporting auditors in assessing whether a company can continue as a going concern")

# --- Problem statement (grading requirement 1) ---
c1, c2 = st.columns([3, 2], gap="small")              # small gap = same spacing as between the colour blocks
with c1:
    with st.container(key="panel-problem"):
        st.subheader("The problem")
        st.markdown(
            "In every financial statement audit the auditor must conclude whether management's use "
            "of the **going concern basis of accounting** is appropriate and whether a **material "
            "uncertainty** exists (ISA 570). In Switzerland, the board must additionally act on "
            "**impending insolvency, capital loss and over-indebtedness** (CO Art. 725–725b).\n\n"
            "Today this procedure is largely manual: annual reports come in different layouts and "
            "accounting standards, ratios are calculated in spreadsheets, and the ISA 570 checklist, "
            "the liquidity plan and the documentation live in separate files.")
with c2:
    with st.container(key="card-who"):
        st.markdown("**Who uses it?**  \nExternal auditors (e.g. audit assistants and managers) "
                    "during the planning and completion phase of an audit.")
    with st.container(key="card-important"):
        st.markdown("**Important**  \nThe app supports professional judgement – it does not "
                    "replace it. The final conclusion is always recorded by the auditor.")

# --- Solution ---
with st.container(key="panel-solution"):                # the CSS splits the list into two columns on desktop
    st.subheader("Our solution")
    st.markdown(
        "One web app that takes the auditor through the complete procedure – from the uploaded "
        "annual report to a documented conclusion:\n"
        "- A **company profile** (industry, size, group) that adapts the thresholds\n"
        "- **AI** turns any annual report into a standardised format\n"
        "- **Ratios with traffic lights** and a **3–5 year trend** analysis\n"
        "- An **ISA 570 questionnaire** for events and conditions in the next 12 months\n"
        "- A **12-month liquidity planner** incl. restructuring measures (CO Art. 725)\n"
        "- A **machine learning model** trained on real bankruptcy data\n"
        "- A combined **risk assessment**, the auditor's conclusion and a **PDF working paper**")

# --- Workflow ---
steps = [
    (":material/domain:", "1 · Company profile"),
    (":material/upload_file:", "2 · Financial statements"),
    (":material/monitoring:", "3 · Ratio analysis"),
    (":material/checklist:", "4 · Questionnaire"),
    (":material/savings:", "5 · Liquidity planner"),
    (":material/model_training:", "6 · Bankruptcy model"),
    (":material/gavel:", "7 · Assessment & report"),
]
with st.container(key="panel-workflow"):
    st.subheader("Workflow")
    # two rows of four cards (the second row has three)
    for row_start in (0, 4):
        cols = st.columns(4)
        for i, (col, (icon, title)) in enumerate(zip(cols, steps[row_start:row_start + 4]), start=row_start):
            with col.container(key=f"card-workflow-{i}"):
                st.markdown(f"### {icon}")
                st.markdown(f"**{title}**")

shared.next_step("pages/1_company_profile.py", "Start with step 1: Company profile")
