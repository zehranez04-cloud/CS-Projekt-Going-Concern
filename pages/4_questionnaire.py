"""Step 4: qualitative ISA 570 questionnaire (next 12 months)."""

# What this page does:
#   questions  the ISA 570 events and conditions, grouped by category, each answered with No / Yes
#   result     three traffic-light cards: qualitative risk score, number of 'Yes' answers, knock-outs
# The questions, weights and the calculation are in logic/assessment.py; this file only shows them.
# The answers are saved in st.session_state.answers and used again in the overall assessment (page 7).
# Use of generative AI: the comments in this file were written with the help of Claude (Anthropic) and checked by us.

import streamlit as st

import shared                                 # helper functions used by all pages
from logic import assessment                  # our own file: questions, weights, evaluation

st.title("4 · ISA 570 questionnaire")
st.caption("Answer each question for the next 12 months. 'Yes' means the event or condition is "
           "present. Sources: inquiries of management, board minutes, loan agreements, "
           "subsequent events. Questions marked KO set the overall risk to 'High'.")

# dict {question id: True/False}; lives in the session state, so the answers stay
# when the user switches to another page and comes back
answers = st.session_state.answers

# ---------------------------------------------------------------------------
# Colours of the answer buttons
# ---------------------------------------------------------------------------
# Streamlit has no option to colour single buttons, so we use our own CSS (in assets/gocon.css,
# loaded for all pages in app.py): every answer widget has a key starting with "q_" (see below).
# If the selected button is the 1st one ("No") it becomes green, if it is the 2nd one ("Yes") red.

# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------
for cat in assessment.CATEGORIES:             # one section per category
    st.subheader(cat)
    for q in [q for q in assessment.QUESTIONS if q.category == cat]:   # questions of this category
        # wide column for the question text, narrow column for the No / Yes buttons
        c1, c2 = st.columns([5, 1], vertical_alignment="center")
        label = f"**{q.id}** · {q.text}"
        c1.markdown(label + (" :red-badge[KO]" if q.knock_out else ""))   # red KO badge for knock-out questions
        c1.caption(f"{q.reference} · weight {q.weight}")                  # ISA reference and weight below the text
        # No / Yes switch; the default is the answer saved before (or "No" if not answered yet)
        choice = c2.segmented_control("Answer", ["No", "Yes"], key=f"q_{q.id}",
                                      default="Yes" if answers.get(q.id) else "No",
                                      label_visibility="collapsed")
        answers[q.id] = choice == "Yes"       # save as True (Yes) / False (No)

# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
# score = weighted 'Yes' points / maximum points (0-1), plus the lists of 'Yes' answers and knock-outs
res = assessment.evaluate_questionnaire(answers)
st.divider()
c1, c2, c3 = st.columns(3)                    # three cards side by side
# traffic light: red if a knock-out is triggered or score >= 40 %, amber if > 10 %, otherwise green
status = "red" if res["knock_outs"] or res["score"] >= 0.4 else ("amber" if res["score"] > 0.1 else "green")
with c1:
    # card 1: qualitative risk score in percent
    shared.traffic_light(status, "Qualitative risk score", f"{res['score']:.0%}",
                     f"{res['points']} of {res['max_points']} weighted points")
with c2:
    # card 2: how many questions were answered with 'Yes' (red as soon as there is one)
    shared.traffic_light("red" if res["yes"] else "green", "Risk indicators ('Yes')",
                     str(len(res["yes"])), f"of {len(assessment.QUESTIONS)} questions")
with c3:
    # card 3: triggered knock-out criteria with their question ids
    shared.traffic_light("red" if res["knock_outs"] else "green", "Knock-out criteria",
                     str(len(res["knock_outs"])),
                     ", ".join(q.id for q in res["knock_outs"]) or "none triggered")

shared.next_step("pages/5_liquidity_planner.py", "Continue with step 5: Liquidity planner")   # button to the next page
