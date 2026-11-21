"""Step 5: 12-month liquidity planner with restructuring measures (CO Art. 725).""" #Do we have enough cash and commmited credit over the next 12 months, what happens if we take resturcturing measures, and is that enough?

import plotly.graph_objects as go 
#plotly is a libary, toolbox of code that someone else wrote, to draw charts. 
# #graph_objects is the part of it that lets us build a chart piece by piece (bars, lines, labels).
#"as go" gives it a short nickname, so later we can write go.Figure() instead of plotly.graph_objects.Figure() 
#We need it on this page to draw the liquidity Chart (bars and a line). We also use it in the bankruptcy model to draw the waterfall chart.
import streamlit as st
# Streamlit is the library that turns our Python file into a web page.
# It gives us the buttons, input fields, tables and titles the user sees.
# "as st" is the usual nickname, so every page element starts with st. (st.title, st.columns). 

import shared
# "shared" is a file written by our own team.
# It holds helper tools that several pages use (checks, colours, traffic lights, the next-step button).
# We import it so this page can write shared.something(...) and reuse that code instead of copying it.
from logic import analysis
# "logic" is a folder in our project where the calculations are, and "analysis" is one file inside it.
# from the folder logic, take the file analysis.
# We keep the maths there so this page only has to show things, and each teammate can work on their own file.

st.title("5 · Liquidity planner")
# Puts the big heading at the top of the web page. The "5" is the step number in our app.
ys = shared.require_financials()
# Asks the shared helper for the financial statements entered in the earlier steps.
# If they are missing, the helper is meant to stop the page and tell the user to enter them first.
# If they exist, we get a list with one entry per year, and ys is our name for it.
latest = ys[-1]
# [-1] means "the last item in the list". The list is ordered by year, so the last item is the newest year.
# We store it in "latest" because we need last year's numbers later, for example the starting cash.
st.caption("Swiss CO Art. 725: the board must monitor solvency. If insolvency is impending "
           "within 12 months, it must take restructuring measures. Prepare (or review "
           "management's) monthly plan and record the planned measures.")
# Shows a small grey explanation text under the heading, here the legal reason for this page.
# The sentence is split over three lines to keep the code readable.
# Python glues the three pieces together into one sentence.
# Each piece ends with a space inside the quotes, otherwise the words would stick together.


ss = st.session_state
#Streamlis's notebook for one user's visit
#Streamlit re-runs this whole file after every click, so normal variables are forgotten eacht time. 
#Whatever we write into session_state is kept between clicks and between pages. We can store the user's inputs there, and also the results of calculations that take a long time to run.
#"ss" is our nickname for it, so we can write ss.something instead of st.session_state.something.


if ss.liquidity_inputs is None:      # first visit: prefill from the latest year
    # "is None" asks: is the notebook entry still empty? That is only true the first time the user opens this page.
    # So the comment says "first visit". Without this check, we would overwrite the user's input after every click.
    # (this line only works if liquidity_inputs was created as None earlier in the app, probably at star-up.)    
    ss.liquidity_inputs = {"opening_cash": float(latest.cash), "credit_line": 0.0,
                           #plan: a ready-made 12-month table, prefilled from last year's figures by our logic file.
                           "plan": analysis.default_plan(latest),
                           #measures: an empty table where the user can add their restructuring measures. 
                           "measures": analysis.empty_measures()}
    # Now we fill the notebook once with starting values. The curly brackets {} create a dictionary, which is like a list 
    # but each entry has a name (key) and a value.
    # opening_cash is taken from the latest year, credit line is zero, and the plan and measures are created by functions in analysis.py. It starts with the cash from last years balance sheet. 

# "li" is not a copy but a second name for the same dictionary.
# So whenever we later change li ["something"], we are changing the saved notebook entry directly. 
# That is why the user's inputs are stil there after a click or after visiting another page and coming back.
li = ss.liquidity_inputs
# A version number saved in the notebook. We use it inside the widget keys below, so that when the user clicks "next step" and comes back,
#  the widgets are reset to the new values from the notebook instead of showing the old values from the previous visit.
# If another part of the app raises the nubmer (for example a reset), all widgets get new names
# and start fresh with the new values. 
v = ss.editor_version

# Splits the page into two columns for the opening cash and credit line inputs. The user can enter numbers there.
# c1 is the left column, c2 is the right column. The number_input widgets are prefilled with the values from the notebook.
# this puts the two input fields side by side, instead of one below the other.
c1, c2 = st.columns(2)

