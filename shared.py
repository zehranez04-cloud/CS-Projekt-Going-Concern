"""
SHARED - session state and small layout helpers used by all pages.

Shared app state (st.session_state) and Streamlit helper functions used by all pages.

Keys in st.session_state:
    engagement        dict: client, fiscal_year, auditor
    profile           dict: company profile (industry, legal form, size, group, ...)
    financials        DataFrame: rows = line items, columns = years
    ai_result         dict: answer of the AI import (mappings, notes, warnings)
    answers           dict: questionnaire answers {question id: True/False}
    liquidity_inputs  dict: opening_cash, credit_line, plan, measures
    weights           dict: weights of the score components
    conclusion        dict: auditor's conclusion
"""

# Link between the pages and the logic/ files: holds the session state, loads samples and
# saved engagements, and provides the cards and buttons that look the same on every page.
# Use of generative AI:
# - Code: parts of the code in this file were written with the help of Claude (Anthropic). We reviewed, tested and adjusted them.
# - Comments: Claude was used as support for writing the comments and making sure that the structure fits.

import streamlit as st

from logic import analysis, assessment, data_input, ml_model
from logic.data_input import table_to_years

# GoCon brand colours for the Plotly charts; must match assets/gocon.css and .streamlit/config.toml
BG, TEXT, TEXT_MUTED, LINE = "#FFFFFF", "#1A1C1B", "#4D585F", "#86959C"
SURFACE, ACCENT, ACCENT_LIGHT, WARM_SURFACE = "#E9ECEB", "#9E6129", "#CFA075", "#F5EBE0"

# Traffic light: the only colours outside the brand palette, reserved for the risk status
GREEN_HEX, AMBER_HEX, RED_HEX, GREY_HEX = "#3F7A5A", "#D1A23A", "#A9483B", "#86959C"
HEX = {"green": GREEN_HEX, "amber": AMBER_HEX, "red": RED_HEX, "grey": GREY_HEX}


def init():
    """Called once per run from app.py: creates default values."""
    ss = st.session_state
    ss.setdefault("engagement", {"client": "", "fiscal_year": "", "auditor": ""})
    ss.setdefault("profile", data_input.default_profile())
    ss.setdefault("profile_confirmed", False)
    ss.setdefault("financials", None)
    ss.setdefault("answers", {})
    ss.setdefault("liquidity_inputs", None)
    ss.setdefault("weights", dict(assessment.DEFAULT_WEIGHTS))
    ss.setdefault("conclusion", {})
    # part of the widget keys on pages 1, 2 and 5; raising it rebuilds those widgets with new data
    ss.setdefault("editor_version", 0)


def _reset_widgets():
    """Forget widget states of the previous engagement (questionnaire answers,
    table editors) so the newly loaded data is shown."""
    ss = st.session_state
    # prefixes: q_ = questionnaire (page 4), p_ = profile (page 1), measures_base = page 5
    for k in [k for k in ss.keys() if str(k).startswith(("q_", "p_", "measures_base"))]:
        del ss[k]
    ss.editor_version += 1


def load_sample(name):
    ss = st.session_state
    ss.financials = data_input.sample_table(name)
    ss.engagement = {"client": name.split(" (")[0], "fiscal_year": data_input.YEARS[-1],
                     "auditor": ss.engagement.get("auditor", "")}
    ss.answers = dict(data_input.SAMPLE_ANSWERS.get(name, {}))
    ss.profile = data_input.default_profile() | data_input.SAMPLE_PROFILES.get(name, {})
    ss.profile_confirmed = True
    ss.liquidity_inputs = None
    ss.conclusion = {}
    ss.pop("ai_result", None)
    _reset_widgets()


def load_engagement(data):
    ss = st.session_state
    for k, v in data.items():
        ss[k] = v
    ss.liquidity_inputs = data.get("liquidity_inputs")   # None if no plan was saved
    # merge with the defaults so audit files saved before a profile field existed still work
    ss.profile = data_input.default_profile() | (data.get("profile") or {})
    ss.profile_confirmed = bool(data.get("profile"))
    ss.pop("ai_result", None)
    _reset_widgets()


def years():
    """Financial years of the current engagement (oldest first) or []."""
    df = st.session_state.get("financials")
    industry = st.session_state.profile["industry"]   # -> industry-specific thresholds
    return table_to_years(df, industry) if df is not None else []


def require_financials():
    """Stops the page with a hint if no financial statements are loaded yet."""
    if not years():
        st.info("No financial statements loaded yet. Upload an annual report or load a "
                "sample company first.")
        st.page_link("pages/2_financial_statements.py", label="Go to step 2: Financial statements",
                     icon=":material/arrow_forward:")
        st.stop()
    return years()


def liquidity_result():
    li = st.session_state.get("liquidity_inputs")
    if not li:
        return None
    return analysis.evaluate_plan(li["opening_cash"], li["credit_line"], li["plan"], li["measures"])


# cached: the model file is loaded only once, not on every rerun of a page
@st.cache_resource
def model_package():
    return ml_model.load_model()


def ml_score(fy):
    pkg = model_package()
    if pkg is None:
        return None, None
    return ml_model.predict(pkg, fy)


def overall_assessment():
    """Combined result of all modules for the current engagement."""
    ys = years()
    score, _ = ml_score(ys[-1])
    return assessment.assess(ys, st.session_state.answers, liquidity_result(), score,
                          st.session_state.weights, st.session_state.profile)


def legal_tests(fy):
    return [analysis.capital_loss(fy), analysis.over_indebtedness(fy),
            analysis.impending_insolvency(liquidity_result())]


def traffic_light(status, title, value="", caption=""):
    """Card with a coloured dot, used on several pages."""
    # key "card-<title>" lets assets/gocon.css style each card individually
    key = "card-" + "".join(ch if ch.isalnum() else "-" for ch in title.lower())
    with st.container(border=True, key = key):
        # look defined in assets/gocon.css (.gc-dot, .gc-card-title)
        st.markdown(f"<div class='gc-card-title'><span class='gc-dot gc-dot-{status}'></span>"
                    f"{title}</div>", unsafe_allow_html=True)
        if value:
            st.markdown(f"### {value}")
        if caption:
            st.caption(caption)


def next_step(page, label):
    st.divider()
    st.page_link(page, label=label, icon=":material/arrow_forward:")
