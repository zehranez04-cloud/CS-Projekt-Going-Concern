"""Step 2: upload the annual report, standardise it with AI and review it."""

# What this page does:
#   1. The auditor loads the financial statements in one of three ways (tabs):
#      A) upload an annual report -> the Claude API converts it into our standard format
#      B) load a sample company (for testing and the demo, no API key needed)
#      C) enter the figures manually in an empty table
#   2. The result of the AI import is shown transparently (standard, currency, mapping).
#   3. The auditor reviews and corrects every figure in an editable table.
#   4. A plausibility check tests whether the balance sheet balances.
# Why it matters: every later step (ratios, ML model, assessment) uses these figures.
# The calculations live in logic/data_input.py; this file only builds the page.
# Use of generative AI: the comments in this file were written with the help of Claude (Anthropic) and checked by us.

import pandas as pd                           # tables (DataFrames)
import streamlit as st                        # web app framework

import shared                                 # helper functions used by all pages
from logic import data_input                  # our own file: standard format and AI import
# KEYS = internal names of the line items, LABELS = names shown to the user,
# LINE_ITEMS = item -> (label, statement), MAX_YEARS = max. number of years, empty_table = empty input table
from logic.data_input import KEYS, LABELS, LINE_ITEMS, MAX_YEARS, empty_table

st.title("2 · Financial statements")          # title of the page
st.caption("Upload the balance sheet, income statement and cash flow statement of the last "
           f"3–{MAX_YEARS} years. The AI converts them into a standardised format.")


# ---------------------------------------------------------------------------
# API key and model for the AI import
# The key is never written into the code: it is read from .streamlit/secrets.toml
# (locally, excluded from GitHub) or from the secrets of the Streamlit Cloud.
# ---------------------------------------------------------------------------
def api_settings():
    """API key from .streamlit/secrets.toml (locally) or the Streamlit Cloud secrets."""
    try:
        # .get(...) returns None if the key is missing; AI_MODEL is optional (default model otherwise)
        return st.secrets.get("ANTHROPIC_API_KEY"), st.secrets.get("AI_MODEL", data_input.DEFAULT_MODEL)
    except Exception:          # no secrets file at all
        return None, data_input.DEFAULT_MODEL   # no key -> the AI tab is disabled, the rest of the app still works


# Three tabs = three ways to load the financial statements (the text in front is an icon)
tab_ai, tab_sample, tab_manual = st.tabs([":material/auto_awesome: Upload with AI",
                                          ":material/science: Sample company",
                                          ":material/edit: Manual entry"])

# ---------------------------------------------------------------------------
# Option A: AI import (Claude API)
# ---------------------------------------------------------------------------
with tab_ai:
    api_key, model = api_settings()           # key and model from the secrets (see above)
    # Upload field; accept_multiple_files=True -> e.g. one file per year
    files = st.file_uploader("Annual reports (PDF, Excel or CSV) – several files allowed, "
                             "e.g. one per year", type=["pdf", "xlsx", "xls", "csv"],
                             accept_multiple_files=True)
    if not api_key:                           # without key: hint how to add one
        st.info("No API key found. Add ANTHROPIC_API_KEY to .streamlit/secrets.toml "
                "(see secrets.toml.example) to use the AI import.")
    # The button only works if files were uploaded AND a key exists
    if st.button("Standardise with AI", type="primary", disabled=not files or not api_key):
        with st.spinner("The AI is reading the annual report … this takes about 20–90 seconds"):
            try:
                # Send the files (name, content as bytes) to the Claude API (see logic/data_input.py):
                # table = standardised figures, answer = full AI answer, warnings = failed balance checks
                table, answer, warnings = data_input.standardise(
                    [(f.name, f.getvalue()) for f in files], api_key, model)
                st.session_state.financials = table               # store the figures for all other pages
                # store the AI answer so the auditor can see how the AI worked (shown further below)
                st.session_state.ai_result = {"answer": answer, "warnings": warnings,
                                              "files": [f.name for f in files]}
                eng = st.session_state.engagement                 # engagement data from page 1
                # fill in client name and fiscal year from the report, but only if they are still empty
                eng["client"] = eng["client"] or answer["company"]
                eng["fiscal_year"] = eng["fiscal_year"] or table.columns[-1]
                st.session_state.editor_version += 1              # new version -> the table below shows the new data
                st.rerun()                                        # reload the page with the imported figures
            except Exception as err:                              # e.g. wrong key, no internet, unreadable file
                st.error(f"AI import failed: {err}")              # show the error instead of crashing the app

