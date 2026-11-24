# Step 7 - Assessment & report: combines ratios, questionnaire and ML model into one going concern
# risk, records the auditor's conclusion (ISA 570.17-23) and documents everything as PDF and audit file.
# The app proposes, the auditor decides (professional judgement).
# Use of generative AI:
# - Code: parts of the code in this file were written with the help of Claude (Anthropic). We reviewed, tested and adjusted them.
# - Comments: Claude was used as support for writing the comments and making sure that the structure fits. We checked and partly adjusted them.

import plotly.graph_objects as go
import streamlit as st

import shared
from logic import assessment, documentation

st.title("7 · Assessment & report")
ys = shared.require_financials()
ss = st.session_state

# --- Weights of the components ---
# The weights are normalised in assess() (logic/assessment.py), so they do not have to add up to 1.

st.subheader("Weighting of the components", anchor=False)                                       # anchor=False: no link symbol
st.caption("How strongly should each source count? The weights are normalised to 100 %.")
with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    w = ss.weights                                                                              # reference: slider values are saved directly
    w["quantitative"] = c1.slider("Ratios", 0.0, 1.0, w["quantitative"], 0.05)
    w["qualitative"] = c2.slider("ISA 570 questionnaire", 0.0, 1.0, w["qualitative"], 0.05)
    w["ml"] = c3.slider("ML model", 0.0, 1.0, w["ml"], 0.05)

res = shared.overall_assessment()
liq = shared.liquidity_result()                # None if the liquidity plan (page 5) was not prepared

# --- Result ---
c1, c2 = st.columns([1, 2], gap="large")

with c1:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=res["score"] * 100, number={"suffix": " %"},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": shared.TEXT},

               # same zones as LEVELS in logic/assessment.py: < 30 % low, < 60 % medium, else high
               "steps": [{"range": [0, 30], "color": shared.GREEN_HEX},
                         {"range": [30, 60], "color": shared.AMBER_HEX},
                         {"range": [60, 100], "color": shared.RED_HEX}]}))

    fig.update_layout(height=260, margin=dict(t=30, b=0, l=40, r=40))
    st.plotly_chart(fig, width="stretch")

with c2:
    shared.traffic_light(res["colour"], "Going concern risk", res["level"], res["text"])

    # knock-outs set the risk to "High" regardless of the score
    if res["knock_outs"]:
        st.error("**Knock-out criteria triggered** – risk set to High:\n\n" +
                 "\n".join(f"- {k}" for k in res["knock_outs"]))

    # without the plan, impending insolvency (CO Art. 725) cannot be assessed
    if liq is None:
        st.info("The liquidity plan (CO Art. 725) has not been prepared yet.")

# Score of each component and its share of the total weight
p, wn = res["parts"], res["weights"]
tot = sum(wn.values()) or 1                # "or 1" avoids dividing by 0 if all weights are 0
cols = st.columns(3)
for col, (key, label) in zip(cols, [("quantitative", "Ratios"), ("qualitative", "Questionnaire"),
                                    ("ml", "ML model")]):
    col.metric(f"{label} · weight {wn[key] / tot:.0%}", f"{p[key]:.0%}" if wn[key] else "not used")

with st.expander(f"All warning signals ({len(res['signals'])})", expanded=True):
    for source, text in res["signals"] or [("–", "No warning signals")]:
        st.markdown(f"- **{source}:** {text}")

# --- Composition and robustness of the score ---
# The auditor must be able to explain the result (ISA 230). We show (1) how much each source
# contributes and (2) whether the risk level would change with a different weighting.
# This block was written with the help of Claude (see header).
st.subheader("Composition and robustness of the score", anchor=False)
c1, c2 = st.columns(2, gap="large")

# Left: stacked bar; each segment = weight x score of one source, the whole bar = overall score
with c1:
    st.caption("Contribution of each source to the overall score (weight × score).")
    fig = go.Figure()
    # brand colours, because the traffic-light colours are reserved for risk
    for row, colour in zip(assessment.score_breakdown(res), [shared.TEXT, shared.ACCENT, shared.LINE]):
        if row["weight"] == 0:
            continue
        fig.add_bar(y=["Score"], x=[row["contribution"] * 100], orientation="h",
                    name=row["label"], marker_color=colour,
                    hovertemplate=(f"{row['label']}: weight {row['weight']:.0%} × score "
                                   f"{row['score']:.0%} = {row['contribution']:.1%}<extra></extra>"))
    fig.update_layout(barmode="stack", height=200, margin=dict(t=10, b=0, l=0, r=10),
                      xaxis=dict(range=[0, 100], dtick=25, ticksuffix=" %"), yaxis=dict(visible=False),
                      legend=dict(orientation="h", y=-0.5))
    st.plotly_chart(fig, width="stretch")

