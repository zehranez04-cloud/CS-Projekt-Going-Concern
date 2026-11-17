"""Step 6: machine learning - bankruptcy prediction model."""

# What this page does:
#   1. If no model exists yet: train it on the Polish dataset with one click.
#   2. Show the quality of the model (training data, ROC-AUC, benchmark).
#   3. Show the risk score of the client for every year (bar chart).
#   4. Explain the score of one year: which ratios increase or decrease the risk.
# The model itself (training, prediction) is in logic/ml_model.py.
# The score of the latest year flows into the overall assessment on page 7 (weight "ML model").
# Use of generative AI: the comments in this file were written with the help of Claude (Anthropic) and checked by us.

import plotly.graph_objects as go             # interactive charts
import streamlit as st

import shared                                 # helper functions used by all pages
from logic import ml_model                    # our own file: training and prediction

st.title("6 · Bankruptcy model")
ys = shared.require_financials()              # financial years of the client; stops the page if none are loaded
st.caption("Logistic regression trained by us on the Polish Companies Bankruptcy dataset "
           "(UCI). It uses only ratios that can be computed exactly from the standardised "
           "financial statements.")

# ---------------------------------------------------------------------------
# Load or train the model
# ---------------------------------------------------------------------------
pkg = shared.model_package()                  # trained model (None if not trained yet)
if pkg is None:
    # No model yet: train it directly in the app (data must be in the data folder)
    if not ml_model.training_data_available():
        st.warning("No trained model found. Copy the Polish dataset (1year.arff … 5year.arff) "
                   "into the data folder, then come back to this page.")
        st.stop()
    st.info("The Polish dataset was found, but the model has not been trained yet.")
    if st.button("Train model now", type="primary", icon=":material/model_training:"):
        with st.spinner("Training the model on the Polish dataset … (about 10–60 seconds)"):
            ml_model.train()               # trains and saves the model as data/bankruptcy_model.joblib
        shared.model_package.clear()   # reload the newly saved model
        st.rerun()
    st.stop()

# Quality of the model, measured on the test data (see train() in logic/ml_model.py)
m = pkg["metrics"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Training data", f"{m['n']:,} companies")
c2.metric("Bankrupt share", f"{m['bankrupt_share']:.1%}")
c3.metric("ROC-AUC (test)", f"{m['auc_logreg']:.2f}", help="1.0 = perfect, 0.5 = random")
c4.metric("Benchmark random forest", f"{m['auc_rf']:.2f}")

# ---------------------------------------------------------------------------
# Score per year (user can select the year)
# ---------------------------------------------------------------------------
st.subheader("Risk score of the client")
scores = [ml_model.predict(pkg, fy)[0] for fy in ys]   # one score per year ([0] = only the score, not the explanation)
# Bar colour: red from 70 %, amber from 40 %, otherwise green
fig = go.Figure(go.Bar(x=[fy.year for fy in ys], y=scores, text=[f"{s:.0%}" for s in scores],
                       marker_color=[shared.RED_HEX if s >= 0.7 else shared.AMBER_HEX if s >= 0.4 else shared.GREEN_HEX
                                     for s in scores]))
fig.update_layout(height=320, template="simple_white", yaxis_tickformat=".0%",
                  yaxis_range=[0, 1], margin=dict(t=20, b=20))
st.plotly_chart(fig, width="stretch")
st.caption("Trained with balanced class weights: the score ranks risk, it is not the exact "
           "probability of bankruptcy for this client. Green < 40 %, amber 40–70 %, red ≥ 70 %.")

# ---------------------------------------------------------------------------
# Explanation of the score: contribution of every ratio (user selects the year)
# ---------------------------------------------------------------------------
year = st.select_slider("Explain the score for year", [fy.year for fy in ys], value=ys[-1].year)
fy = next(f for f in ys if f.year == year)    # financial year that was selected
score, contrib = ml_model.predict(pkg, fy)    # contrib = table with the contribution of every ratio
# Horizontal bars: red = ratio increases the risk, green = ratio decreases it
fig = go.Figure(go.Bar(x=contrib["Contribution"], y=contrib["Description"], orientation="h",
                       marker_color=[shared.RED_HEX if c > 0 else shared.GREEN_HEX for c in contrib["Contribution"]]))
fig.update_layout(height=460, template="simple_white", yaxis_autorange="reversed",
                  margin=dict(t=20, b=20), xaxis_title="Contribution (red = increases risk)")
st.plotly_chart(fig, width="stretch")

# Details for the documentation: pipeline, confusion matrix, all values, limitation
with st.expander("Model details"):
    st.markdown("**Pipeline:** missing values → median · outliers capped at 1st/99th percentile · "
                "standardisation · logistic regression (class_weight='balanced').")
    cm = m["confusion_matrix"]
    st.markdown(f"**Confusion matrix on test data** (threshold 50 %): "
                f"true negatives {cm[0][0]:,}, false positives {cm[0][1]:,}, "
                f"false negatives {cm[1][0]:,}, true positives {cm[1][1]:,} "
                f"→ recall (bankrupt detected) {m['recall_logreg']:.0%}")
    st.dataframe(contrib.rename(columns={"Feature": "Polish attribute"}), hide_index=True,
                 width="stretch")
    st.caption("Limitation: Polish companies 2000–2013. Transferability to Swiss companies "
               "should be discussed critically.")

shared.next_step("pages/7_assessment_report.py", "Continue with step 7: Assessment & report")