# ---------------------------------------------------------------------------
# Option B: sample companies (for testing and the demo)
# ---------------------------------------------------------------------------
with tab_sample:
    name = st.selectbox("Sample company", list(data_input.SAMPLES))   # drop-down with the sample companies
    if st.button("Load sample"):
        shared.load_sample(name)                  # loads figures, questionnaire answers and profile (shared.py)
        st.rerun()

# ---------------------------------------------------------------------------
# Option C: empty table for manual entry
# ---------------------------------------------------------------------------
with tab_manual:
    first = st.number_input("First year", 2000, 2100, 2021)      # (label, minimum, maximum, default)
    n = st.slider("Number of years", 1, MAX_YEARS, 3)            # how many years (columns)
    if st.button("Create empty table"):
        st.session_state.financials = empty_table(range(first, first + n))   # e.g. 2021, 2022, 2023
        st.session_state.pop("ai_result", None)   # forget an earlier AI import (None = no error if missing)
        st.session_state.editor_version += 1
        st.rerun()

# ---------------------------------------------------------------------------
# Result of the AI import: transparency for the auditor
# ---------------------------------------------------------------------------
# Only shown after an AI import. The auditor must be able to understand what the AI did.
ai = st.session_state.get("ai_result")          # None if no AI import was made
if ai:
    a = ai["answer"]                            # answer of the AI (company, standard, currency, mapping, notes)
    st.success(f"**{a['company']}** imported from {', '.join(ai['files'])} · "
               f"Standard: {a['standard']} · Currency: {a['currency']}")
    for w in ai["warnings"]:                    # one warning per year whose balance sheet does not balance
        st.warning("Balance check: " + w)
    st.warning("AI can make mistakes. Compare every figure with the original report before "
               "continuing – the auditor remains responsible for the data.")
    # Mapping table: which original line items the AI put into which standard item
    with st.expander("How did the AI map the line items?"):
        st.dataframe(pd.DataFrame([{"Standard item": LABELS[m["standard_item"]],
                                    "Original line items": m["original_items"]}
                                   for m in a["mappings"]]), hide_index=True, width="stretch")
        for note in a["notes"]:                 # remarks of the AI, e.g. assumptions it made
            st.markdown(f"- {note}")

# ---------------------------------------------------------------------------
# Review table (editable)
# ---------------------------------------------------------------------------
df = st.session_state.financials                # rows = line items, columns = years
if df is None:                                  # nothing loaded yet -> stop here
    st.stop()

st.subheader("Standardised financial statements")
st.caption("Review and correct the figures. Leave operating cash flow empty if there is no "
           "cash flow statement – it is then approximated as net income + depreciation.")
view = df.copy()                                # copy for display, the original stays unchanged
view.insert(0, "Statement", [LINE_ITEMS[k][1] for k in KEYS])   # first column: balance sheet, income statement, ...
view.index = [LABELS[k] for k in KEYS]          # readable names instead of internal keys
# Editable table; the column "Statement" is locked. The key changes with editor_version,
# so the table is rebuilt when new data is loaded.
edited = st.data_editor(
    view, height=740, width="stretch", disabled=["Statement"],
    key=f"fin_editor_{st.session_state.editor_version}",
    column_config={c: st.column_config.NumberColumn(c, format="localized", step=1000.0)
                   for c in df.columns})
# Turn the edited table back into the internal format and save it
new = edited.drop(columns="Statement")          # remove the display column
new.index = KEYS                                # internal keys again
new.index.name = "item"
st.session_state.financials = new               # corrections of the auditor are used on all pages

# Plausibility check: does the balance sheet balance?
ys = shared.years()                             # one object per financial year
for fy in ys:
    # tolerance: 0.5 % of total assets (at least 1) for rounding differences in the report
    if abs(fy.balance_difference) > max(1.0, 0.005 * abs(fy.total_assets)):
        st.error(f"{fy.year}: balance sheet does not balance – difference {fy.balance_difference:,.0f}")
if len(ys) < 3:                                 # trends need at least 3 years
    st.info("Tip: upload at least 3 years so the app can analyse trends.")

shared.next_step("pages/3_ratio_analysis.py", "Continue with step 3: Ratio analysis")
