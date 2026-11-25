"""Step 4: qualitative ISA 570 questionnaire (next 12 months)."""

# What this page does:
# Page 4: ISA 570 questions (No / Yes), result as 3 traffic lights.
# Questions, weights and calculation -> logic/assessment.py, this page only displays them.
# The answers are saved in st.session_state.answers and used again in the overall assessment on page 7.

# Use of generative AI:
# - Code: parts of the code in this file were written with the help of Claude (Anthropic). We reviewed, tested and adjusted them.
# - Comments: Claude was used as support for writing the comments and making sure that the structure fits.

import streamlit as st

import shared                                 # helpers for all pages
from logic import assessment                  # questions + evaluation

st.title("4 · ISA 570 questionnaire")
st.caption("Answer each question for the next 12 months. 'Yes' means the event or condition is "
           "present. Sources: inquiries of management, board minutes, loan agreements, "
           "subsequent events. Questions marked KO set the overall risk to 'High'.")

# dict {question id: True/False}; in session_state so nothing gets lost when switching pages
answers = st.session_state.answers


# --- Button Colours ---

# Streamlit can't colour single buttons, so we use our own CSS (assets/gocon.css, loaded in app.py).
# All answer buttons have a key starting with "q_": No = green, Yes = red.

# --- Questions ---

for cat in assessment.CATEGORIES:             
    st.subheader(cat)
    for q in [q for q in assessment.QUESTIONS if q.category == cat]:   
        c1, c2 = st.columns([5, 1], vertical_alignment="center") # question left, buttons right
        label = f"**{q.id}** · {q.text}"
        c1.markdown(label + (" :red-badge[KO]" if q.knock_out else ""))   
        c1.caption(f"{q.reference} · weight {q.weight}")                 
        # default = answer saved before, otherwise "No"
        choice = c2.segmented_control("Answer", ["No", "Yes"], key=f"q_{q.id}",
                                      default="Yes" if answers.get(q.id) else "No",
                                      label_visibility="collapsed")
        answers[q.id] = choice == "Yes"       # save as True (Yes) / False (No)


# --- Result ---

# score (0-1), 'Yes' answers, knock-outs
res = assessment.evaluate_questionnaire(answers)
st.divider()
c1, c2, c3 = st.columns(3)                    
# red: knock-out or score >= 40 %, amber: > 10 %, else green
status = "red" if res["knock_outs"] or res["score"] >= 0.4 else ("amber" if res["score"] > 0.1 else "green")
with c1:
    # card 1: qualitative risk score in percent
    shared.traffic_light(status, "Qualitative risk score", f"{res['score']:.0%}",
                     f"{res['points']} of {res['max_points']} weighted points")
with c2:
    # card 2: how many questions were answered with 'Yes'
    shared.traffic_light("red" if res["yes"] else "green", "Risk indicators ('Yes')",
                     str(len(res["yes"])), f"of {len(assessment.QUESTIONS)} questions")
with c3:
    # card 3: triggered knock-out criteria
    shared.traffic_light("red" if res["knock_outs"] else "green", "Knock-out criteria",
                     str(len(res["knock_outs"])),
                     ", ".join(q.id for q in res["knock_outs"]) or "none triggered")

shared.next_step("pages/5_liquidity_planner.py", "Continue with step 5: Liquidity planner")   # button to the next page
