"""
DOCUMENTATION - audit evidence of the going concern procedure.

Sections:
    1. PDF working paper (fpdf2 + matplotlib chart)
    2. Audit files in a SQLite database (save, list, load, delete)
"""

import io                               # treats data in memory like a file (chart image for PDF, JSON for database)
import json                             # converts Python data into JSON text and back (to store data in database)
import os                               # works with folders and file paths (location of database file)
import sqlite3                          # file-based database that is part of Python (saved audit files)
from datetime import date, datetime     # today's date for the pdf, date and time when an audit file is saved

import matplotlib                       # external library for charts (trend chart in pdf)
import pandas as pd                     # external library for tables (financial statements, liquidity plan)
from fpdf import FPDF                   # external library that creates pdf document
from fpdf.fonts import FontFace         # describes a font style (bold, size, color) for pdf tables

matplotlib.use("Agg")                   # render charts without a screen (only as an image, no window opens)
import matplotlib.pyplot as plt         # noqa: E402  (must come after matplotlib.use) -> drawing functions for charts

from logic import analysis              # our own file: ratios and legal tests (shown in the pdf)
from logic.data_input import KEYS       # our own file: list of standard line items (to load saved tables)
from logic.ml_model import ROOT         # our own file: path of project folder (to find the data folder)


# ============================================================================
# PDF EXPORT - the working paper that documents the whole audit procedure
#
# The PDF is the output of all steps of the website (company profile, ratios,
# questionnaire, liquidity plan, ML model, conclusion). It is built in 3 parts:
#   1. class Report   -> design building blocks (footer, headings, paragraph,
#                        traffic-light dot, table row), like style templates in Word
#   2. _trend_chart() -> draws the line chart of the key ratios as an image
#   3. build_pdf()    -> writes the report section by section (cover, profile,
#                        sections 1-8) and returns the finished PDF for the download
#
# the pdf is built with fpdf2 which means that the built-in pdf fonts only support Latin-1 characters, so all text passes through -t() which replaces unsupported characters
# in fpdf2 the page is also filled from top to bottom like a typewriter;
# sizes are in mm (usable page width = 180 mm); colours are RGB values (0-255).
# ============================================================================


# Here we define the traffic-light colors, which will be used for the illustrations of the ratios and their status (green = good, amber (yellow) = inbetween, red = bad)
# Traffic-light colours as RGB values (red, green, blue, each 0-255)
COLOURS = {"green": (46, 158, 107), "amber": (242, 182, 50), "red": (214, 69, 69),
           "grey": (160, 160, 160)}
# dark main colour for headings
INK = (30, 43, 51)


def _t(text):
    """Make text safe for the Latin-1 PDF core fonts."""
    # the built.in pdf fonts don't know some special characters -> hence we replace them:
    repl = {"–": "-", "—": "-", "≤": "<=", "≥": ">=", "’": "'", "‘": "'", "“": '"', "”": '"',
            "…": "...", "→": "->", "•": "-", "×": "x"}
    text = str(text)                                     # make sure we have text (also if a number is passed)
    for a, b in repl.items():                            # go through every pair (special character, replacement)  
        text = text.replace(a, b)                        # replace special character in the text, any other unknown character becomes "?" instead of crashing the pdf export.
    return text.encode("latin-1", "replace").decode("latin-1")

# Here we define the different components of the pdf report, which is the output of the audited work done in all the steps of the website
# First we need to define the classes. A class is like a blueprint for objects: it defines which data an object holds and which functions (called "methods") it can perform
# Advantage of this: the design is defined once, in build_pdf we then simply write pdf.h2 ("...") instead of repeating font, size and color everytime
# "self" means the pdf object itsself, e.g. self.set_font(...) changes the font of exactly this pdf

class Report(FPDF):
# "class Report(FPDF)" means that the Report takes over everything from the existing class FPDF or the fpdf2 library (creating pages, writing text, drawing shapes, saving the PDF)
# therefore we add our methods for the design of our working paper

