"""
DOCUMENTATION - audit evidence of the going concern procedure.

Sections:
    1. PDF working paper (fpdf2 + matplotlib chart)
    2. Audit files in a SQLite database (save, list, load, delete)
"""

import io
import json
import os
import sqlite3
from datetime import date, datetime

import matplotlib
import pandas as pd
from fpdf import FPDF

matplotlib.use("Agg")  # render charts without a screen
import matplotlib.pyplot as plt  # noqa: E402  (must come after matplotlib.use)

from logic import analysis
from logic.data_input import KEYS
from logic.ml_model import ROOT


# ============================================================================
# PDF export: documentation of the going concern audit procedure (working paper).
#
# Built with fpdf2. The built-in PDF fonts only support Latin-1 characters, so
# all text passes through _t() which replaces unsupported characters.
# ============================================================================

COLOURS = {"green": (46, 158, 107), "amber": (242, 182, 50), "red": (214, 69, 69),
           "grey": (160, 160, 160)}
INK = (30, 43, 51)


def _t(text):
    """Make text safe for the Latin-1 PDF core fonts."""
    repl = {"–": "-", "—": "-", "≤": "<=", "≥": ">=", "’": "'", "‘": "'", "“": '"', "”": '"',
            "…": "...", "→": "->", "•": "-", "×": "x"}
    text = str(text)
    for a, b in repl.items():
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


class Report(FPDF):
   
    def footer(self):
        """Footer on every page: note on the left, page number on the right."""
        self.set_y(-12)                       # 12 mm above the bottom edge
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 6, _t("Going Concern Audit - confidential"), align="L")
        self.cell(0, 6, f"Page {self.page_no()}/{{nb}}", align="R")

    def h1(self, text):
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(*INK)
        self.multi_cell(0, 9, _t(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def h2(self, text):
        self.ln(3)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*INK)
        self.cell(0, 8, _t(text), new_x="LMARGIN", new_y="NEXT")

    def para(self, text, size=10, bold=False):
        self.set_font("Helvetica", "B" if bold else "", size)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5, _t(text), new_x="LMARGIN", new_y="NEXT")

    def dot(self, status, x=None, y=None, d=3.2):
        x = self.get_x() + 1 if x is None else x
        y = self.get_y() + 1.4 if y is None else y
        self.set_fill_color(*COLOURS.get(status, COLOURS["grey"]))
        self.ellipse(x, y, d, d, style="F")

    def row(self, cells, widths, status=None, bold=False, fill=False):
        """One table row; optional traffic-light dot in front."""
        self.set_font("Helvetica", "B" if bold else "", 9)
        self.set_text_color(40, 40, 40)
        if fill:
            self.set_fill_color(238, 242, 244)
        if status:
            self.dot(status)
        self.set_x(self.l_margin + 6)
        for text, w in zip(cells, widths):
            self.cell(w, 6, _t(text), fill=fill)
        self.ln(6)


def _trend_chart(years):
    """Small line chart of key ratios for the PDF (PNG in memory)."""
    keys = ["current_ratio", "quick_ratio", "equity_ratio", "roa"]
    fig, ax = plt.subplots(figsize=(7, 2.8), dpi=150)
    labels = [fy.year for fy in years]
    for k in keys:
        r = analysis.RATIO_BY_KEY[k]
        ax.plot(labels, [r.value(fy) for fy in years], marker="o", label=r.name)
    ax.axhline(0, color="#999999", lw=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=7, frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.15))
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def build_pdf(engagement, years, result, legal_tests, liquidity_result, ml_info, conclusion,
              profile=None):
    pdf = Report()
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()

    # --- Cover information --------------------------------------------------------
    pdf.h1(f"Going concern assessment: {engagement.get('client') or 'Unnamed client'}")
    pdf.para(f"Financial year: {engagement.get('fiscal_year') or years[-1].year}    "
             f"Auditor: {engagement.get('auditor') or '-'}    Date: {date.today():%d.%m.%Y}")
    pdf.para(f"Years analysed: {', '.join(fy.year for fy in years)}    "
             f"Framework: {(profile or {}).get('audit_type', 'ISA 570 / PS-CH 570')}, "
             "Swiss CO Art. 725-725b", size=9)

    # --- Company profile ------------------------------------------------------------
    if profile:
        pdf.h2("Company profile")
        group = ("Group company, support letter " + ("available" if profile["support_letter"] else "NOT available")
                 if profile["group"] else "Independent company")
        pdf.para(f"{profile['legal_form']} | Industry: {profile['industry']} | Canton: {profile['canton']} | "
                 f"Founded: {profile['founded']} | Employees: {profile['employees']} | "
                 f"Listed: {'yes' if profile['listed'] else 'no'} | {group}", size=9)
        for label, key in [("Business model", "description"), ("Key risks", "key_risks"),
                           ("Auditor's notes", "notes")]:
            if profile.get(key):
                pdf.para(f"{label}: {profile[key]}", size=9)

    # --- Result -----------------------------------------------------------------
    pdf.h2("1. Overall assessment")
    pdf.dot(result["colour"], x=pdf.l_margin, y=pdf.get_y() + 1.5, d=4)
    pdf.set_x(pdf.l_margin + 7)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, _t(f"Going concern risk: {result['level']} ({result['score']:.0%})"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.para(result["text"])
    p, w = result["parts"], result["weights"]
    pdf.para(f"Components: ratios {p['quantitative']:.0%} (weight {w['quantitative']:.0%}), "
             f"questionnaire {p['qualitative']:.0%} (weight {w['qualitative']:.0%}), "
             f"ML model {p['ml']:.0%} (weight {w['ml']:.0%})", size=9)
    if result["knock_outs"]:
        pdf.para("Knock-out criteria triggered:", bold=True)
        for k in result["knock_outs"]:
            pdf.para(f"- {k}", size=9)

    # --- Auditor's conclusion -------------------------------------------------------
    pdf.h2("2. Auditor's conclusion (ISA 570.17-23)")
    if conclusion:
        pdf.para(f"Going concern basis appropriate: {'Yes' if conclusion['basis'] else 'No'}    "
                 f"Material uncertainty: {'Yes' if conclusion['uncertainty'] else 'No'}    "
                 f"Adequately disclosed: {'Yes' if conclusion['disclosed'] else 'No'}", size=9)
        pdf.para(f"Implication for the auditor's report: {conclusion['opinion']}", bold=True)
        pdf.para(conclusion["reason"], size=9)
        if conclusion.get("comment"):
            pdf.para(f"Auditor's comment: {conclusion['comment']}", size=9)
    else:
        pdf.para("Not yet recorded by the auditor.")

    # --- Legal tests ---------------------------------------------------------------
    pdf.h2("3. Legal thresholds (Swiss CO)")
    for t in legal_tests:
        pdf.row([t["test"], t["result"]], [70, 110], status=t["status"], bold=True)
        pdf.set_x(pdf.l_margin + 6)
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
    for source, text in result["signals"] or [("-", "No warning signals")]:
        pdf.para(f"- {source}: {text}", size=9)

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
