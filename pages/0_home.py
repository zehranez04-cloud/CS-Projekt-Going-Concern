"""Home page: problem statement and how the app works."""

import streamlit as st

import shared

st.title("Going Concern Audit")
st.markdown("##### Supporting auditors in assessing whether a company can continue as a going concern")

# ---------------------------------------------------------------------------
# Problem statement (grading requirement 1)
# ---------------------------------------------------------------------------
c1, c2 = st.columns([3, 2], gap="large")
with c1:
    st.subheader("The problem")
    st.markdown(
        "In every financial statement audit the auditor must conclude whether management's use "
        "of the **going concern basis of accounting** is appropriate and whether a **material "
        "uncertainty** exists (ISA 570). In Switzerland, the board must additionally act on "
        "**impending insolvency, capital loss and over-indebtedness** (CO Art. 725–725b).\n\n"
        "Today this procedure is largely manual: annual reports come in different layouts and "
        "accounting standards, ratios are calculated in spreadsheets, and the ISA 570 checklist, "
        "the liquidity plan and the documentation live in separate files.")
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
with c2:
    with st.container(border=True):
        st.markdown("**Who uses it?**  \nExternal auditors (e.g. audit assistants and managers) "
                    "during the planning and completion phase of an audit.")
        st.markdown("**Important**  \nThe app supports professional judgement – it does not "
                    "replace it. The final conclusion is always recorded by the auditor.")

st.divider()
st.subheader("Workflow")
steps = [
    (":material/domain:", "1 · Company profile", "Industry, size, group"),
    (":material/upload_file:", "2 · Financial statements", "Upload & standardise with AI"),
    (":material/monitoring:", "3 · Ratio analysis", "Legal tests, ratios, trends"),
    (":material/checklist:", "4 · Questionnaire", "ISA 570 events and conditions"),
    (":material/savings:", "5 · Liquidity planner", "12 months, CO Art. 725"),
    (":material/model_training:", "6 · Bankruptcy model", "Machine learning score"),
    (":material/gavel:", "7 · Assessment & report", "Conclusion and PDF"),
]
cols = st.columns(len(steps))
for col, (icon, title, text) in zip(cols, steps):
    with col.container(border=True, height=150):
        st.markdown(f"### {icon}")
        st.markdown(f"**{title}**")
        st.caption(text)

shared.next_step("pages/1_company_profile.py", "Start with step 1: Company profile")