# our methods:
    def footer(self):
        """Footer on every page of the pdf report: note on the left, page number on the right."""
        #fodf2 calls this function automatically at the bottom of every page
        self.set_y(-12)                                                          # 12 mm above the bottom edge
        self.set_font("Helvetica", "I", 8)                                       # Font: Helvetica, italic, size 8
        self.set_text_color(130, 130, 130)                                       # colour of the text: grey
        self.cell(0, 6, _t("Going Concern Audit - confidential"), align="L")     # note on the left 
        self.cell(0, 6, f"Page {self.page_no()}/{{nb}}", align="R")              # Page-Number (e.g. 1/3) on the right, ({nb} = total pages)

    def h1(self, text):
        # Main title of the pdf (large & bold)
        self.set_font("Helvetica", "B", 18)                                 # Font: Helvetica, bold, size 18
        self.set_text_color(*INK)                                           # dark main color (* unpacks the three RGB numbers)
        self.multi_cell(0, 9, _t(text), new_x="LMARGIN", new_y="NEXT")      # text may wrap, then the next line
        self.ln(1)                                                          # 1 mm space below

    def h2(self, text):
        # Section heading, e.g. "3 . Legal thresholds"
        self.ln(3)                                                          # 3 mm space above the section
        self.set_font("Helvetica", "B", 12)                                 # Font: Helvetica, bold, size 12
        self.set_text_color(*INK)                                       
        self.cell(0, 8, _t(text), new_x="LMARGIN", new_y="NEXT")            # one line, then next line

    def para(self, text, size=10, bold=False):
        # Normal paragraph, long text wraps automatically 
        self.set_font("Helvetica", "B" if bold else "", size)               # Font: Helvetica, font is bold only if requested, otherwise normal text, size is 10 (as defined in the line above)
        self.set_text_color(40, 40, 40)                                     # almost black
        self.multi_cell(0, 5, _t(text), new_x="LMARGIN", new_y="NEXT")      # width 0 = full page width 

    def dot(self, status, x=None, y=None, d=3.2): 
        # colored traffic-light dot with diameter d (mm) gets defined in the colors defined above (green, amber, red, grey)                       
        x = self.get_x() + 1 if x is None else x                            # no position given -> at the current cursor
        y = self.get_y() + 1.4 if y is None else y                          # (+1.4 mm gets added so that the dot is centered on the text line)
        self.set_fill_color(*COLOURS.get(status, COLOURS["grey"]))          # color of status, shows in grey if the status is unkown
        self.ellipse(x, y, d, d, style="F")                                 # draw a filled circle ("F" = circle is filled)

    def row(self, cells, widths, status=None, bold=False, fill=False):
        """One table row; optional traffic-light dot in front."""
        self.set_font("Helvetica", "B" if bold else "", 9)                  # Font: same logic as above
        self.set_text_color(40, 40, 40)                                     # same logic as above
        if fill:                               
            self.set_fill_color(238, 242, 244)                              # grey background (e.g. header row)
        if status:                                                          # is traffic-light dot requested?
            self.dot(status)
        self.set_x(self.l_margin + 6)                                       # start the text 6mm right of the margin (so that we have room for the dot)
        for text, w in zip(cells, widths):                                  # zip pairs each text with its column width
            self.cell(w, 6, _t(text), fill=fill)                            # one cell: width w, height 6 mm
        self.ln(6)                                                          # go to the next row

