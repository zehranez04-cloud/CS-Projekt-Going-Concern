"""Step 5: 12-month liquidity planner with restructuring measures (CO Art. 725)."""

import plotly.graph_objects as go
import streamlit as st

import shared
from logic import analysis

st.title("5 · Liquidity planner")
ys = shared.require_financials()
latest = ys[-1]
st.caption("Swiss CO Art. 725: the board must monitor solvency. If insolvency is impending "
           "within 12 months, it must take restructuring measures. Prepare (or review "
           "management's) monthly plan and record the planned measures.")

ss = st.session_state
if ss.liquidity_inputs is None:          # first visit: prefill from the latest year
    ss.liquidity_inputs = {"opening_cash": float(latest.cash), "credit_line": 0.0,
                           "plan": analysis.default_plan(latest),
                           "measures": analysis.empty_measures()}
li = ss.liquidity_inputs
v = ss.editor_version

c1, c2 = st.columns(2)
li["opening_cash"] = c1.number_input("Opening cash balance", value=float(li["opening_cash"]),
                                     step=10_000.0, format="%.0f", key=f"open_{v}")
li["credit_line"] = c2.number_input("Undrawn committed credit lines", value=float(li["credit_line"]),
                                    step=10_000.0, format="%.0f", key=f"cl_{v}",
                                    help="Only lines the bank has committed in writing.")

st.subheader("Monthly cash flows")
st.caption("Prefilled from the latest year (revenue / 12; net flow = operating cash flow / 12). "
           "Adjust to the budget – e.g. add loan repayments under 'Debt service'.")
li["plan"] = st.data_editor(li["plan"], hide_index=True, width="stretch", disabled=["Month"],
                            key=f"plan_{v}",
                            column_config={c: st.column_config.NumberColumn(c, format="localized", step=1000.0)
                                           for c in ("Receipts", "Operating payments", "Debt service")})

st.subheader("Restructuring measures")
st.caption("Cash effect of each planned measure in the month it is expected (positive = inflow).")
# Rows can be added here. The editor must always start from the same base table,
# otherwise added rows would be applied twice. The base is refreshed whenever
# the editor is shown anew (widget state is removed when leaving the page).
if f"meas_{v}" not in ss:
    ss["measures_base"] = li["measures"].copy()
li["measures"] = st.data_editor(
    ss["measures_base"], num_rows="dynamic", hide_index=True, width="stretch", key=f"meas_{v}",
    column_config={
        "Measure": st.column_config.TextColumn("Description"),
        "Type": st.column_config.SelectboxColumn("Type", options=analysis.MEASURE_TYPES),
        "Month": st.column_config.NumberColumn("Month", min_value=1, max_value=12, step=1),
        "Amount": st.column_config.NumberColumn("Cash effect", format="localized", step=10_000.0),
    })

res = analysis.evaluate_plan(li["opening_cash"], li["credit_line"], li["plan"], li["measures"])

# ---------------------------------------------------------------------------
# Chart: headroom with and without measures
# ---------------------------------------------------------------------------
fig = go.Figure()
fig.add_bar(x=analysis.MONTHS, y=res["headroom_base"], name="Headroom without measures",
            marker_color=[shared.RED_HEX if h < 0 else "#A9B8C0" for h in res["headroom_base"]])
fig.add_scatter(x=analysis.MONTHS, y=res["headroom_measures"], name="Headroom with measures",
                mode="lines+markers", line=dict(color=shared.GREEN_HEX, width=3))
fig.add_hline(y=0, line_color="#1E2B33")
fig.update_layout(height=380, template="simple_white", margin=dict(t=20, b=20),
                  yaxis_title="Cash + undrawn credit lines", legend=dict(orientation="h", y=-0.15))
st.plotly_chart(fig, width="stretch")

test = analysis.impending_insolvency(res)
c1, c2, c3 = st.columns(3)
with c1:
    shared.traffic_light(test["status"], "CO Art. 725", test["result"], test["detail"])
with c2:
    runway = res["runway_months"]
    shared.traffic_light("green" if runway is None or runway >= 12 else "red", "Runway",
                     "no net outflow" if runway is None else f"{runway:.1f} months",
                     "Available liquidity / average monthly net outflow")
with c3:
    shared.traffic_light("green" if res["min_headroom_measures"] >= 0 else "red",
                     "Lowest headroom with measures", f"{res['min_headroom_measures']:,.0f}",
                     f"Measures total: {res['measures_total']:,.0f}")

shared.next_step("pages/6_bankruptcy_model.py", "Continue with step 6: Bankruptcy model")
