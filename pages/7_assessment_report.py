# STEP 7 - ASSESSMENT & REPORT (combined result, auditor's conclusion, PDF export, saving)

#First to show what this page does:
    #1. The user sets how strongly each source counts (weights of the components).
    #2. The app combines ratios, questionnaire and ML model into one going concern risk and shows it as a gauge, traffic light and list of warning signals.
    #   Two charts show how the score is composed and whether the risk level depends on the weighting.
    #3. The auditor records his/her own conclusion (ISA 570.17-23); the app derives the implication for the auditor's report.
    #4. Everything is documented: PDF working paper for download and saving as an audit file in the database.

#Why it matters for the audit: The app proposes, the auditor decides (professional judgement). 
#This page brings together the results of all previous steps and documents the final conclusion.

import plotly.graph_objects as go             # library for interactive charts (here: the risk gauge)
import streamlit as st

import shared                                 # helper functions used by all pages
from logic import assessment, documentation   # overall assessment logic / PDF and database -> our own files

st.title("7 · Assessment & report")           # title for this page in the website
ys = shared.require_financials()              # loaded financial years; stops the page if none are loaded
ss = st.session_state                         # short name for the session state

# ---------------------------------------------------------------------------
# Weights of the components (user interaction)
# ---------------------------------------------------------------------------
# First we've implemented three sliders, where the auditor can decide on how strongly do ratios, questionnaire and ML model count in the overall score.
# The values range between 0 and 1 in steps of 0.05; they are normalised later, so they do not have to add up to 1.

st.subheader("Weighting of the components", anchor=False)                                       # anchor=False: no link symbol
st.caption("How strongly should each source count? The weights are normalised to 100 %.")
with st.container(border=True):                                                                 # box with a frame around the three sliders
    c1, c2, c3 = st.columns(3)
    w = ss.weights                                                                              # current weights (dictionary stored in the session state)
 # slider(label, minimum, maximum, current value, step); the new value is written back into w
    w["quantitative"] = c1.slider("Ratios", 0.0, 1.0, w["quantitative"], 0.05)
    w["qualitative"] = c2.slider("ISA 570 questionnaire", 0.0, 1.0, w["qualitative"], 0.05)
    w["ml"] = c3.slider("ML model", 0.0, 1.0, w["ml"], 0.05)

# Now we calculate the overall result with the current weights (see logic/assessment.py) and the result of the liquidity plan (only if the liquidity plan was prepared on page 5)
res = shared.overall_assessment()
liq = shared.liquidity_result()

# ---------------------------------------------------------------------------
# Result
# Now the results of the audit procedure get shown
# ---------------------------------------------------------------------------
c1, c2 = st.columns([1, 2], gap="large")   # left 1/3 (gauge), right 2/3 (text)

# Left: gauge (speedometer) showing the risk score from 0 to 100 %
with c1:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=res["score"] * 100, number={"suffix": " %"},         # score 0-1 -> 0-100 %
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#1E2B33"},              # dark pointer bar
               
               # coloured zones: 0-30 % low (green), 30-60 % medium (amber), 60-100 % high (red)
               "steps": [{"range": [0, 30], "color": shared.GREEN_HEX},
                         {"range": [30, 60], "color": shared.AMBER_HEX},
                         {"range": [60, 100], "color": shared.RED_HEX}]}))
    
    fig.update_layout(height=260, margin=dict(t=30, b=0, l=40, r=40))                   # height and margins in pixels
    st.plotly_chart(fig, width="stretch")                                               # show the chart, full column width

# Right: traffic-light card with risk level and explanation (what to do next under ISA 570)
with c2:
    shared.traffic_light(res["colour"], "Going concern risk", res["level"], res["text"])

    # Knock-out criteria set the risk to "High" regardless of the score -> red box with the list
    if res["knock_outs"]:
        st.error("**Knock-out criteria triggered** – risk set to High:\n\n" +
                 "\n".join(f"- {k}" for k in res["knock_outs"]))
        
    # now we provide a hint if the liquidity plan (needed for CO Art. 725) is still missing
    if liq is None:
        st.info("The liquidity plan (CO Art. 725) has not been prepared yet.")

# Three small figures below: score of each component and its share of the total weight
p, wn = res["parts"], res["weights"]       # p = scores of the components, wn = weights used
tot = sum(wn.values()) or 1                # sum of the weights (1 if all are 0, to avoid dividing by 0)
cols = st.columns(3)
# zip pairs each column with one component: (column, (internal name, label))
for col, (key, label) in zip(cols, [("quantitative", "Ratios"), ("qualitative", "Questionnaire"),
                                    ("ml", "ML model")]):
    # e.g. "Ratios · weight 40%" with the value "88%"; "not used" if the weight is 0
    col.metric(f"{label} · weight {wn[key] / tot:.0%}", f"{p[key]:.0%}" if wn[key] else "not used")