def _trend_chart(years):
    # Small line chart of key ratios for the PDF (PNG image in memory)
    # Input: years = list of FinancialYear (oldest first)
    # Output: the chart as PNG image.

    # The four ratios shown in the chart (internal names from analysis.py):
    # current ratio, quick ratio, equity ratio, return on assets (ROA)
    keys = ["current_ratio", "quick_ratio", "equity_ratio", "roa"]

    # Create an empty chart. matplotlib always returns two objects:
    #   fig = the whole picture (like the sheet of paper)
    #   ax  = the drawing area with the axes, where the lines are drawn
    # figsize = size in inches (7 x 2.8 = wide and flat, fits the PDF width)
    # dpi     = dots per inch = sharpness of the image (150 = sharp when printed)
    fig, ax = plt.subplots(figsize=(7, 2.8), dpi=150)

    # Labels of the x-axis: the years, e.g. ["2021", "2022", "2023", "2024", "2025"]
    labels = [fy.year for fy in years]

    # Draw one line per ratio
    for k in keys:
        # Get the definition of the ratio (name, formula, unit) from analysis.py
        r = analysis.RATIO_BY_KEY[k]
        # Calculate the ratio for every year with r.value(fy) and draw the line:
        #   x-values = years, y-values = ratio values,
        #   marker="o" = a dot on each year, label = name shown in the legend
        ax.plot(labels, [r.value(fy) for fy in years], marker="o", label=r.name)

    # Thin grey horizontal line at 0: shows at a glance when a ratio turns negative
    # (lw = line width)
    ax.axhline(0, color="#999999", lw=0.8)

    # "Spines" are the frame lines around the chart. Hide the top and right ones
    # (set_visible(False)) for a cleaner, modern look.
    ax.spines[["top", "right"]].set_visible(False)

    # Legend (which colour = which ratio):
    #   fontsize=7            small text
    #   frameon=False         no box around the legend
    #   ncol=4                all four entries side by side in one row
    #   loc="upper center"    anchored at its top centre ...
    #   bbox_to_anchor=(0.5, 1.15)  ... placed horizontally in the middle (0.5) and
    #                               slightly ABOVE the chart (1.15 = 15 % above the top),
    #                               so it does not cover the lines
    ax.legend(fontsize=7, frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.15))

    # Smaller numbers on the axes (size 8)
    ax.tick_params(labelsize=8)

    # Adjust the spacing automatically so that no labels are cut off or overlap
    fig.tight_layout()

    # Save the chart as an image WITHOUT creating a file on the computer:
    buf = io.BytesIO()                  # empty "file" in memory (buffer)
    fig.savefig(buf, format="png")      # write the chart as PNG image into this buffer
    plt.close(fig)                      # close the chart to free memory (important on a server)
    buf.seek(0)                         # move back to the start of the buffer, so it can be read from the beginning
    return buf                          # return the image; build_pdf() inserts it with pdf.image(...)