# Draws a number field in the LEFT Column. Whatever the user types is returned and saved into li["opening_cash"]. 
# The value is prefilled from the notebook, and the user can only enter multiples of 10'000.
#  The key is a unique name for this widget, so Streamlit can remember its value between clicks. 
#  We add the version number to the key so that when the user clicks "next step" and comes back, the widget is reset to the new values from the notebook instead of showing the old values from the previous visit.
# "opening cash balance" is the label above the field.
# value=... what the field shows at the start: the amount stored in li (as a decimal number).
# step=10_000.0 means the user can only enter multiples of 10'000. how much the + and - buttons change the number (the underscore only makes it easier to read). 
# format="%.0f" means the number is shown without decimals.
# key=...   A unique ID for this field. Streamlit needs it to tell widgets apart.
            # The {v} inserts the version number from above into the text. 
li["opening_cash"] = c1.number_input("Opening cash balance", value=float(li["opening_cash"]),
                                     step=10_000.0, format="%.0f", key=f"open_{v}")

# The same thing for the RIGHT column: The credit lines the bank has granted but the company has not used yet.
# It has its own key ("cl_" plus the version) so that it doesn't mix up with the opening cash field. (field above)
# help=... adds a small question mark with the tooltip. It reminds the user to enter only credit lines
# that the bank has committed in writing, because only those count as safe liquidity.
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
# The next section is for the user to enter their restructuring measures. It has a heading and a caption explaining what to do.
# A smaller heading that starts the section for restructuring measures
# (actions the company takes to get out of a liquidity problem, for example selling assets, delaying payments, or raising new capital).
st.subheader("Restructuring measures")

# Small grey help text under the heading: the user enters what each measure bring in cash
# and in which month. Positive numbers mean money comes in, negative numbers mean money goes out. 
# The app will calculate the effect of all measures on the liquidity chart above.
st.caption("Cash effect of each planned measure in the month it is expected (positive = inflow).")

#   The first time the user visits this page, we copy the empty table from the notebook into the base.
# Rows can be added here. One must always start from the same base table,
# otherwise added rows would be applied twice. The base is refreshed whenever
# the editor is shown something new (widget state is removed when leaving the page).
# Streamlit also forgets the table's memory when the user leaves the page, so we store it in the notebook. 
    # and then we take a fresh snapshot of the current data as the new base. 
    # This way, the user can add rows, leave the page and come back, and the table will still show the added rows. 
    # Rows can be added here. the user can always start from the same base table, otherwise added rows would be applied twice.

if f"meas_{v}" not in ss:
    # Then we save a snapshot of the current measures as the new base table. 
    # .copy() makes a separate duplicate, so later changes to li["measures"] don't change the base table.
    ss["measures_base"] = li["measures"].copy()

# Shows the editable table. The user's finished table comes back and is saved into li["measures"]. 
# The table is prefilled from the base table in the notebook. So it is kept when the user clicks around or visits other pages. 
# The user can add or delete rows, and the table will expand or shrink accordingly.
li["measures"] = st.data_editor(

    # We always feed in the BASE table (not li["measures"]) so
    #  that the user can add rows, leave the page and come back, 
    # and the table will still show the added rows.
    # num_rows="dynamic" means the user can add or delete rows.
    #  (we don't know how many measures there will be, so we let the user decide.) 
    # widht="stretch" makes the table fill the page width.
    # hide_index=True removes the row numbers on the left. 
    # key=f"meas_{v}" gives it a unique name so Streamlit can remember its state between clicks.
        # it is the same name we checked for in the if statement above, so that the base table is only created once per visit.

    ss["measures_base"], num_rows="dynamic", hide_index=True, width="stretch", key=f"meas_{v}",
    column_config={
        #The column "Measure" is shown as "Description" and holds free text.
        "Measure": st.column_config.TextColumn("Description"),
        # "Type" becomes a dropdown list. the user can only pick from the list in analysis.MEASURE_TYPES. 
        # The list is defined in logic/analysis.py and contains the types of measures we support.
        # therefore no one can type a type that we don't know how to handle.
        "Type": st.column_config.SelectboxColumn("Type", options=analysis.MEASURE_TYPES),
        # "Month" only accepts whole numbers from 1 to 12, because our plan only covers 12 months. 
        # The user can only + or - the number by 1, and the field is shown as "Month" instead of "Month (1-12)".
        "Month": st.column_config.NumberColumn("Month", min_value=1, max_value=12, step=1),
        # "Amount" is shown as "Cash effect". "localized" means it is shown with the user's local number format (commas or dots).
        # the arrow buttons change the number in steps of 10'000.0. 
        # The user can enter positive or negative numbers, because measures can bring in cash or cost cash.
        "Amount": st.column_config.NumberColumn("Cash effect", format="localized", step=10_000.0),
    })


#The main calculation. We hand over the four inputs (starting cash, credit line, monthly plan, and measures) to the analysis file, 
# which does the maths and returns a dictionary with the results. These results are called "res" and are used in the chart and the traffic lights below.
# "res" contains everything we need for the chart and the traffic lights below.
# Because Streamlit re-runs the page after every change, the results update live.
res = analysis.evaluate_plan(li["opening_cash"], li["credit_line"], li["plan"], li["measures"])


