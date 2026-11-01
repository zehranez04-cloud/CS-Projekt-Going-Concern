"""Audit files: saved engagements in the SQLite database."""

import streamlit as st

import shared
from logic import documentation

st.title("Audit files")
st.caption("Saved going concern assessments. Load one to continue working on it or to "
           "compare it with the current year.")

files = documentation.list_audit_files()
if files.empty:
    st.info("No audit files saved yet. Save one on the page 'Assessment & report'.")
    st.stop()

st.dataframe(files, hide_index=True, width="stretch",
             column_config={"risk_score": st.column_config.ProgressColumn(
                 "Risk score", min_value=0.0, max_value=1.0, format="percent")})

c1, c2, c3 = st.columns([2, 1, 1], vertical_alignment="bottom")
choice = c1.selectbox("Audit file", files["id"],
                      format_func=lambda i: f"#{i} · {files.set_index('id').at[i, 'client']} "
                                            f"({files.set_index('id').at[i, 'saved_at']})")
if c2.button("Load", type="primary", width="stretch"):
    shared.load_engagement(documentation.load_audit_file(int(choice)))
    st.switch_page("pages/7_assessment_report.py")
if c3.button("Delete", width="stretch"):
    documentation.delete_audit_file(int(choice))
    st.rerun()
