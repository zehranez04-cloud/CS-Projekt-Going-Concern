"""Step 4: qualitative ISA 570 questionnaire (next 12 months)."""

import streamlit as st

import shared
from logic import assessment

st.title("4 · ISA 570 questionnaire")
st.caption("Answer each question for the next 12 months. 'Yes' means the event or condition is "
           "present. Sources: inquiries of management, board minutes, loan agreements, "
           "subsequent events. Questions marked KO set the overall risk to 'High'.")

answers = st.session_state.answers

st.html(f"""<style>
[class*="st-key-q_"] button[aria-checked="true"]:nth-of-type(1) {{
    background-color: {shared.GREEN_HEX} !important; border-color: {shared.GREEN_HEX} !important;
    color: white !important; }}
[class*="st-key-q_"] button[aria-checked="true"]:nth-of-type(2) {{
    background-color: {shared.RED_HEX} !important; border-color: {shared.RED_HEX} !important;
    color: white !important; }}
</style>""")

for cat in assessment.CATEGORIES:
    st.subheader(cat)
    for q in [q for q in assessment.QUESTIONS if q.category == cat]:
        c1, c2 = st.columns([5, 1], vertical_alignment="center")
        label = f"**{q.id}** · {q.text}"
        c1.markdown(label + (" :red-badge[KO]" if q.knock_out else ""))
        c1.caption(f"{q.reference} · weight {q.weight}")
        choice = c2.segmented_control("Answer", ["No", "Yes"], key=f"q_{q.id}",
                                      default="Yes" if answers.get(q.id) else "No",
                                      label_visibility="collapsed")
        answers[q.id] = choice == "Yes"
        
# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
res = assessment.evaluate_questionnaire(answers)
st.divider()
c1, c2, c3 = st.columns(3)
status = "red" if res["knock_outs"] or res["score"] >= 0.4 else ("amber" if res["score"] > 0.1 else "green")
with c1:
    shared.traffic_light(status, "Qualitative risk score", f"{res['score']:.0%}",
                     f"{res['points']} of {res['max_points']} weighted points")
with c2:
    shared.traffic_light("red" if res["yes"] else "green", "Risk indicators ('Yes')",
                     str(len(res["yes"])), f"of {len(assessment.QUESTIONS)} questions")
with c3:
    shared.traffic_light("red" if res["knock_outs"] else "green", "Knock-out criteria",
                     str(len(res["knock_outs"])),
                     ", ".join(q.id for q in res["knock_outs"]) or "none triggered")

shared.next_step("pages/5_liquidity_planner.py", "Continue with step 5: Liquidity planner")