# List of all warning signals (ratios, legal tests, questionnaire, profile), opened by default:
with st.expander(f"All warning signals ({len(res['signals'])})", expanded=True):
    for source, text in res["signals"] or [("–", "No warning signals")]:                   # if the list is empty: "No warning signals"
        st.markdown(f"- **{source}:** {text}")                                             # e.g. "- Ratio: Cash ratio: 0.02"

# ---------------------------------------------------------------------------
# Composition and robustness of the score
# The auditor has to be able to explain the result (ISA 230: documentation). Therefore we show
# (1) how much each source contributes to the score and (2) whether the risk level would change
# with a different weighting of ratios and questionnaire.
# Use of generative AI: this block was written with the help of Claude (Anthropic) and was checked and tested by us.
# ---------------------------------------------------------------------------
st.subheader("Composition and robustness of the score", anchor=False)
c1, c2 = st.columns(2, gap="large")

# Left: one stacked bar. Each segment = weight x score of one source; the whole bar = overall score.
with c1:
    st.caption("Contribution of each source to the overall score (weight × score).")
    fig = go.Figure()
    # one colour per source (dark blue, light blue, grey); the traffic-light colours stay reserved for risk
    for row, colour in zip(assessment.score_breakdown(res), ["#1E2B33", "#5B8DB8", "#A0A0A0"]):
        if row["weight"] == 0:                                             # source not used -> no segment
            continue
        fig.add_bar(y=["Score"], x=[row["contribution"] * 100], orientation="h",   # horizontal bar, in %
                    name=row["label"], marker_color=colour,
                    # text shown when the mouse is over the segment
                    hovertemplate=(f"{row['label']}: weight {row['weight']:.0%} × score "
                                   f"{row['score']:.0%} = {row['contribution']:.1%}<extra></extra>"))
    fig.update_layout(barmode="stack", height=200, margin=dict(t=10, b=0, l=0, r=10),
                      xaxis=dict(range=[0, 100], dtick=25, ticksuffix=" %"), yaxis=dict(visible=False),
                      legend=dict(orientation="h", y=-0.5))                 # legend below the bar
    st.plotly_chart(fig, width="stretch")

# Right: line chart. x = share of the ratios, y = overall score; the background shows the three risk zones.
with c2:
    st.caption("Score for every split between ratios and questionnaire (ML share unchanged).")
    sens = assessment.weight_sensitivity(res)                               # list of dicts, see logic/assessment.py
    fig = go.Figure()
    # coloured zones as in the gauge above: low (green), medium (amber), high (red)
    for low, high, colour in [(0, 30, shared.GREEN_HEX), (30, 60, shared.AMBER_HEX), (60, 100, shared.RED_HEX)]:
        fig.add_hrect(y0=low, y1=high, fillcolor=colour, opacity=0.25, line_width=0)
    fig.add_scatter(x=[r["ratio_share"] * 100 for r in sens], y=[r["score"] * 100 for r in sens],
                    mode="lines+markers", line=dict(color="#1E2B33"), name="Score",
                    hovertemplate="Ratios %{x:.0f} %: score %{y:.0f} %<extra></extra>")
    fig.update_layout(height=200, margin=dict(t=10, b=0, l=0, r=10), showlegend=False,
                      xaxis=dict(title="Share of ratios (rest: questionnaire)", ticksuffix=" %"),
                      yaxis=dict(range=[0, 100], ticksuffix=" %"))
    st.plotly_chart(fig, width="stretch")

# One sentence that tells the auditor how much the result depends on the weighting
levels = list(dict.fromkeys(r["level"] for r in sens))      # levels that occur, without duplicates, in order
if res["knock_outs"]:
    st.info("The risk level does not depend on the weighting: a knock-out criterion sets it to High.")
elif len(levels) == 1:
    st.success(f"Robust result: the risk level is **{levels[0]}** for every weighting of ratios and questionnaire.")
else:
    st.warning("The risk level depends on the weighting (" + " / ".join(levels) + "). "
               "Document why the chosen weights are appropriate for this client.")

# ---------------------------------------------------------------------------
# Auditor's conclusion (ISA 570.17-23) - professional judgement
# Now we come to the auditor's final conclusion, which also includes their professional judgement
# Therefore we have three questions provided to form the auditors conclusion, which are implemented in the following part of the code
# ---------------------------------------------------------------------------
# logic: Decision tree of ISA 570 with three questions. The answers determine the type of audit opinion. The app only derives the consequence; the auditor makes the decision.