# ---------------------------------------------------------------------------
# Chart: headroom with and without measures
# ---------------------------------------------------------------------------
# Creates an empty chart, like a blank sheet. The next lines draw onto it. 
# We use the "graph_objects" part of plotly,
#  which lets us build a chart piece by piece (bars, lines, labels).
# "go" is the nickname we gave it when we imported it, so we can write go.Figure() instead of plotly.graph_objects.Figure(). (already mentioned at the top of the code).
fig = go.Figure()

# Draws one bar per month: the available liquidity WITHOUT any measures. The bar is red if the headroom is negative, grey otherwise.
# x = the month names (the same list that the table uses). 
# y = the headroom without measures, which we got from the analysis file. So the values from our results.
# name = the label shown in the legend.

fig.add_bar(x=analysis.MONTHS, y=res["headroom_base"], name="Headroom without measures",
            # marker_color sets the colour of every bar. The list is built with a short loop:
            # for every value h in the results, take red if h is below 0 (not enough money),
            # otherwise take grey. The result is a list of colours, one for each bar.
            # the little coloured square next to the code is only VS Code's colour preview, not part of the code. 
            marker_color=[shared.RED_HEX if h < 0 else shared.LINE for h in res["headroom_base"]])

# Draws a line with dots on top of the bars: the availability liquidity WITH the measures.
# Bars against an amber line let the reader see at once whether the measures help. 
fig.add_scatter(x=analysis.MONTHS, y=res["headroom_measures"], name="Headroom with measures",
                mode="lines+markers", line=dict(color=shared.ACCENT, width=3))

# Draws a dark horizonat line at 0. Above it we can pay our bills, below it we are in trouble. The line is dark so it is visible even on the red bars.
fig.add_hline(y=0, line_color=shared.TEXT)

# Layout settings for the whole chart: 
# height 380 pixels, a clean white style, small margins at the top and bottom, 
# a title on the vertical axis that says what the numbers mean, 
# and a horizontal legend below the chart instead of on the right. 
# (y=-0.15 means below the chart, negative numbers are below the bottom edge.)
fig.update_layout(height=380, template="simple_white", margin=dict(t=20, b=20),
                  yaxis_title="Cash + undrawn credit lines", legend=dict(orientation="h", y=-0.15))

# Shows the finished chart on the web page, using the full page width. 
#   One can hover over bars and lines to see the exact numbers, zoom in, or hide one of the two series by clicking its name in the legend.
st.plotly_chart(fig, width="stretch")


# Asks our calculation file for the legal verdict: is insolvency impending within 12 months?
#  It returns a dictionary with the status, the result, and a short explanation.
test = analysis.impending_insolvency(res)


# Creates three boxes side by side for the three traffic lights.
c1, c2, c3 = st.columns(3)

# "with c1." means: whatever we write inside this block will be drawn in the left column.
with c1:
    # Our helper draws a coloured traffic light. We give it the status colour, a title, 
    # the short result and the detail text. The helper formats it nicely and adds a small question mark with the detail text as a tooltip.
    shared.traffic_light(test["status"], "CO Art. 725", test["result"], test["detail"])


# Everything indented below goes into the second box: the runway. 
with c2:
    # Runway = for how many months the available liquidity lasts. We take it from the results.
    runway = res["runway_months"]

    # Green if there is no money going out (runway is None, nothing to calculate)
    # of if the money lasts at least 12 months. Otherwise red.
    # The order matters: if runway is NOne, Python stops after the first part 
    # and never tries to compare None with 12, which would cause an error. 
    shared.traffic_light("green" if runway is None or runway >= 12 else "red", "Runway",
                     "no net outflow" if runway is None else f"{runway:.1f} months",
                     # the small explanation teext under it.
                     "Available liquidity / average monthly net outflow")

# Everything indented below goes into the third box: the lowest point with measures.
with c3:
    # Green if the lowest month WITH measures is still 0 or higher, red if it is below 0.
    #  The user can see at a glance whether the measures are enough to avoid insolvency.
    shared.traffic_light("green" if res["min_headroom_measures"] >= 0 else "red",
                         # Big text: the lowest value. ":,.0f" means thousands separators and no decimals. 
                         # Inside an f-string that uses double quotes we use single quotes for the dictionary key.
                     "Lowest headroom with measures", f"{res['min_headroom_measures']:,.0f}",
                     # Small tet: teh total of all measures.
                     f"Measures total: {res['measures_total']:,.0f}")

# Shows the button that leads to the next page (step 6, bankruptcy model). 
# the first text is the file name of that page, the second is the text on the button. 
# the file name must match the real file name exactly, including spelling, 
# otherwise teh button will not find the page. 

shared.next_step("pages/6_bankruptcy_model.py", "Continue with step 6: Bankruptcy model")