def build_pdf(engagement, years, result, legal_tests, liquidity_result, ml_info, conclusion,
              profile=None):
    # Creates the PDF working paper and returns it as bytes (for the download button on page 7).

    #All inputs are prepared on page 7 'Assessment & report' and passed to this function:
        #engagement        dictionary: client name, financial year, auditor        (page 1)
       # years             list of FinancialYear objects, oldest first            (page 2)
        #result            overall assessment: score, risk level, colour, warning signals and questionnaire result  (page 7)
        #legal_tests       results of the legal tests CO Art. 725, 725a, 725b      (page 3)
        #liquidity_result  result of the 12-month liquidity plan, or None if the plan was not prepared   (page 5)
        #ml_info           ML risk score and model figures, or None if the model is not trained        (page 6)
        #conclusion        auditor's conclusion (yes/no answers, opinion, comment), or an empty dictionary if not recorded yet (page 7)
        #profile           company profile (industry, legal form, ...), optional  (page 1) "=None" means: this input may be left out
   
    # Create a new, empty PDF from our class Report (with our own design building blocks)
    pdf = Report()

    # Automatic page break: when the text reaches 15 mm above the bottom edge,
    # fpdf2 starts a new page by itself (True = switched on, margin = distance in mm).
    # This also leaves room for the footer.
    pdf.set_auto_page_break(True, margin=15)

    # Add the first page; from here on the content is written from top to bottom
    pdf.add_page()


    # --- Cover information --------------------------------------------------------
    # First lines of the PDF: title, client, year, auditor, date, years and framework.

    # Main title with the client name.
    # engagement.get('client') reads the client name from page 1;"or 'Unnamed client'" is used if no name was entered (empty text).
    pdf.h1(f"Going concern assessment: {engagement.get('client') or 'Unnamed client'}")

    # Line with financial year, auditor and today's date:
    #   - financial year from page 1; if empty, the latest year of the figures (years[-1] = last in the list)
    #   - auditor from page 1; if empty, a dash "-"
    #   - date.today():%d.%m.%Y = today's date in Swiss format, e.g. 15.11.2026
    # The spaces inside the text create some distance between the three pieces of information.
    pdf.para(f"Financial year: {engagement.get('fiscal_year') or years[-1].year}    "
             f"Auditor: {engagement.get('auditor') or '-'}    Date: {date.today():%d.%m.%Y}")

    # Smaller line (size 9) with the analysed years and the audit framework:
    #   - ', '.join(...) lists all years separated by commas, e.g. "2021, 2022, 2023"
    #   - (profile or {}) uses an empty dictionary if no profile exists, so .get() still works;
    #     .get('audit_type', 'ISA 570 / PS-CH 570') reads the audit type chosen on page 1,
    #     or uses ISA 570 as default if none was chosen
    #   - Swiss CO Art. 725-725b = the legal basis (capital loss, over-indebtedness, insolvency)
    pdf.para(f"Years analysed: {', '.join(fy.year for fy in years)}    "
             f"Framework: {(profile or {}).get('audit_type', 'ISA 570 / PS-CH 570')}, "
             "Swiss CO Art. 725-725b", size=9)

    # --- Company profile ------------------------------------------------------------
    # now we section with the master data entered on page 1 (company profile).
    # "if profile:" means it only print this section if a profile exists (not None / not empty).
    if profile:
        pdf.h2("Company profile")                  # section heading

        # Text about the group structure, depending on two switches on page 1:
        #   - part of a group AND support letter  -> "Group company, support letter available"
        #   - part of a group, NO support letter  -> "Group company, support letter NOT available"
        #   - not part of a group                 -> "Independent company"
        # ("A if condition else B" = short form of if/else in one line)
        group = ("Group company, support letter " + ("available" if profile["support_letter"] else "NOT available")
                 if profile["group"] else "Independent company")

        # One line (size 9) with all master data, separated by " | ":
        # legal form, industry, canton, year founded, employees, listed (yes/no), group text
        # profile['...'] reads the value of each field from the profile dictionary
        pdf.para(f"{profile['legal_form']} | Industry: {profile['industry']} | Canton: {profile['canton']} | "
                 f"Founded: {profile['founded']} | Employees: {profile['employees']} | "
                 f"Listed: {'yes' if profile['listed'] else 'no'} | {group}", size=9)

        # The three free texts from page 1 (business understanding).
        # The list contains pairs: (title printed in the PDF, field name in the profile).
        # The loop goes through the three pairs one after the other.
        for label, key in [("Business model", "description"), ("Key risks", "key_risks"),
                           ("Auditor's notes", "notes")]:
            if profile.get(key):                   # only print the text if the user filled it in (not empty)
                pdf.para(f"{label}: {profile[key]}", size=9)   # e.g. "Key risks: Dependence on two customers"

    # --- Result -----------------------------------------------------------------
    # in Section 1 we have the overall going concern risk, i.e. the main result of the whole app.
    pdf.h2("1. Overall assessment")

    # we put the Traffic-light dot (green / amber / red) in front of the result:
    #   x = pdf.l_margin            -> at the left margin of the page
    #   y = pdf.get_y() + 1.5       -> current height + 1.5 mm, so the dot is centred on the text line
    #   d = 4                       -> diameter 4 mm (slightly larger than the dots in the tables)
    pdf.dot(result["colour"], x=pdf.l_margin, y=pdf.get_y() + 1.5, d=4)

    # Move the cursor 7 mm to the right, so the text starts next to the dot (not on top of it)
    pdf.set_x(pdf.l_margin + 7)

    # we write the Result line in bold, size 12, e.g. "Going concern risk: High (74%)"
    #   result['level'] = Low / Medium / High
    #   result['score'] = score between 0 and 1; :.0% shows it as percentage without decimals (0.74 -> 74%)
    #   .cell(0, 7, ...) = one line, full width (0), height 7 mm; then jump to the next line
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, _t(f"Going concern risk: {result['level']} ({result['score']:.0%})"),
             new_x="LMARGIN", new_y="NEXT")

    # Explanation of the risk level with the next audit steps according to ISA 570
    pdf.para(result["text"])

    # How the score was calculated: the three components and their weights
    #   p = scores of the components (parts), w = weights set with the sliders on page 7
    #   (two variables are filled in one line: p gets result["parts"], w gets result["weights"])
    p, w = result["parts"], result["weights"]
    pdf.para(f"Components: ratios {p['quantitative']:.0%} (weight {w['quantitative']:.0%}), "
             f"questionnaire {p['qualitative']:.0%} (weight {w['qualitative']:.0%}), "
             f"ML model {p['ml']:.0%} (weight {w['ml']:.0%})", size=9)

    # Now we move on to the Knock-out criteria (e.g. over-indebtedness, liquidity shortfall, KO questions):
    # they set the risk to "High" regardless of their calculated score.
    # this is only printed if at least one knock-out was triggered (list not empty)
    if result["knock_outs"]:
        pdf.para("Knock-out criteria triggered:", bold=True) # bold heading line with text "Knock-out criteria triggered"
        for k in result["knock_outs"]:                       # one line per knock-out criterion
            pdf.para(f"- {k}", size=9)                       # as a list with "-" in front


    # --- Auditor's conclusion -------------------------------------------------------
    # Section 2: the auditor's own conclusion (professional judgement, ISA 570.17-23).
    # The app only proposes a risk level; the auditor decides and records the conclusion on page 7. The following section documents that auditor-decision.
    pdf.h2("2. Auditor's conclusion (ISA 570.17-23)")

    # "if conclusion:" = only if the auditor has already recorded a conclusion,(the dictionary is not empty)
    if conclusion:
        # The three answers of the decision tree, converted from True/False into Yes/No:
        #   basis       -> is the going concern basis of accounting appropriate?
        #   uncertainty -> does a material uncertainty exist?
        #   disclosed   -> is it adequately disclosed in the notes?
        pdf.para(f"Going concern basis appropriate: {'Yes' if conclusion['basis'] else 'No'}    "
                 f"Material uncertainty: {'Yes' if conclusion['uncertainty'] else 'No'}    "
                 f"Adequately disclosed: {'Yes' if conclusion['disclosed'] else 'No'}", size=9)

        # Resulting type of audit opinion (in bold), e.g. "Unmodified opinion with a
        # 'Material Uncertainty Related to Going Concern' section"
        pdf.para(f"Implication for the auditor's report: {conclusion['opinion']}", bold=True)

        # Reason with the ISA reference, e.g. "Material uncertainty adequately disclosed (ISA 570.22)."
        pdf.para(conclusion["reason"], size=9)

        # Optional free-text comment of the auditor, it only gets printed if one was entered
        if conclusion.get("comment"):
            pdf.para(f"Auditor's comment: {conclusion['comment']}", size=9)
    else:
        # No conclusion recorded yet -> say so explicitly as it is important for the audit trail
        pdf.para("Not yet recorded by the auditor.")

    # --- Legal tests ---------------------------------------------------------------
    # Section 3: the legal thresholds of the Swiss Code of Obligations: capital loss (CO Art. 725a), over-indebtedness (CO Art. 725b), impending insolvency (CO Art. 725)
    pdf.h2("3. Legal thresholds (Swiss CO)")

    # legal_tests is a list with one dictionary per test, e.g. {"test": "Capital loss (CO Art. 725a)", "result": "Capital loss", "status": "amber", "detail": "Net assets 1,420,000 vs. limit 1,450,000 ..."}
    for t in legal_tests:
        # Table row in bold: name of the test (70 mm wide) and result (110 mm wide),
        # with a traffic-light dot in front (status = green / amber / red / grey)
        pdf.row([t["test"], t["result"]], [70, 110], status=t["status"], bold=True)
        # Indent the next line by 6 mm, so the detail starts under the text (not under the dot)
        pdf.set_x(pdf.l_margin + 6)
        # Small line (size 8) with the calculation behind the result, as audit evidence
        pdf.para(t["detail"], size=8)


    # --- Ratios ------------------------------------------------------------------
    pdf.h2("4. Financial ratios")
    show = years[-3:]
    widths = [58] + [25] * len(show) + [30]
    pdf.row(["Ratio", *[fy.year for fy in show], "Trend"], widths, bold=True, fill=True)
    for r in analysis.RATIOS:
        pdf.row([r.name, *[analysis.display(r, fy) for fy in show], analysis.trend(r.key, years)],
                widths, status=r.status(years[-1]))
    pdf.para(f"Traffic light refers to the latest year, thresholds for the industry "
             f"'{years[-1].industry}' (rules of thumb, subject to the auditor's judgement).", size=8)
    if len(years) >= 2:
        pdf.image(_trend_chart(years), w=180)
    if not years[-1].has_cash_flow_statement:
        pdf.para("No cash flow statement available: operating cash flow approximated as "
                 "net income + depreciation.", size=8)

    # --- Questionnaire --------------------------------------------------------------
    q = result["questionnaire"]
    pdf.h2("5. ISA 570 questionnaire")
    pdf.para(f"Risk indicators answered 'Yes': {len(q['yes'])} - qualitative score "
             f"{q['score']:.0%} ({q['points']} of {q['max_points']} points)")
    for item in q["yes"]:
        pdf.para(f"- [{item.id}] {item.text} ({item.reference})", size=9)

    # --- Liquidity plan -------------------------------------------------------------
    pdf.h2("6. 12-month liquidity plan (CO Art. 725)")
    if liquidity_result:
        lr = liquidity_result
        pdf.para(f"Lowest headroom without measures: {lr['min_headroom_base']:,.0f}; "
                 f"with measures: {lr['min_headroom_measures']:,.0f}")
        pdf.para("First shortfall without measures: "
                 f"{'month ' + str(lr['first_shortfall_base']) if lr['first_shortfall_base'] else 'none'}; "
                 "with measures: "
                 f"{'month ' + str(lr['first_shortfall_measures']) if lr['first_shortfall_measures'] else 'none'}")
        if lr["runway_months"]:
            pdf.para(f"Runway at the average monthly outflow: {lr['runway_months']:.1f} months")
    else:
        pdf.para("Liquidity plan not prepared.")

    # --- ML -------------------------------------------------------------------------
    pdf.h2("7. Bankruptcy prediction model")
    if ml_info:
        pdf.para(f"Model risk score: {ml_info['score']:.0%} (logistic regression trained on "
                 f"{ml_info['n']:,} Polish companies, ROC-AUC {ml_info['auc']:.2f}). "
                 "The score is a statistical indicator, not a probability for this client.")
    else:
        pdf.para("Model not available.")

    # --- Warning signals -----------------------------------------------------------
    pdf.h2("8. All warning signals")
    # Sort by category so that all signals of one category stand together
    order = ["Ratio", "Legal", "Questionnaire", "Profile"]
    signals = sorted(result["signals"], key=lambda s: order.index(s[0]) if s[0] in order else len(order))
    signals = signals or [("-", "No warning signals")]
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(40, 40, 40)
    pdf.set_draw_color(220, 226, 230)                   # light grey lines
    pdf.set_fill_color(255, 255, 255)                   # white cells (reset from the dots)
    with pdf.table(col_widths=(35, 145), line_height=5.5, text_align="LEFT",
                   borders_layout="HORIZONTAL_LINES", cell_fill_mode="NONE",
                   headings_style=FontFace(emphasis="BOLD", fill_color=(238, 242, 244))) as table:
        table.row(["Category", "Warning signal"])       # header row
        previous = None
        for source, text in signals:
            # Show the category only in the first row of each group (Ratio, Legal, ...)
            table.row([_t(source) if source != previous else "", _t(text)])
            previous = source
            
    pdf.ln(4)
    pdf.para("This working paper was prepared with the Going Concern Audit app. The app supports "
                "the auditor; the conclusion is the auditor's professional judgement (ISA 570).", size=8)
    return bytes(pdf.output())


