"""Step 7: combined assessment, auditor's conclusion, PDF export and saving."""

import plotly.graph_objects as go
import streamlit as st

import shared
from logic import assessment, documentation

st.title("7 · Assessment & report")
ys = shared.require_financials()
ss = st.session_state

# ---------------------------------------------------------------------------
# Weights of the components (user interaction)
# ---------------------------------------------------------------------------
st.subheader("Weighting of the components", anchor=False)
st.caption("How strongly should each source count? The weights are normalised to 100 %.")
with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    w = ss.weights
    w["quantitative"] = c1.slider("Ratios", 0.0, 1.0, w["quantitative"], 0.05)
    w["qualitative"] = c2.slider("ISA 570 questionnaire", 0.0, 1.0, w["qualitative"], 0.05)
    w["ml"] = c3.slider("ML model", 0.0, 1.0, w["ml"], 0.05)

res = shared.overall_assessment()
liq = shared.liquidity_result()

# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
c1, c2 = st.columns([1, 2], gap="large")
with c1:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=res["score"] * 100, number={"suffix": " %"},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#1E2B33"},
               "steps": [{"range": [0, 30], "color": shared.GREEN_HEX},
                         {"range": [30, 60], "color": shared.AMBER_HEX},
                         {"range": [60, 100], "color": shared.RED_HEX}]}))
    fig.update_layout(height=260, margin=dict(t=30, b=0, l=40, r=40))
    st.plotly_chart(fig, width="stretch")
with c2:
    shared.traffic_light(res["colour"], "Going concern risk", res["level"], res["text"])
    if res["knock_outs"]:
        st.error("**Knock-out criteria triggered** – risk set to High:\n\n" +
                 "\n".join(f"- {k}" for k in res["knock_outs"]))
    if liq is None:
        st.info("The liquidity plan (CO Art. 725) has not been prepared yet.")

p, wn = res["parts"], res["weights"]
tot = sum(wn.values()) or 1
cols = st.columns(3)
for col, (key, label) in zip(cols, [("quantitative", "Ratios"), ("qualitative", "Questionnaire"),
                                    ("ml", "ML model")]):
    col.metric(f"{label} · weight {wn[key] / tot:.0%}", f"{p[key]:.0%}" if wn[key] else "not used")

with st.expander(f"All warning signals ({len(res['signals'])})", expanded=True):
    for source, text in res["signals"] or [("–", "No warning signals")]:
        st.markdown(f"- **{source}:** {text}")

# ---------------------------------------------------------------------------
# Auditor's conclusion (ISA 570.17-23) - professional judgement
# ---------------------------------------------------------------------------
st.subheader("Auditor's conclusion")
st.caption("The app proposes, the auditor decides. Record your conclusion; the app derives the "
           "implication for the auditor's documentation.")
prev = ss.conclusion
c1, c2, c3 = st.columns(3)
basis = c1.radio("Is the going concern basis of accounting appropriate?", ["Yes", "No"],
                 index=0 if prev.get("basis", True) else 1)
uncert = c2.radio("Does a material uncertainty exist?", ["Yes", "No"],
                  index=0 if prev.get("uncertainty") else 1, disabled=basis == "No")
discl = c3.radio("Is it adequately disclosed in the notes?", ["Yes", "No"],
                 index=0 if prev.get("disclosed", True) else 1,
                 disabled=basis == "No" or uncert == "No")
comment = st.text_area("Comment / rationale", prev.get("comment", ""))
opinion, reason = assessment.report_implication(basis == "Yes", uncert == "Yes", discl == "Yes")
st.info(f"**Implication for the auditor's report:** {opinion}  \n{reason}")
if st.button("Record conclusion", type="primary"):
    ss.conclusion = {"basis": basis == "Yes", "uncertainty": uncert == "Yes",
                     "disclosed": discl == "Yes", "comment": comment,
                     "opinion": opinion, "reason": reason}
    st.rerun()
if ss.conclusion:
    st.success("Conclusion recorded.")

# ---------------------------------------------------------------------------
# PDF export and saving to the database
# ---------------------------------------------------------------------------
st.subheader("Documentation")
pkg = shared.model_package()
ml_info = None
if pkg:
    s, _ = shared.ml_score(ys[-1])
    ml_info = {"score": s, "n": pkg["metrics"]["n"], "auc": pkg["metrics"]["auc_logreg"]}
pdf = documentation.build_pdf(ss.engagement, ys, res, shared.legal_tests(ys[-1]), liq, ml_info, ss.conclusion,
                       ss.profile)
client = (ss.engagement["client"] or "client").replace(" ", "_")
c1, c2 = st.columns(2)
c1.download_button("Download PDF working paper", pdf, file_name=f"going_concern_{client}.pdf",
                   mime="application/pdf", icon=":material/picture_as_pdf:", width="stretch")
if c2.button("Save to audit files", icon=":material/save:", width="stretch"):
    ss.result = {"level": res["level"], "score": res["score"]}
    new_id = documentation.save_audit_file(ss)
    st.toast(f"Saved as audit file #{new_id}")
