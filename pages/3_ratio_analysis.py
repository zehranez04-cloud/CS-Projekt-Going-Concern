"""Step 3: legal thresholds, ratios with traffic lights and trend analysis."""

import plotly.graph_objects as go
import streamlit as st

import shared
from logic import analysis

st.title("3 · Ratio analysis")
ys = shared.require_financials()
latest = ys[-1]
st.caption(f"Traffic lights refer to the latest year ({latest.year}) and use the thresholds "
           f"for the industry **{latest.industry}** (see company profile). "
           f"Trend over {len(ys)} year(s): {ys[0].year}–{latest.year}.")

if not latest.has_cash_flow_statement:
    st.info("No cash flow statement for the latest year: operating cash flow is approximated "
            "as net income + depreciation.")

# ---------------------------------------------------------------------------
# I) Legal thresholds
# ---------------------------------------------------------------------------
st.subheader("I · Legal thresholds (Swiss CO)")
cols = st.columns(3)
for col, t in zip(cols, shared.legal_tests(latest)):
    with col:
        # The legal consequence is shown inside the card, so all cards have the same height
        text = t["detail"] + (f"  \n:material/warning: {t['consequence']}" if t["consequence"] else "")
        shared.traffic_light(t["status"], t["test"], t["result"], text)

# ---------------------------------------------------------------------------
# II-IV) Ratio cockpit
# ---------------------------------------------------------------------------
TREND_ICON = {"improving": ":material/trending_up:", "deteriorating": ":material/trending_down:",
              "stable": ":material/trending_flat:", "n/a": ""}

for group, roman in [("Liquidity", "II"), ("Cash flow and debt", "III"),
                     ("Capital and profitability", "IV")]:
    st.subheader(f"{roman} · {group}")
    group_ratios = [r for r in analysis.RATIOS if r.group == group]
    cols = st.columns(len(group_ratios))
    for col, r in zip(cols, group_ratios):
        tr = analysis.trend(r.key, ys)
        with col:
            shared.traffic_light(r.status(latest), r.name, analysis.display(r, latest),
                             f"{TREND_ICON[tr]} {tr} · {r.formula}")

# ---------------------------------------------------------------------------
# Table: all years
# ---------------------------------------------------------------------------
st.subheader("All years")

# Soft colours for the dots 
SOFT = {"green": "#8CC9A6", "amber": "#EFCF7A", "red": "#E89A9A", "grey": "#D0D5D8"}
TREND_TEXT = {"improving": "↗ improving", "deteriorating": "↘ deteriorating",
              "stable": "→ stable", "n/a": "–"}

def dot(status):
    """Small round dot in the soft colour of the traffic light."""
    return (f"<span style='display:inline-block;width:9px;height:9px;border-radius:50%;"
            f"background:{SOFT[status]};margin-right:8px;vertical-align:middle'></span>")


# The table is built as HTML: it shows all rows at once 
head = "".join(f"<th class='num'>{fy.year}</th>" for fy in ys)
body = ""
for group in ["Liquidity", "Cash flow and debt", "Capital and profitability"]:
    body += f"<tr class='group'><td colspan='{len(ys) + 2}'>{group}</td></tr>"
    for r in [x for x in analysis.RATIOS if x.group == group]:
        cells = "".join(f"<td class='num'>{dot(r.status(fy))}{analysis.display(r, fy)}</td>" for fy in ys)
        body += f"<tr><td>{r.name}</td>{cells}<td class='trend'>{TREND_TEXT[analysis.trend(r.key, ys)]}</td></tr>"

st.html(f"""
<style>
  .ratios {{ width:100%; border-collapse:collapse; font-size:14px; color:#1E2B33; }}
  .ratios th {{ text-align:left; font-weight:600; padding:8px 10px; border-bottom:2px solid #E3E8EB; }}
  .ratios td {{ padding:7px 10px; border-bottom:1px solid #EEF2F4; }}
  .ratios .num, .ratios td:first-child {{ white-space:nowrap; }}
  .ratios .group td {{ background:#F6F8F9; font-weight:600; font-size:12px; color:#5F6B73;
                       text-transform:uppercase; letter-spacing:0.04em; }}
  .ratios .trend {{ color:#5F6B73; white-space:nowrap; }}
</style>
<table class="ratios">
  <tr><th>Ratio</th>{head}<th>Trend</th></tr>
  {body}
</table>""")

# ---------------------------------------------------------------------------
# Trend chart with threshold bands (interactive selection)
# ---------------------------------------------------------------------------
st.subheader("Trend of a ratio")
choice = st.selectbox("Select ratio", [r.name for r in analysis.RATIOS], index=8)
r = next(x for x in analysis.RATIOS if x.name == choice)
x = [fy.year for fy in ys]
y = [r.value(fy) for fy in ys]
fig = go.Figure()
fig.add_scatter(x=x, y=y, mode="lines+markers", line=dict(color="#1E2B33", width=3),
                marker=dict(size=12, color=[shared.HEX[r.status(fy)] for fy in ys],
                            line=dict(color="#1E2B33", width=1)),
                hovertemplate="%{x}: %{y:.3f}<extra></extra>")
fig.update_layout(height=380, margin=dict(t=20, b=20), template="simple_white",
                  yaxis_tickformat=".0%" if r.unit == "%" else None, yaxis_title=r.formula)
st.plotly_chart(fig, width="stretch")
st.caption(f"Thresholds: {analysis.threshold_text(r, latest.industry)}. Marker colour = traffic light of that year.")

# Balance sheet structure over time
st.subheader("Balance sheet structure")
fig = go.Figure()
fig.add_bar(name="Equity", x=x, y=[fy.equity for fy in ys], marker_color="#055933")
fig.add_bar(name="Interest-bearing debt", x=x, y=[fy.interest_bearing_debt for fy in ys],
            marker_color="#055885")
fig.add_bar(name="Other liabilities", x=x,
            y=[fy.total_liabilities - fy.interest_bearing_debt for fy in ys], marker_color="#A9B8C0")
fig.add_scatter(name="Net income", x=x, y=[fy.net_income for fy in ys], mode="lines+markers",
                line=dict(color="#D64545", width=3))
fig.update_layout(barmode="relative", height=380, margin=dict(t=20, b=20), template="simple_white",
                  legend=dict(orientation="h", y=-0.15))
st.plotly_chart(fig, width="stretch")

shared.next_step("pages/4_questionnaire.py", "Continue with step 4: ISA 570 questionnaire")