# ============================================================================
# SQLite database for audit files ("engagements").
#
# Every assessment can be saved as an audit file and loaded again later, e.g.
# to compare the client with last year's audit. SQLite is a file-based database
# management system that is part of Python - no server is needed.
# ============================================================================

DB_PATH = os.path.join(ROOT, "data", "audit_files.db")


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS engagements (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            client        TEXT NOT NULL,
            fiscal_year   TEXT,
            auditor       TEXT,
            saved_at      TEXT NOT NULL,
            risk_level    TEXT,
            risk_score    REAL,
            financials    TEXT,   -- input table as JSON
            answers       TEXT,   -- questionnaire answers as JSON
            liquidity     TEXT,   -- liquidity plan as JSON
            conclusion    TEXT,   -- auditor's conclusion as JSON
            profile       TEXT    -- company profile as JSON
        )""")
    # Migration: databases created before the profile existed get the new column
    cols = [row[1] for row in con.execute("PRAGMA table_info(engagements)")]
    if "profile" not in cols:
        con.execute("ALTER TABLE engagements ADD COLUMN profile TEXT")
    return con


def save_audit_file(state):
    """Saves the current engagement and returns its id."""
    liq = state.get("liquidity_inputs")
    with _connect() as con:
        cur = con.execute(
            """INSERT INTO engagements (client, fiscal_year, auditor, saved_at, risk_level,
               risk_score, financials, answers, liquidity, conclusion, profile)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (state["engagement"]["client"] or "Unnamed client",
             state["engagement"]["fiscal_year"], state["engagement"]["auditor"],
             datetime.now().isoformat(timespec="seconds"),
             state.get("result", {}).get("level"), state.get("result", {}).get("score"),
             state["financials"].to_json(),
             json.dumps(state.get("answers", {})),
             json.dumps({"opening_cash": liq["opening_cash"], "credit_line": liq["credit_line"],
                         "plan": liq["plan"].to_json(), "measures": liq["measures"].to_json()})
             if liq else None,
             json.dumps(state.get("conclusion", {})),
             json.dumps(state.get("profile", {}))))
        return cur.lastrowid


