"""
ANALYSIS - quantitative going concern tests.

Sections:
    1. Legal thresholds (Swiss CO Art. 725, 725a, 725b)
    2. Financial ratios with traffic lights and trend analysis
    3. 12-month liquidity planner (CO Art. 725)
"""

# Calculations behind pages 3 and 5; the results are also used in logic/assessment.py and the PDF.
# Status values used throughout the app: "green" = no indication, "amber" = watch,
# "red" = critical, "grey" = cannot be assessed (missing data).
# Use of generative AI:
# - Code: parts of the code in this file were written with the help of Claude (Anthropic). We reviewed, tested and adjusted them.
# - Comments: Claude was used as support for writing the comments and making sure that the structure fits. We checked and partly adjusted them.

import math
from dataclasses import dataclass

import pandas as pd

# thresholds(industry, key) returns the (green, red) limits of a ratio for the selected industry
from logic.data_input import thresholds


# Constants, so a typo ("gren") causes an error instead of a silent bug
GREEN, AMBER, RED, GREY = "green", "amber", "red", "grey"
# Points per colour for quantitative_score; grey gets no points
STATUS_POINTS = {GREEN: 0.0, AMBER: 0.5, RED: 1.0}


# --- I) Legal thresholds (Swiss CO) ---
# Every test returns a dict with the same keys, so page 3 and the PDF can show all tests the same way:
#   test, status, result, detail (figures behind the result), consequence (empty if no problem)
def capital_loss(fy):
    """CO Art. 725a: half of share capital + legal capital reserves + legal
    retained earnings is no longer covered by net assets (= equity)."""
    base = fy.share_capital + fy.legal_capital_reserves + fy.legal_retained_earnings
    limit = base / 2
    loss = fy.equity < limit
    return {
        "test": "Capital loss (CO Art. 725a)",
        # amber = capital loss but equity still positive; red = equity negative
        "status": AMBER if loss and fy.equity >= 0 else (RED if loss else GREEN),
        "result": "Capital loss" if loss else "No capital loss",
        "detail": f"Net assets {fy.equity:,.0f} vs. limit {limit:,.0f} (50% of {base:,.0f})",
        "consequence": ("Board of directors must take restructuring measures; if there is "
                        "no auditor, the annual accounts must be audited (limited audit)."
                        if loss else ""),
    }


def over_indebtedness(fy):
    """CO Art. 725b: liabilities are no longer covered by assets."""
    over = fy.total_liabilities > fy.total_assets
    return {
        "test": "Over-indebtedness (CO Art. 725b)",
        "status": RED if over else GREEN,
        "result": "Justified concern of over-indebtedness" if over else "No over-indebtedness",
        "detail": (f"Liabilities {fy.total_liabilities:,.0f} vs. assets {fy.total_assets:,.0f} "
                   "(book values; going concern AND liquidation values must be tested)"),
        "consequence": ("Interim accounts at going concern and liquidation values must be "
                        "audited; the court must be notified unless creditors subordinate "
                        "their claims." if over else ""),
    }


def impending_insolvency(liquidity_result):
    """CO Art. 725: impending insolvency within 12 months. Needs the
    forward-looking liquidity plan - historical statements cannot answer it."""
    if liquidity_result is None:                   # no liquidity plan yet (page 5)
        return {"test": "Impending insolvency (CO Art. 725)", "status": GREY,
                "result": "Not assessed yet",
                "detail": "Complete the 12-month liquidity planner.", "consequence": ""}
    m = liquidity_result["first_shortfall_base"]   # first month short of cash, without measures
    if m is None:
        return {"test": "Impending insolvency (CO Art. 725)", "status": GREEN,
                "result": "Solvency secured for 12 months",
                "detail": f"Lowest headroom: {liquidity_result['min_headroom_base']:,.0f}",
                "consequence": ""}
    # Shortfall: amber if the restructuring measures close the gap, red if not
    cured = liquidity_result["first_shortfall_measures"] is None
    return {
        "test": "Impending insolvency (CO Art. 725)",
        "status": AMBER if cured else RED,
        "result": f"Liquidity shortfall in month {m}",
        "detail": ("Planned restructuring measures close the gap." if cured
                   else "Planned measures do NOT close the gap."),
        "consequence": "Board must take measures to secure solvency (CO Art. 725).",
    }


# --- II-IV) Ratios with thresholds ---
# nan instead of an error if the denominator is 0 -> status grey
def _div(a, b):
    return a / b if b else float("nan")


# Describes one ratio; the value comes from RATIO_FUNCS, the traffic light from RATIO_STATUS (below).
@dataclass
class Ratio:
    key: str
    name: str
    group: str           # Liquidity / Cash flow and debt / Capital and profitability
    formula: str         # shown to the user
    unit: str            # "x", "%", "CHF", "years"
    weight: float        # weight in the quantitative score (0 = display only)
    explanation: str     # thresholds as text

    def value(self, fy):
        return RATIO_FUNCS[self.key](fy)

    def status(self, fy):
        return RATIO_STATUS[self.key](fy, self.value(fy))


