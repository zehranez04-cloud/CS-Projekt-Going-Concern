"""Step 1: engagement data and company profile (user data input).

The inputs on this page change the analysis on the following pages:
industry -> traffic-light thresholds, size -> audit type / framework,
founding year and group structure -> additional warning signals.
"""

from datetime import date

import pandas as pd
import streamlit as st

import shared
from logic import analysis, data_input

st.title("1 · Company profile")
st.caption("Enter the master data of the audit client. The industry, size and group structure "
           "are used in the analysis – e.g. a retailer is assessed with different liquidity "
           "thresholds than an IT company.")

ss = st.session_state
p, eng, v = ss.profile, ss.engagement, ss.editor_version

# ---------------------------------------------------------------------------
# Engagement
# ---------------------------------------------------------------------------
st.subheader("Engagement")
c1, c2, c3 = st.columns(3)
eng["client"] = c1.text_input("Client name", eng["client"], key=f"p_client_{v}")
eng["fiscal_year"] = c2.text_input("Financial year audited", eng["fiscal_year"],
                                   placeholder="e.g. 2025", key=f"p_fy_{v}")
eng["auditor"] = c3.text_input("Auditor", eng["auditor"], key=f"p_auditor_{v}")

# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------
st.subheader("Company")
c1, c2, c3 = st.columns(3)
p["industry"] = c1.selectbox("Industry", data_input.INDUSTRIES, index=data_input.INDUSTRIES.index(p["industry"]),
                             key=f"p_industry_{v}",
                             help="Selects industry-specific thresholds for the analysis.")
p["legal_form"] = c2.selectbox("Legal form", data_input.LEGAL_FORMS,
                               index=data_input.LEGAL_FORMS.index(p["legal_form"]), key=f"p_legal_{v}")
p["canton"] = c3.selectbox("Canton of domicile", data_input.CANTONS, index=data_input.CANTONS.index(p["canton"]),
                           key=f"p_canton_{v}")
c1, c2, c3, c4 = st.columns(4)
p["founded"] = c1.number_input("Year founded", 1800, date.today().year, int(p["founded"]),
                               key=f"p_founded_{v}")
p["employees"] = c2.number_input("Employees (FTE, annual average)", 0, 1_000_000,
                                 int(p["employees"]), step=5, key=f"p_emp_{v}")
p["currency"] = c3.selectbox("Reporting currency", data_input.CURRENCIES,
                             index=data_input.CURRENCIES.index(p["currency"]), key=f"p_cur_{v}")
p["listed"] = c4.toggle("Listed on a stock exchange", p["listed"], key=f"p_listed_{v}")

if p["legal_form"] == "Other":
    st.caption(":material/info: CO Art. 725–725b apply to companies limited by shares; the "
               "GmbH (Art. 820) and the cooperative (Art. 903) refer to them.")

# ---------------------------------------------------------------------------
# Group structure
# ---------------------------------------------------------------------------
st.subheader("Group structure")
c1, c2 = st.columns(2)
p["group"] = c1.toggle("Part of a group (subsidiary)", p["group"], key=f"p_group_{v}")
p["support_letter"] = c2.toggle("Written support letter from the parent available",
                                p["support_letter"], key=f"p_support_{v}",
                                disabled=not p["group"],
                                help="A binding letter of support can mitigate going concern "
                                     "doubts of a subsidiary (evaluate it like management's plans, ISA 570.16).")

# ---------------------------------------------------------------------------
# Audit type (CO Art. 727) - with automatic check if financials are loaded
# ---------------------------------------------------------------------------
st.subheader("Audit")
p["audit_type"] = st.radio("Type of audit", data_input.AUDIT_TYPES, index=data_input.AUDIT_TYPES.index(p["audit_type"]),
                           horizontal=True, key=f"p_audit_{v}")
ys = shared.years()
if ys:
    ordinary, reason = data_input.audit_type_check(p, ys)
    if ordinary and p["audit_type"] != data_input.AUDIT_TYPES[0]:
        st.warning(f"Check the audit type: {reason}")
    else:
        st.caption(f":material/fact_check: Size check: {reason}")
else:
    st.caption("The size check (CO Art. 727) runs as soon as financial statements are loaded.")

# ---------------------------------------------------------------------------
# Business understanding (ISA 315) - free text, included in the PDF
# ---------------------------------------------------------------------------
st.subheader("Business understanding")
p["description"] = st.text_area("Business model and main products", p["description"],
                                key=f"p_desc_{v}", height=80)
c1, c2 = st.columns(2)
p["key_risks"] = c1.text_area("Key risks known from planning (e.g. customer dependence)",
                              p["key_risks"], key=f"p_risks_{v}", height=100)
p["notes"] = c2.text_area("Auditor's notes", p["notes"], key=f"p_notes_{v}", height=100)

# ---------------------------------------------------------------------------
# Feedback: what the inputs change
# ---------------------------------------------------------------------------
st.subheader("Effect on the analysis")
c1, c2 = st.columns([3, 2], gap="large")
with c1:
    st.markdown(f"**Traffic-light thresholds for: {p['industry']}**")
    rows = []
    for r in analysis.RATIOS:
        if r.key in analysis.INDUSTRY_KEYS:
            rows.append({"Ratio": r.name,
                         "This industry": analysis.threshold_text(r, p["industry"]).split(" (")[0],
                         "General": analysis.threshold_text(r, "General").split(" (")[0]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
with c2:
    st.markdown("**Framework**")
    st.write("ISA 570 (Revised) / PS-CH 570" if p["audit_type"] == data_input.AUDIT_TYPES[0]
             else "Swiss standard on limited audits (SER) – going concern is assessed with "
                  "inquiries and analytical procedures.")
    st.markdown("**Signals from the profile**")
    sig = data_input.profile_signals(p)
    for _, text in sig or [("", "None")]:
        st.write(("⚠️ " if sig else "") + text)

if st.button("Confirm profile", type="primary", icon=":material/check:"):
    ss.profile_confirmed = True
    st.toast("Company profile saved")

shared.next_step("pages/2_financial_statements.py", "Continue with step 2: Financial statements")
