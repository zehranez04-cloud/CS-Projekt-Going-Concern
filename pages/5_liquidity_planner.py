"""Step 5: 12-month liquidity planner with restructuring measures (CO Art. 725)."""

# Answers: is there enough cash and committed credit for the next 12 months, and do the planned
# restructuring measures close a possible gap? The calculation is in logic/analysis.py (evaluate_plan);
# the result feeds the legal test "impending insolvency" (page 3) and the knock-out check (page 7).
# Use of generative AI:
# - Code: parts of the code in this file were written with the help of Claude (Anthropic). We reviewed, tested and adjusted them.
# - Comments: Claude was used as support for writing the comments and making sure that the structure fits. We checked and partly adjusted them.

import plotly.graph_objects as go
import streamlit as st

import shared
from logic import analysis

st.title("5 · Liquidity planner")
ys = shared.require_financials()
latest = ys[-1]                      # the plan is prefilled from the latest year
st.caption("Swiss CO Art. 725: the board must monitor solvency. If insolvency is impending "
           "within 12 months, it must take restructuring measures. Prepare (or review "
           "management's) monthly plan and record the planned measures.")


# Streamlit reruns the whole file after every click; only the session state survives.
ss = st.session_state


if ss.liquidity_inputs is None:      # first visit: prefill from the latest year
    ss.liquidity_inputs = {"opening_cash": float(latest.cash), "credit_line": 0.0,
                           "plan": analysis.default_plan(latest),
                           "measures": analysis.empty_measures()}

# li is a reference, not a copy: changing li changes the session state directly,
# so the inputs stay when the user switches pages.
li = ss.liquidity_inputs
# Part of every widget key: when a sample or audit file is loaded, v changes and the widgets
# are rebuilt with the new values instead of keeping the old ones.
v = ss.editor_version

c1, c2 = st.columns(2)

li["opening_cash"] = c1.number_input("Opening cash balance", value=float(li["opening_cash"]),
                                     step=10_000.0, format="%.0f", key=f"open_{v}")

# only committed lines count as safe liquidity
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
# --- Restructuring measures ---
st.subheader("Restructuring measures")

st.caption("Cash effect of each planned measure in the month it is expected (positive = inflow).")

# Workaround for num_rows="dynamic": the editor must always get the same base table, otherwise
# added rows would be applied twice. A new snapshot is taken only when the editor widget does not
# exist yet (first visit, or after leaving the page, when Streamlit removes its widget state).
if f"meas_{v}" not in ss:
    ss["measures_base"] = li["measures"].copy()

li["measures"] = st.data_editor(

    ss["measures_base"], num_rows="dynamic", hide_index=True, width="stretch", key=f"meas_{v}",
    column_config={
        "Measure": st.column_config.TextColumn("Description"),
        # dropdown, so only types defined in logic/analysis.py can be chosen
        "Type": st.column_config.SelectboxColumn("Type", options=analysis.MEASURE_TYPES),
        # the plan only covers 12 months
        "Month": st.column_config.NumberColumn("Month", min_value=1, max_value=12, step=1),
        # positive = inflow, negative = outflow
        "Amount": st.column_config.NumberColumn("Cash effect", format="localized", step=10_000.0),
    })


# Recalculated on every rerun, so the chart and cards update live
res = analysis.evaluate_plan(li["opening_cash"], li["credit_line"], li["plan"], li["measures"])


# --- Chart: headroom with and without measures ---
fig = go.Figure()

# bars = without measures, red in months with negative headroom
fig.add_bar(x=analysis.MONTHS, y=res["headroom_base"], name="Headroom without measures",
            marker_color=[shared.RED_HEX if h < 0 else shared.LINE for h in res["headroom_base"]])

# line = with measures; bars vs. line shows at once whether the measures help
fig.add_scatter(x=analysis.MONTHS, y=res["headroom_measures"], name="Headroom with measures",
                mode="lines+markers", line=dict(color=shared.ACCENT, width=3))

# zero line: below it the company cannot pay its bills
fig.add_hline(y=0, line_color=shared.TEXT)

fig.update_layout(height=380, template="simple_white", margin=dict(t=20, b=20),
                  yaxis_title="Cash + undrawn credit lines", legend=dict(orientation="h", y=-0.15))

st.plotly_chart(fig, width="stretch")


# --- Result cards ---
test = analysis.impending_insolvency(res)


c1, c2, c3 = st.columns(3)

with c1:
    shared.traffic_light(test["status"], "CO Art. 725", test["result"], test["detail"])


with c2:
    runway = res["runway_months"]

    # runway None = no net outflow. The None check must come first, otherwise
    # "None >= 12" would raise an error.
    shared.traffic_light("green" if runway is None or runway >= 12 else "red", "Runway",
                     "no net outflow" if runway is None else f"{runway:.1f} months",
                     "Available liquidity / average monthly net outflow")

with c3:
    # green if the measures avoid a shortfall in every month
    shared.traffic_light("green" if res["min_headroom_measures"] >= 0 else "red",
                     "Lowest headroom with measures", f"{res['min_headroom_measures']:,.0f}",
                     f"Measures total: {res['measures_total']:,.0f}")

shared.next_step("pages/6_bankruptcy_model.py", "Continue with step 6: Bankruptcy model")