def list_audit_files():
    with _connect() as con:
        return pd.read_sql_query(
            "SELECT id, client, json_extract(profile, '$.industry') AS industry, fiscal_year, "
            "auditor, saved_at, risk_level, risk_score "
            "FROM engagements ORDER BY saved_at DESC", con)


def load_audit_file(engagement_id):
    """Returns the saved engagement as a dict ready for st.session_state."""
    with _connect() as con:
        row = con.execute("SELECT client, fiscal_year, auditor, financials, answers, liquidity, "
                          "conclusion, profile FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    if row is None:
        raise KeyError(engagement_id)
    client, fy, auditor, fin, answers, liq, concl, prof = row
    financials = pd.read_json(io_str(fin), convert_axes=False).reindex(KEYS)
    financials.index.name = "item"
    financials.columns = [str(c) for c in financials.columns]
    out = {"engagement": {"client": client, "fiscal_year": fy, "auditor": auditor},
           "financials": financials, "answers": json.loads(answers or "{}"),
           "conclusion": json.loads(concl or "{}"), "profile": json.loads(prof or "{}")}
    if liq:
        d = json.loads(liq)
        measures = pd.read_json(io_str(d["measures"]), convert_axes=False)
        if measures.empty:                      # keep the column structure
            measures = analysis.empty_measures()
        out["liquidity_inputs"] = {"opening_cash": d["opening_cash"], "credit_line": d["credit_line"],
                                   "plan": pd.read_json(io_str(d["plan"]), convert_axes=False), "measures": measures}
    return out


def delete_audit_file(engagement_id):
    with _connect() as con:
        con.execute("DELETE FROM engagements WHERE id = ?", (engagement_id,))


def io_str(text):
    """pandas >= 2.1 expects a file-like object instead of a literal JSON string."""
    return io.StringIO(text)
