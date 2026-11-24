"""Step 3: legal thresholds, ratios with traffic lights and trend analysis."""

# Shows the three legal tests of the Swiss CO, 11 ratios as traffic-light cards, a table over all
# years and two trend charts. The calculations are in logic/analysis.py; the ratios also form the
# "Ratios" score of the overall assessment (page 7).
# Use of generative AI:
# - Code: parts of the code in this file were written with the help of Claude (Anthropic). We reviewed, tested and adjusted them.
# - Comments: Claude was used as support for writing the comments and making sure that the structure fits. We checked and partly adjusted them.

import plotly.graph_objects as go
import streamlit as st

import shared
from logic import analysis

st.title("3 · Ratio analysis")
ys = shared.require_financials()              # oldest first; stops the page if none are loaded
latest = ys[-1]                               # the traffic lights refer to the latest year
st.caption(f"Traffic lights refer to the latest year ({latest.year}) and use the thresholds "
           f"for the industry **{latest.industry}** (see company profile). "
           f"Trend over {len(ys)} year(s): {ys[0].year}–{latest.year}.")

if not latest.has_cash_flow_statement:
    st.info("No cash flow statement for the latest year: operating cash flow is approximated "
            "as net income + depreciation.")

# --- I) Legal thresholds ---
st.subheader("I · Legal thresholds (Swiss CO)")
cols = st.columns(3)
for col, t in zip(cols, shared.legal_tests(latest)):
    with col:
        # consequence inside the card, so all cards have the same height
        text = t["detail"] + (f"  \n:material/warning: {t['consequence']}" if t["consequence"] else "")
        shared.traffic_light(t["status"], t["test"], t["result"], text)

# --- II-IV) Ratio cockpit ---
TREND_ICON = {"improving": ":material/trending_up:", "deteriorating": ":material/trending_down:",
              "stable": ":material/trending_flat:", "n/a": ""}

for group, roman in [("Liquidity", "II"), ("Cash flow and debt", "III"),
                     ("Capital and profitability", "IV")]:
    st.subheader(f"{roman} · {group}")
    group_ratios = [r for r in analysis.RATIOS if r.group == group]
    cols = st.columns(len(group_ratios))
    for col, r in zip(cols, group_ratios):
        tr = analysis.trend(r.key, ys)        # trend over all years, colour only for the latest year
        with col:
            shared.traffic_light(r.status(latest), r.name, analysis.display(r, latest),
                             f"{TREND_ICON[tr]} {tr}  \n:gray[{r.formula}]")

# --- Table: all years ---
st.subheader("All years")

TREND_TEXT = {"improving": "↗ improving", "deteriorating": "↘ deteriorating",
              "stable": "→ stable", "n/a": "–"}

def dot(status):
    """Small round dot in the colour of the traffic light (style: .gc-dot in assets/gocon.css)."""
    return f"<span class='gc-dot gc-dot-sm gc-dot-{status}'></span>"


# Built as HTML instead of st.dataframe: shows all rows at once and allows coloured dots per cell
head = "".join(f"<th class='num'>{fy.year}</th>" for fy in ys)
body = ""
for group in ["Liquidity", "Cash flow and debt", "Capital and profitability"]:
    # grey heading row per group, spanning all columns (ratio + years + trend)
    body += f"<tr class='group'><td colspan='{len(ys) + 2}'>{group}</td></tr>"
    for r in [x for x in analysis.RATIOS if x.group == group]:
        cells = "".join(f"<td class='num'>{dot(r.status(fy))}{analysis.display(r, fy)}</td>" for fy in ys)
        body += f"<tr><td>{r.name}</td>{cells}<td class='trend'>{TREND_TEXT[analysis.trend(r.key, ys)]}</td></tr>"

# Layout in assets/gocon.css (.ratios); the wrapper scrolls sideways on small screens.
st.html(f"""
<div class="gc-table-wrap"><table class="ratios">
  <tr><th>Ratio</th>{head}<th>Trend</th></tr>
  {body}
</table></div>""")

# --- Trend chart of one ratio ---
st.subheader("Trend of a ratio")
choice = st.selectbox("Select ratio", [r.name for r in analysis.RATIOS], index=8)   # index 8 = equity ratio
r = next(x for x in analysis.RATIOS if x.name == choice)
x = [fy.year for fy in ys]
y = [r.value(fy) for fy in ys]
# marker colour = traffic light of that year
fig = go.Figure()
fig.add_scatter(x=x, y=y, mode="lines+markers", line=dict(color=shared.TEXT, width=3),
                marker=dict(size=12, color=[shared.HEX[r.status(fy)] for fy in ys],
                            line=dict(color=shared.TEXT, width=1)),
                hovertemplate="%{x}: %{y:.3f}<extra></extra>")
fig.update_layout(height=380, margin=dict(t=20, b=20), template="simple_white",
                  yaxis_tickformat=".0%" if r.unit == "%" else None, yaxis_title=r.formula)
st.plotly_chart(fig, width="stretch")
st.caption(f"Thresholds: {analysis.threshold_text(r, latest.industry)}. Marker colour = traffic light of that year.")

# --- Balance sheet structure ---
st.subheader("Balance sheet structure")
# Stacked bars (= total assets) plus net income as a line -> shows how losses eat up the equity
fig = go.Figure()
fig.add_bar(name="Equity", x=x, y=[fy.equity for fy in ys], marker_color=shared.TEXT_MUTED)
fig.add_bar(name="Interest-bearing debt", x=x, y=[fy.interest_bearing_debt for fy in ys],
            marker_color=shared.LINE)
fig.add_bar(name="Other liabilities", x=x,
            y=[fy.total_liabilities - fy.interest_bearing_debt for fy in ys], marker_color=shared.ACCENT_LIGHT)
fig.add_scatter(name="Net income", x=x, y=[fy.net_income for fy in ys], mode="lines+markers",
                line=dict(color=shared.ACCENT, width=3))
# "relative" stacks negative values (negative equity) below zero
fig.update_layout(barmode="relative", height=380, margin=dict(t=20, b=20), template="simple_white",
                  legend=dict(orientation="h", y=-0.15))
st.plotly_chart(fig, width="stretch")

shared.next_step("pages/4_questionnaire.py", "Continue with step 4: ISA 570 questionnaire")