def _band(v, green_from, red_below):
    """Higher is better: >= green_from -> green, < red_below -> red, else amber."""
    if v is None or math.isnan(v):
        return GREY
    if v >= green_from:
        return GREEN
    return RED if v < red_below else AMBER


RATIO_FUNCS = {
    "cash_ratio": lambda f: _div(f.cash, f.current_liabilities),
    "quick_ratio": lambda f: _div(f.cash + f.receivables, f.current_liabilities),
    "current_ratio": lambda f: _div(f.current_assets, f.current_liabilities),
    "net_working_capital": lambda f: f.current_assets - f.current_liabilities,
    "operating_cash_flow": lambda f: f.ocf,
    "net_debt_ebitda": lambda f: _div(f.interest_bearing_debt - f.cash, f.ebitda),
    "interest_coverage": lambda f: _div(f.ebit, f.interest_expense),
    "debt_payback": lambda f: _div(f.total_liabilities - f.cash, f.ocf),
    "equity_ratio": lambda f: _div(f.equity, f.total_assets),
    "ebitda_margin": lambda f: _div(f.ebitda, f.revenue),
    "roa": lambda f: _div(f.net_income, f.total_assets),
}


# Special status rules for ratios where the plain number can be misleading:
# Net debt / EBITDA: lower is better; a negative EBITDA would give a "good" negative value
def _net_debt_status(f, v):
    if f.interest_bearing_debt - f.cash <= 0:
        return GREEN                      # net cash position
    if f.ebitda <= 0:
        return RED                        # debt cannot be served from earnings
    green_to, red_above = thresholds(f.industry, "net_debt_ebitda")
    return GREEN if v <= green_to else (AMBER if v <= red_above else RED)


def _ind(key):
    """Status function using the industry-specific thresholds (logic/data_input.py)."""
    return lambda f, v: _band(v, *thresholds(f.industry, key))


# Green from 3x, red below 1.5x
def _interest_status(f, v):
    if f.interest_expense <= 0:
        return GREEN                      # no interest burden
    return _band(v, 3.0, 1.5)


# Years needed to repay the debt from the operating cash flow: green up to 5, red above 8
def _payback_status(f, v):
    if f.total_liabilities - f.cash <= 0:
        return GREEN                      # no net debt
    if f.ocf <= 0:
        return RED                        # negative cash flow: debt is never repaid
    return GREEN if v <= 5 else (AMBER if v <= 8 else RED)


# _ind(...) = thresholds depend on the industry (company profile)
RATIO_STATUS = {
    "cash_ratio": _ind("cash_ratio"),
    "quick_ratio": _ind("quick_ratio"),
    "current_ratio": _ind("current_ratio"),
    "net_working_capital": lambda f, v: GREEN if v >= 0 else RED,
    "operating_cash_flow": lambda f, v: GREEN if v > 0 else RED,
    "net_debt_ebitda": _net_debt_status,
    "interest_coverage": _interest_status,
    "debt_payback": _payback_status,
    "equity_ratio": _ind("equity_ratio"),
    "ebitda_margin": _ind("ebitda_margin"),
    "roa": lambda f, v: _band(v, 0.02, 0.0),
}

# All 11 ratios in the order shown on page 3.
# Weight 2 = strong going concern indicator (cash flow, net debt, equity), 1 = normal, 0 = display only.
RATIOS = [
    # II) Liquidity
    Ratio("cash_ratio", "Cash ratio", "Liquidity", "Cash / current liabilities", "x", 1,
          "Green >= 0.2, red < 0.1"),
    Ratio("quick_ratio", "Quick ratio", "Liquidity",
          "(Cash + short-term receivables) / current liabilities", "x", 1,
          "Green >= 1.0, red < 0.7"),
    Ratio("current_ratio", "Current ratio", "Liquidity", "Current assets / current liabilities",
          "x", 1, "Green >= 1.5, red < 1.0"),
    Ratio("net_working_capital", "Net working capital", "Liquidity",
          "Current assets - current liabilities", "CHF", 0,
          "Red if negative. Display only - same information as the current ratio."),
    # III) Cash flow and debt
    Ratio("operating_cash_flow", "Operating cash flow", "Cash flow and debt",
          "From the cash flow statement", "CHF", 2,
          "Red if negative (ISA 570.A3: negative operating cash flows)"),
    Ratio("net_debt_ebitda", "Net debt / EBITDA", "Cash flow and debt",
          "(Interest-bearing debt - cash) / EBITDA", "x", 2,
          "Green <= 3, red > 4 or EBITDA <= 0. Typical bank covenant."),
    Ratio("interest_coverage", "Interest coverage", "Cash flow and debt",
          "EBIT / interest expense", "x", 1, "Green >= 3, red < 1.5"),
    Ratio("debt_payback", "Debt payback period", "Cash flow and debt",
          "(Total liabilities - cash) / operating cash flow", "years", 1,
          "Green <= 5 years, red > 8 years or negative cash flow"),
    # IV) Capital and profitability
    Ratio("equity_ratio", "Equity ratio", "Capital and profitability",
          "Equity / total assets", "%", 2, "Green >= 20%, red < 10%"),
    Ratio("ebitda_margin", "EBITDA margin", "Capital and profitability",
          "EBITDA / revenue", "%", 1, "Green >= 8%, red < 0%"),
    Ratio("roa", "Return on assets (ROA)", "Capital and profitability",
          "Net income / total assets", "%", 1,
          "Green >= 2%, red < 0% (ISA 570.A3: substantial operating losses)"),
]
RATIO_BY_KEY = {r.key: r for r in RATIOS}


