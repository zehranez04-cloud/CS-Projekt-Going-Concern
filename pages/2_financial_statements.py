"""Step 2: upload the annual report, standardise it with AI and review it."""

# Loads the financial statements in one of three ways (AI upload, sample company, manual entry),
# shows how the AI mapped the line items and lets the auditor correct every figure.
# Every later step (ratios, ML model, assessment) uses these figures; the logic is in logic/data_input.py.
# Use of generative AI:
# - Code: parts of the code in this file were written with the help of Claude (Anthropic). We reviewed, tested and adjusted them.
# - Comments: Claude was used as support for writing the comments and making sure that the structure fits. We checked and partly adjusted them.

import pandas as pd
import streamlit as st

import shared
from logic import data_input
from logic.data_input import KEYS, LABELS, LINE_ITEMS, MAX_YEARS, empty_table

st.title("2 · Financial statements")
st.caption("Upload the balance sheet, income statement and cash flow statement of the last "
           f"3–{MAX_YEARS} years. The AI converts them into a standardised format.")


# --- API key and model ---
# The key is never in the code: it comes from .streamlit/secrets.toml (local, not on GitHub)
# or from the Streamlit Cloud secrets.
def api_settings():
    """API key from .streamlit/secrets.toml (locally) or the Streamlit Cloud secrets."""
    try:
        # AI_MODEL is optional; otherwise the default model is used
        return st.secrets.get("ANTHROPIC_API_KEY"), st.secrets.get("AI_MODEL", data_input.DEFAULT_MODEL)
    except Exception:          # no secrets file at all
        return None, data_input.DEFAULT_MODEL   # no key -> the AI tab is disabled, the rest of the app still works


tab_ai, tab_sample, tab_manual = st.tabs([":material/auto_awesome: Upload with AI",
                                          ":material/science: Sample company",
                                          ":material/edit: Manual entry"])

# --- Option A: AI import (Claude API) ---
with tab_ai:
    api_key, model = api_settings()
    files = st.file_uploader("Annual reports (PDF, Excel or CSV) – several files allowed, "
                             "e.g. one per year", type=["pdf", "xlsx", "xls", "csv"],
                             accept_multiple_files=True)
    if not api_key:
        st.info("No API key found. Add ANTHROPIC_API_KEY to .streamlit/secrets.toml "
                "(see secrets.toml.example) to use the AI import.")
    if st.button("Standardise with AI", type="primary", disabled=not files or not api_key):
        with st.spinner("The AI is reading the annual report … this takes about 20–90 seconds"):
            try:
                # table = standardised figures, answer = full AI answer, warnings = failed balance checks
                table, answer, warnings = data_input.standardise(
                    [(f.name, f.getvalue()) for f in files], api_key, model)
                st.session_state.financials = table
                # kept so the auditor can see how the AI worked (shown further below)
                st.session_state.ai_result = {"answer": answer, "warnings": warnings,
                                              "files": [f.name for f in files]}
                eng = st.session_state.engagement
                # only fill client and year from the report if page 1 left them empty
                eng["client"] = eng["client"] or answer["company"]
                eng["fiscal_year"] = eng["fiscal_year"] or table.columns[-1]
                st.session_state.editor_version += 1              # new editor key -> the table below shows the new data
                st.rerun()
            except Exception as err:                              # e.g. wrong key, no internet, unreadable file
                st.error(f"AI import failed: {err}")              # show the error instead of crashing the app

# --- Option B: sample companies (testing and demo, no API key needed) ---
with tab_sample:
    name = st.selectbox("Sample company", list(data_input.SAMPLES))
    if st.button("Load sample"):
        shared.load_sample(name)                  # also loads questionnaire answers and profile
        st.rerun()

# --- Option C: empty table for manual entry ---
with tab_manual:
    first = st.number_input("First year", 2000, 2100, 2021)
    n = st.slider("Number of years", 1, MAX_YEARS, 3)
    if st.button("Create empty table"):
        st.session_state.financials = empty_table(range(first, first + n))
        st.session_state.pop("ai_result", None)   # forget an earlier AI import
        st.session_state.editor_version += 1
        st.rerun()

# --- Result of the AI import: transparency for the auditor ---
# Only shown after an AI import, so the auditor can understand what the AI did.
ai = st.session_state.get("ai_result")
if ai:
    a = ai["answer"]
    st.success(f"**{a['company']}** imported from {', '.join(ai['files'])} · "
               f"Standard: {a['standard']} · Currency: {a['currency']}")
    for w in ai["warnings"]:                    # one warning per year whose balance sheet does not balance
        st.warning("Balance check: " + w)
    st.warning("AI can make mistakes. Compare every figure with the original report before "
               "continuing – the auditor remains responsible for the data.")
    with st.expander("How did the AI map the line items?"):
        st.dataframe(pd.DataFrame([{"Standard item": LABELS[m["standard_item"]],
                                    "Original line items": m["original_items"]}
                                   for m in a["mappings"]]), hide_index=True, width="stretch")
        for note in a["notes"]:                 # e.g. assumptions the AI made
            st.markdown(f"- {note}")

# --- Review table (editable) ---
df = st.session_state.financials                # rows = line items, columns = years
if df is None:
    st.stop()

st.subheader("Standardised financial statements")
st.caption("Review and correct the figures. Leave operating cash flow empty if there is no "
           "cash flow statement – it is then approximated as net income + depreciation.")
# display copy with readable labels; converted back to internal keys below
view = df.copy()
view.insert(0, "Statement", [LINE_ITEMS[k][1] for k in KEYS])
view.index = [LABELS[k] for k in KEYS]
# The key changes with editor_version, so the editor is rebuilt when new data is loaded.
edited = st.data_editor(
    view, height=740, width="stretch", disabled=["Statement"],
    key=f"fin_editor_{st.session_state.editor_version}",
    column_config={c: st.column_config.NumberColumn(c, format="localized", step=1000.0)
                   for c in df.columns})
new = edited.drop(columns="Statement")
new.index = KEYS
new.index.name = "item"
st.session_state.financials = new               # the auditor's corrections are used on all pages

# --- Plausibility check: does the balance sheet balance? ---
ys = shared.years()
for fy in ys:
    # tolerance: 0.5 % of total assets (at least 1) for rounding differences in the report
    if abs(fy.balance_difference) > max(1.0, 0.005 * abs(fy.total_assets)):
        st.error(f"{fy.year}: balance sheet does not balance – difference {fy.balance_difference:,.0f}")
if len(ys) < 3:                                 # trends need at least 3 years
    st.info("Tip: upload at least 3 years so the app can analyse trends.")

shared.next_step("pages/3_ratio_analysis.py", "Continue with step 3: Ratio analysis")