# Right: score for every split between ratios and questionnaire, on top of the three risk zones
with c2:
    st.caption("Score for every split between ratios and questionnaire (ML share unchanged).")
    sens = assessment.weight_sensitivity(res)
    fig = go.Figure()
    for low, high, colour in [(0, 30, shared.GREEN_HEX), (30, 60, shared.AMBER_HEX), (60, 100, shared.RED_HEX)]:
        fig.add_hrect(y0=low, y1=high, fillcolor=colour, opacity=0.25, line_width=0)
    fig.add_scatter(x=[r["ratio_share"] * 100 for r in sens], y=[r["score"] * 100 for r in sens],
                    mode="lines+markers", line=dict(color=shared.TEXT), name="Score",
                    hovertemplate="Ratios %{x:.0f} %: score %{y:.0f} %<extra></extra>")
    fig.update_layout(height=200, margin=dict(t=10, b=0, l=0, r=10), showlegend=False,
                      xaxis=dict(title="Share of ratios (rest: questionnaire)", ticksuffix=" %"),
                      yaxis=dict(range=[0, 100], ticksuffix=" %"))
    st.plotly_chart(fig, width="stretch")

# robust = the same level for every weighting
levels = list(dict.fromkeys(r["level"] for r in sens))      # distinct levels, order kept
if res["knock_outs"]:
    st.info("The risk level does not depend on the weighting: a knock-out criterion sets it to High.")
elif len(levels) == 1:
    st.success(f"Robust result: the risk level is **{levels[0]}** for every weighting of ratios and questionnaire.")
else:
    st.warning("The risk level depends on the weighting (" + " / ".join(levels) + "). "
               "Document why the chosen weights are appropriate for this client.")

# --- Auditor's conclusion (ISA 570.17-23) ---
# Decision tree of ISA 570 with three questions. The app only derives the consequence for the
# auditor's report; the decision itself is the auditor's professional judgement.

st.subheader("Auditor's conclusion")
st.caption("The app proposes, the auditor decides. Record your conclusion; the app derives the "
           "implication for the auditor's documentation.")
prev = ss.conclusion                       # empty dict if nothing was recorded yet
c1, c2, c3 = st.columns(3)

# Defaults: the previous answer, otherwise the normal case ("Yes" / "No" / "Yes")
basis = c1.radio("Is the going concern basis of accounting appropriate?", ["Yes", "No"],
                 index=0 if prev.get("basis", True) else 1)

# irrelevant if the basis is not appropriate -> disabled
uncert = c2.radio("Does a material uncertainty exist?", ["Yes", "No"],
                  index=0 if prev.get("uncertainty") else 1, disabled=basis == "No")

# only relevant if a material uncertainty exists
discl = c3.radio("Is it adequately disclosed in the notes?", ["Yes", "No"],
                 index=0 if prev.get("disclosed", True) else 1,
                 disabled=basis == "No" or uncert == "No")
comment = st.text_area("Comment / rationale", prev.get("comment", ""))   # rationale for the professional judgement

opinion, reason = assessment.report_implication(basis == "Yes", uncert == "Yes", discl == "Yes")
st.info(f"**Implication for the auditor's report:** {opinion}  \n{reason}")

# The conclusion is used in the PDF and the database
if st.button("Record conclusion", type="primary"):
    ss.conclusion = {"basis": basis == "Yes", "uncertainty": uncert == "Yes",
                     "disclosed": discl == "Yes", "comment": comment,
                     "opinion": opinion, "reason": reason}
    st.rerun()                             # so the progress list in the sidebar updates
if ss.conclusion:
    st.success("Conclusion recorded.")

# --- PDF export and saving to the database ---
st.subheader("Documentation")

pkg = shared.model_package()               # None if the model is not trained
ml_info = None
if pkg:
    s, _ = shared.ml_score(ys[-1])
    ml_info = {"score": s, "n": pkg["metrics"]["n"], "auc": pkg["metrics"]["auc_logreg"]}

pdf = documentation.build_pdf(ss.engagement, ys, res, shared.legal_tests(ys[-1]), liq, ml_info, ss.conclusion,
                       ss.profile)

# e.g. "going_concern_Alpenwerk_Machines_AG.pdf"
client = (ss.engagement["client"] or "client").replace(" ", "_")
c1, c2 = st.columns(2)

c1.download_button("Download PDF working paper", pdf, file_name=f"going_concern_{client}.pdf",
                   mime="application/pdf", icon=":material/picture_as_pdf:", width="stretch")

# saved audit files can be loaded again on the page "Audit files"
if c2.button("Save to audit files", icon=":material/save:", width="stretch"):
    ss.result = {"level": res["level"], "score": res["score"]}   # shown in the list of audit files
    new_id = documentation.save_audit_file(ss)
    st.toast(f"Saved as audit file #{new_id}")