def fmt(value, unit):
    """Format a ratio value for display."""
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "n/a"
    if unit == "%":
        return f"{value:.1%}"
    if unit == "CHF":
        return f"{value:,.0f}"
    if unit == "years":
        return f"{value:.1f} y" if value >= 0 else "negative"
    return f"{value:.2f}"


# Ratios whose thresholds change with the industry (defined in logic/data_input.py)
INDUSTRY_KEYS = {"cash_ratio", "quick_ratio", "current_ratio", "equity_ratio", "ebitda_margin",
                 "net_debt_ebitda"}


def threshold_text(ratio, industry):
    """Thresholds as text for the active industry."""
    if ratio.key not in INDUSTRY_KEYS:
        return ratio.explanation
    g, r = thresholds(industry, ratio.key)
    show = (lambda x: f"{x:.0%}") if ratio.unit == "%" else (lambda x: f"{x:g}")
    if ratio.key == "net_debt_ebitda":
        return f"Green <= {show(g)}, red > {show(r)} or EBITDA <= 0 ({industry})"
    return f"Green >= {show(g)}, red < {show(r)} ({industry})"


def display(ratio, fy):
    """Value as text. Ratios with a negative denominator are meaningless as a
    number, so we show the reason instead (e.g. "EBITDA <= 0")."""
    if ratio.key == "net_debt_ebitda":
        if fy.interest_bearing_debt - fy.cash <= 0:
            return "net cash"
        if fy.ebitda <= 0:
            return "EBITDA <= 0"
    if ratio.key == "debt_payback":
        if fy.total_liabilities - fy.cash <= 0:
            return "no net debt"
        if fy.ocf <= 0:
            return "cash flow <= 0"
    if ratio.key == "interest_coverage" and fy.interest_expense <= 0:
        return "no interest"
    return fmt(ratio.value(fy), ratio.unit)


def ratio_table(years):
    """All ratios for all years: list of dicts (one per ratio)."""
    rows = []
    for r in RATIOS:
        row = {"key": r.key, "Ratio": r.name, "Group": r.group, "Formula": r.formula,
               "Thresholds": r.explanation}
        for fy in years:
            v = r.value(fy)
            row[fy.year] = (v, r.status(fy))
        rows.append(row)
    return rows


# --- Trend analysis (3-5 years) ---
# For net debt / EBITDA and debt payback lower is better
HIGHER_IS_BETTER = {k: True for k in RATIO_FUNCS} | {"net_debt_ebitda": False,
                                                     "debt_payback": False}


def _trend_value(key, fy):
    """Value used for the trend. For "lower is better" ratios a negative
    denominator means the worst case, so it is replaced by a high cap value."""
    v = RATIO_FUNCS[key](fy)
    if key == "net_debt_ebitda":
        if fy.interest_bearing_debt - fy.cash <= 0:
            return 0.0
        return 20.0 if fy.ebitda <= 0 else min(v, 20.0)
    if key == "debt_payback":
        if fy.total_liabilities - fy.cash <= 0:
            return 0.0
        return 30.0 if fy.ocf <= 0 else min(v, 30.0)
    return v


def trend(ratio_key, years):
    """Direction of a ratio over the available years:
    'improving', 'deteriorating', 'stable' or 'n/a' (fewer than 2 years).
    Uses the slope of a simple linear regression."""
    vals = [_trend_value(ratio_key, fy) for fy in years]
    # (year index, value); years without a valid value are left out
    pts = [(i, v) for i, v in enumerate(vals) if v is not None and math.isfinite(v)]
    if len(pts) < 2:
        return "n/a"
    # Least-squares slope = average change per year
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    slope = sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx
    # Relative to the average value, so ratios of different size are comparable
    # (1e-9 avoids dividing by 0)
    scale = max(abs(my), 1e-9)
    if abs(slope) / scale < 0.03:     # less than 3% change per year -> stable
        return "stable"
    better = slope > 0 if HIGHER_IS_BETTER[ratio_key] else slope < 0
    return "improving" if better else "deteriorating"


