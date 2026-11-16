# Audit files: saved engagements in the SQLite database.

# In this page we:
#  - show all assessments that were saved on page 7 (via the button "save to audit files")
#  - the user can load a saved file (e.g. to continue working on it or compare it with the current year) or delete it

# This tool is important, as it is a crucial part of the auditing process to keep everything documented 
# -> in the database everything concluded from the audits is saved: figures, profile, questionnaire, liquidity plan and auditor's conclusion

#lkjkj 
import streamlit as st

import shared                         # helper functions used by all pages
from logic import documentation       # database functions (list, load, delete audit files)

st.title("Audit files")
st.caption("Saved going concern assessments. Load one to continue working on it or to "
           "compare it with the current year.")

# First we need to read all saved audit files from the database as a table
# (columns: id, client, industry, fiscal year, auditor, saved at, risk level, risk score)
files = documentation.list_audit_files()

# if nothing is saved yet we provide a hint and stop here (the rest of the page is not shown)
if files.empty:
    st.info("No audit files saved yet. Save one on the page 'Assessment & report'.")
    st.stop()

# Otherwise we continue and show the table of all audit files. 
# The column "risk_score" (0-1) is shown as a progress bar with a percentage, therefore high risks are directly visible for the auditor
st.dataframe(files, hide_index=True, width="stretch",
             column_config={"risk_score": st.column_config.ProgressColumn(
                 "Risk score", min_value=0.0, max_value=1.0, format="percent")})

# Row with dropdown (2/3 of the width) and two buttons (1/6 each), aligned at the bottom
c1, c2, c3 = st.columns([2, 1, 1], vertical_alignment="bottom")

# We provide a dropdown to choose one audit file. The options are the ids (numbers);
# format_func defines how each option is displayed, e.g. "#3 · Alpenwerk Machines AG (2026-11-15T21:40:02)".
# lambda i: ...  is a small function in one line that turns the id i into this text: files.set_index('id').at[i, 'client'] looks up the client name of the row with id i.
choice = c1.selectbox("Audit file", files["id"],
                      format_func=lambda i: f"#{i} · {files.set_index('id').at[i, 'client']} "
                                            f"({files.set_index('id').at[i, 'saved_at']})")

# The user can either load an audit file (which leads to page 7) or delete it, which is done in the following two code blocks:

# I) Load: read the chosen audit file from the database, put all its data into the session state (figures, profile, answers, liquidity plan, conclusion)
# then we jump directly to page 7 to see the result -> int(...) converts the id from the table (a numpy number) into a normal Python integer, which the database can work with
if c2.button("Load", type="primary", width="stretch"):
    shared.load_engagement(documentation.load_audit_file(int(choice)))
    st.switch_page("pages/7_assessment_report.py")

# II) Delete: remove the chosen audit file from the database and reload the page -> table is then shown without it
if c3.button("Delete", width="stretch"):
    documentation.delete_audit_file(int(choice))
    st.rerun()