st.subheader("Auditor's conclusion")
st.caption("The app proposes, the auditor decides. Record your conclusion; the app derives the "
           "implication for the auditor's documentation.")
prev = ss.conclusion                       # conclusion recorded earlier (empty dictionary if none)
c1, c2, c3 = st.columns(3)

# Question 1. Pre-selection (index): the previous answer, otherwise "Yes" (normal case)
basis = c1.radio("Is the going concern basis of accounting appropriate?", ["Yes", "No"],
                 index=0 if prev.get("basis", True) else 1)

# Question 2. Pre-selection: previous answer, otherwise "No" (normal case).
# Greyed out if question 1 = "No" (then the answer to this question doesn't matter anymore)
uncert = c2.radio("Does a material uncertainty exist?", ["Yes", "No"],
                  index=0 if prev.get("uncertainty") else 1, disabled=basis == "No")

# Question 3. Only relevant if a material uncertainty exists -> otherwise greyed out
discl = c3.radio("Is it adequately disclosed in the notes?", ["Yes", "No"],
                 index=0 if prev.get("disclosed", True) else 1,
                 disabled=basis == "No" or uncert == "No")
comment = st.text_area("Comment / rationale", prev.get("comment", ""))   # Here the auditor can write free text in a textbox, e.g. state some things they've seen in the audit process that support their decision regarding their conclusion. 
                                                                         #This tool is needed, as a part of the conclusion lays in the professional judgement of an auditor. 

# Now we derive the type of audit opinion from the three answers (see logic/assessment.py), e.g. ("Adverse opinion", "The going concern basis of accounting is inappropriate (ISA 570.21).")
# basis == "Yes" turns the text answer into True/False
opinion, reason = assessment.report_implication(basis == "Yes", uncert == "Yes", discl == "Yes")
st.info(f"**Implication for the auditor's report:** {opinion}  \n{reason}")

# Save the conclusion in the session state (used in the PDF and the database)
if st.button("Record conclusion", type="primary"):
    ss.conclusion = {"basis": basis == "Yes", "uncertainty": uncert == "Yes",
                     "disclosed": discl == "Yes", "comment": comment,
                     "opinion": opinion, "reason": reason}
    st.rerun()                             # reload the page so the progress list in the sidebar updates
if ss.conclusion:
    st.success("Conclusion recorded.")

# ---------------------------------------------------------------------------
# PDF export and saving to the database
# We then provide with the possibility to export a pdf document, where all the audited steps and important conclusions are stated
# This can be called the overall output of our whole product, being a tool which accesses the going concern of a company in the audit process
# ---------------------------------------------------------------------------
st.subheader("Documentation")

# ML information for the PDF, only provided if the model has been trained
pkg = shared.model_package()               # trained model (None if not trained yet)
ml_info = None
if pkg:
    s, _ = shared.ml_score(ys[-1])         # risk score of the latest year (the explanation "_" is not needed here)
    ml_info = {"score": s, "n": pkg["metrics"]["n"], "auc": pkg["metrics"]["auc_logreg"]}

# Create the PDF from the results of all steps (see build_pdf in our file: logic/documentation.py)
pdf = documentation.build_pdf(ss.engagement, ys, res, shared.legal_tests(ys[-1]), liq, ml_info, ss.conclusion,
                       ss.profile)

# File name of the PDF, e.g. "going_concern_Alpenwerk_Machines_AG.pdf" (the spaces get replaced by "_", as it is the standard format of naming documents)
client = (ss.engagement["client"] or "client").replace(" ", "_")
c1, c2 = st.columns(2)

# Left button: here we provide a download button for the pdf export (mime = file type, so the browser knows that it's a pdf)
c1.download_button("Download PDF working paper", pdf, file_name=f"going_concern_{client}.pdf",
                   mime="application/pdf", icon=":material/picture_as_pdf:", width="stretch")

# Right button: with a click on this button the auditor can save the whole engagement as an audit file in the SQLite database (this can be loaded again on the page "Audit files")
if c2.button("Save to audit files", icon=":material/save:", width="stretch"):
    ss.result = {"level": res["level"], "score": res["score"]}   # result shown in the list of audit files
    new_id = documentation.save_audit_file(ss)                   # save and get the number of the new audit file
    st.toast(f"Saved as audit file #{new_id}")                   # small pop-up message that confirms that the audit file was saved in the database