# --- Quantitative score: all ratios in ONE number between 0 and 1 ---
# The "Ratios" part of the overall assessment (assess() in logic/assessment.py).
# Our project concept added/deducted a percentage per ratio; we use a weighted share instead,
# so the result always stays between 0 and 1:
#     score = sum(weight x STATUS_POINTS) / sum(weights)
# Example with weights 2, 1, 1: red (2 x 1.0) + amber (1 x 0.5) + green (1 x 0.0) = 2.5 of 4 -> 0.625
def quantitative_score(years):
    """Weighted share of critical ratios in the latest year (0 = all green,
    1 = all red). Ratios that cannot be computed are ignored."""
    fy = years[-1]                     # only the latest year counts (trends are shown separately on page 3)
    total = points = 0.0
    for r in RATIOS:
        st = r.status(fy)
        # skip display-only (weight 0) and grey ratios, so missing data does not
        # make the company look better or worse
        if r.weight == 0 or st == GREY:
            continue
        total += r.weight
        points += r.weight * STATUS_POINTS[st]
    return points / total if total else 0.0


# --- 12-month liquidity planner (Swiss CO Art. 725: impending insolvency) ---
# Two scenarios: base case (without measures) and base case + planned restructuring measures.
# The result is used on page 5, in impending_insolvency above and as a knock-out criterion in
# assess() (logic/assessment.py).

MONTHS = [f"M{i}" for i in range(1, 13)]

# Options of the "Type" dropdown on page 5
MEASURE_TYPES = [
    "Capital increase", "New or extended credit line", "Shareholder loan",
    "Sale of non-core assets", "Cost reduction", "Deferral of payments",
    "Subordination of claims", "Other",
]


def default_plan(fy):
    """Starting point derived from the latest financial year: receipts =
    revenue / 12, payments chosen so that the monthly net cash flow equals
    the operating cash flow / 12. The auditor/client adjusts these figures."""
    receipts = round(fy.revenue / 12, -3)               # rounded to thousands
    payments = round(receipts - fy.ocf / 12, -3)
    # Debt service starts at 0 and is entered by the user
    return pd.DataFrame({"Month": MONTHS, "Receipts": [receipts] * 12,
                         "Operating payments": [payments] * 12,
                         "Debt service": [0.0] * 12})


# The dtypes are fixed so that the table editor on page 5 shows the right input fields.
def empty_measures():
    return pd.DataFrame({"Measure": pd.Series(dtype="str"),
                         "Type": pd.Series(dtype="str"),
                         "Month": pd.Series(dtype="int"),
                         "Amount": pd.Series(dtype="float")})


def evaluate_plan(opening_cash, credit_line, plan, measures):
    """Runs the plan month by month.

    Headroom = cash balance + undrawn committed credit line.
    A shortfall occurs in the first month in which headroom becomes negative.
    """
    plan = plan.fillna(0)
    net = (plan["Receipts"] - plan["Operating payments"] - plan["Debt service"]).tolist()

    # Cash from restructuring measures per month; incomplete rows are ignored
    extra = [0.0] * 12
    for _, m in measures.dropna(subset=["Month", "Amount"]).iterrows():
        month = int(m["Month"])
        if 1 <= month <= 12:
            extra[month - 1] += float(m["Amount"])

    # Runs one scenario; add = additional cash per month
    def run(add):
        cash, balances = opening_cash, []
        for i in range(12):
            cash += net[i] + add[i]
            balances.append(cash)
        headroom = [b + credit_line for b in balances]
        # first month with negative headroom (1-12); None if it never happens
        shortfall = next((i + 1 for i, h in enumerate(headroom) if h < 0), None)
        return balances, headroom, shortfall

    bal_b, head_b, short_b = run([0.0] * 12)      # base case
    bal_m, head_m, short_m = run(extra)           # with measures
    avg_burn = -sum(net) / 12                     # positive = money is lost
    available = opening_cash + credit_line
    # first_shortfall_measures is the knock-out criterion in assess() (logic/assessment.py)
    return {
        "balance_base": bal_b, "headroom_base": head_b,
        "balance_measures": bal_m, "headroom_measures": head_m,
        "first_shortfall_base": short_b, "first_shortfall_measures": short_m,
        "min_headroom_base": min(head_b), "min_headroom_measures": min(head_m),
        "measures_total": sum(extra),
        # months the liquidity lasts at the average outflow (None = no net outflow)
        "runway_months": available / avg_burn if avg_burn > 0 else None,
    }
