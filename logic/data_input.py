"""
DATA INPUT - everything that describes the client and its financial statements.

Sections:
    1. Standard format of the financial statements (line items, FinancialYear)
    2. Company profile (industry thresholds, audit type check CO Art. 727)
    3. Sample companies for testing and the demo
    4. AI import with the Claude API (any annual report -> standard format)
"""

import base64
import io
import json
import math
from dataclasses import dataclass
from datetime import date

import pandas as pd


# ============================================================================
# Standardised financial statement format.
#
# Every uploaded annual report - whatever its layout or accounting standard
# (Swiss CO, Swiss GAAP FER, IFRS, ...) - is mapped onto the line items below.
# All ratios, the questionnaire logic and the ML model work with this format only.
# ============================================================================

# ---------------------------------------------------------------------------
# Standard line items: key -> (label shown in the app, statement)
# ---------------------------------------------------------------------------
LINE_ITEMS = {
    # Balance sheet - assets
    "cash": ("Cash and cash equivalents", "Balance sheet"),
    "receivables": ("Short-term receivables", "Balance sheet"),
    "inventories": ("Inventories", "Balance sheet"),
    "other_current_assets": ("Other current assets", "Balance sheet"),
    "non_current_assets": ("Non-current assets", "Balance sheet"),
    # Balance sheet - liabilities
    "st_interest_debt": ("Short-term interest-bearing liabilities", "Balance sheet"),
    "other_current_liabilities": ("Trade payables and other short-term liabilities", "Balance sheet"),
    "lt_interest_debt": ("Long-term interest-bearing liabilities", "Balance sheet"),
    "other_non_current_liabilities": ("Other long-term liabilities and provisions", "Balance sheet"),
    # Balance sheet - equity (split as required by Swiss CO Art. 725a)
    "share_capital": ("Share capital", "Balance sheet"),
    "legal_capital_reserves": ("Legal capital reserves", "Balance sheet"),
    "legal_retained_earnings": ("Legal retained earnings", "Balance sheet"),
    "other_equity": ("Voluntary reserves, retained earnings / losses", "Balance sheet"),
    # Income statement
    "revenue": ("Revenue", "Income statement"),
    "depreciation": ("Depreciation and amortisation", "Income statement"),
    "ebit": ("EBIT (operating result)", "Income statement"),
    "interest_expense": ("Interest expense", "Income statement"),
    "net_income": ("Net income / loss", "Income statement"),
    # Cash flow statement (optional: small companies often do not prepare one)
    "operating_cash_flow": ("Operating cash flow", "Cash flow statement"),
}
KEYS = list(LINE_ITEMS)
LABELS = {k: v[0] for k, v in LINE_ITEMS.items()}
MAX_YEARS = 5


def empty_table(years):
    """Empty input table: rows = line items, columns = years (oldest left)."""
    df = pd.DataFrame({str(y): [float("nan")] * len(KEYS) for y in years}, index=KEYS)
    df.index.name = "item"
    return df


def _num(value):
    """Convert a table cell to float; empty cells count as 0."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(v) else v


@dataclass
class FinancialYear:
    """One financial year in the standard format, with derived totals."""

    year: str
    values: dict
    industry: str = "General"     # selects the traffic-light thresholds

    def __getattr__(self, name):
        # Allows fy.cash, fy.revenue, ... instead of fy.values["cash"]
        if name in LINE_ITEMS:
            return _num(self.values.get(name))
        raise AttributeError(name)

    # -- Derived totals -----------------------------------------------------
    @property
    def current_assets(self):
        return self.cash + self.receivables + self.inventories + self.other_current_assets

    @property
    def total_assets(self):
        return self.current_assets + self.non_current_assets

    @property
    def current_liabilities(self):
        return self.st_interest_debt + self.other_current_liabilities

    @property
    def total_liabilities(self):
        return (self.current_liabilities + self.lt_interest_debt
                + self.other_non_current_liabilities)

    @property
    def interest_bearing_debt(self):
        return self.st_interest_debt + self.lt_interest_debt

    @property
    def equity(self):
        return (self.share_capital + self.legal_capital_reserves
                + self.legal_retained_earnings + self.other_equity)

    @property
    def ebitda(self):
        return self.ebit + self.depreciation

    @property
    def has_cash_flow_statement(self):
        v = self.values.get("operating_cash_flow")
        return v is not None and not (isinstance(v, float) and math.isnan(v))

    @property
    def ocf(self):
        """Operating cash flow. If no cash flow statement is available we use
        the common approximation net income + depreciation."""
        if self.has_cash_flow_statement:
            return self.operating_cash_flow
        return self.net_income + self.depreciation

    @property
    def balance_difference(self):
        """Assets minus (liabilities + equity); should be 0."""
        return self.total_assets - (self.total_liabilities + self.equity)


def table_to_years(df, industry="General"):
    """Input table (DataFrame) -> list of FinancialYear, oldest first.
    Columns that are completely empty are ignored."""
    years = []
    for col in df.columns:
        if df[col].isna().all():
            continue
        years.append(FinancialYear(str(col), {k: df.at[k, col] if k in df.index else None
                                                for k in KEYS}, industry))
    return years


# ============================================================================
# Company profile: qualitative master data entered by the auditor.
#
# The profile is not just "nice to know" - it changes the analysis:
#     - Industry      -> industry-specific traffic-light thresholds for the ratios
#                        (a retailer naturally has a lower quick ratio than an IT firm)
#     - Size / listed -> suggests the type of audit (CO Art. 727) and therefore the
#                        framework: ISA 570 / PS-CH 570 (ordinary) or SER (limited audit)
#     - Founding year -> young companies have a higher failure rate (extra signal)
#     - Group         -> dependence on group support without a support letter (signal)
# ============================================================================

INDUSTRIES = [
    "General", "Manufacturing", "Retail and wholesale", "Construction", "Real estate",
    "IT and services", "Hospitality and tourism", "Healthcare", "Energy and utilities",
]
LEGAL_FORMS = ["AG / SA (company limited by shares)", "GmbH / Sàrl (limited liability company)",
               "Genossenschaft / Cooperative", "Other"]
AUDIT_TYPES = ["Ordinary audit (ISA 570 / PS-CH 570)", "Limited audit (SER)"]
CURRENCIES = ["CHF", "EUR", "USD"]
CANTONS = ["AG", "AI", "AR", "BE", "BL", "BS", "FR", "GE", "GL", "GR", "JU", "LU", "NE", "NW",
           "OW", "SG", "SH", "SO", "SZ", "TG", "TI", "UR", "VD", "VS", "ZG", "ZH", "Abroad"]

# ---------------------------------------------------------------------------
# Industry-specific thresholds: ratio -> (green from, red below).
# For "lower is better" ratios (net debt / EBITDA): (green up to, red above).
# Rules of thumb for teaching purposes - the auditor must apply judgement.
# ---------------------------------------------------------------------------
GENERAL = {"cash_ratio": (0.20, 0.10), "quick_ratio": (1.00, 0.70), "current_ratio": (1.50, 1.00),
           "equity_ratio": (0.20, 0.10), "ebitda_margin": (0.08, 0.00), "net_debt_ebitda": (3.0, 4.0)}

INDUSTRY_THRESHOLDS = {
    "General": GENERAL,
    "Manufacturing": GENERAL | {"current_ratio": (1.50, 1.10), "equity_ratio": (0.30, 0.15)},
    "Retail and wholesale": GENERAL | {"cash_ratio": (0.10, 0.05), "quick_ratio": (0.50, 0.30),
                                       "current_ratio": (1.20, 0.80), "equity_ratio": (0.25, 0.10),
                                       "ebitda_margin": (0.04, 0.00), "net_debt_ebitda": (2.5, 3.5)},
    "Construction": GENERAL | {"current_ratio": (1.30, 1.00), "quick_ratio": (0.80, 0.60),
                               "ebitda_margin": (0.05, 0.00)},
    "Real estate": GENERAL | {"current_ratio": (1.00, 0.50), "quick_ratio": (0.70, 0.40),
                              "equity_ratio": (0.30, 0.15), "ebitda_margin": (0.30, 0.10),
                              "net_debt_ebitda": (8.0, 12.0)},
    "IT and services": GENERAL | {"quick_ratio": (1.20, 0.80), "equity_ratio": (0.30, 0.15),
                                  "ebitda_margin": (0.10, 0.00), "net_debt_ebitda": (2.0, 3.0)},
    "Hospitality and tourism": GENERAL | {"cash_ratio": (0.15, 0.05), "quick_ratio": (0.60, 0.40),
                                          "current_ratio": (1.00, 0.60), "equity_ratio": (0.20, 0.05),
                                          "ebitda_margin": (0.10, 0.00), "net_debt_ebitda": (4.0, 5.0)},
    "Healthcare": GENERAL | {"equity_ratio": (0.30, 0.15), "ebitda_margin": (0.10, 0.00)},
    "Energy and utilities": GENERAL | {"current_ratio": (1.00, 0.70), "quick_ratio": (0.80, 0.50),
                                       "equity_ratio": (0.30, 0.15), "ebitda_margin": (0.15, 0.05),
                                       "net_debt_ebitda": (4.0, 5.5)},
}


def thresholds(industry, ratio_key):
    return INDUSTRY_THRESHOLDS.get(industry, GENERAL)[ratio_key]


def default_profile():
    return {"legal_form": LEGAL_FORMS[0], "industry": "General", "canton": "SG",
            "founded": 2000, "employees": 50, "currency": "CHF", "listed": False,
            "audit_type": AUDIT_TYPES[0], "group": False, "support_letter": False,
            "description": "", "key_risks": "", "notes": ""}


# ---------------------------------------------------------------------------
# CO Art. 727: ordinary audit if listed or if 2 of 3 thresholds are exceeded
# in two consecutive years (total assets 20m, revenue 40m, 250 FTE).
# ---------------------------------------------------------------------------
def audit_type_check(profile, years):
    def exceeded(fy):
        return [fy.total_assets > 20e6, fy.revenue > 40e6, profile["employees"] > 250]
    if profile["listed"]:
        return True, "Listed company -> ordinary audit (CO Art. 727 para. 1 no. 1)."
    if len(years) >= 2:
        both = [sum(exceeded(fy)) >= 2 for fy in years[-2:]]
        if all(both):
            return True, ("2 of 3 size thresholds exceeded in two consecutive years "
                          "-> ordinary audit (CO Art. 727 para. 1 no. 2).")
    return False, ("Size thresholds (total assets CHF 20m, revenue CHF 40m, 250 FTE) not "
                   "exceeded -> limited audit possible (CO Art. 727a), unless opted in.")


def profile_signals(profile):
    """Additional warning signals derived from the profile."""
    signals = []
    age = date.today().year - int(profile["founded"])
    if age < 5:
        signals.append(("Profile", f"Young company ({age} years) - start-ups have a higher failure rate"))
    if profile["group"] and not profile["support_letter"]:
        signals.append(("Profile", "Group company without a confirmed parent support letter"))
    return signals


# ============================================================================
# Fictitious sample companies (5 years, amounts in CHF thousand x 1,000)
# so the app can be demonstrated without uploading a real annual report.
# ============================================================================

YEARS = ["2021", "2022", "2023", "2024", "2025"]

# Values per line item for the five years (in CHF thousand)
SAMPLES = {
    "Alpenwerk Machines AG (distressed)": {
        "cash": [900, 650, 420, 210, 90],
        "receivables": [2100, 2250, 2400, 2550, 2600],
        "inventories": [1800, 2000, 2300, 2600, 2750],
        "other_current_assets": [150, 150, 140, 130, 120],
        "non_current_assets": [5200, 5050, 4850, 4600, 4350],
        "st_interest_debt": [600, 900, 1300, 1800, 2300],
        "other_current_liabilities": [1650, 1500, 2700, 2660, 3230],
        "lt_interest_debt": [2800, 2750, 2700, 2650, 2600],
        "other_non_current_liabilities": [400, 400, 380, 360, 360],
        "share_capital": [2000, 2000, 2000, 2000, 2000],
        "legal_capital_reserves": [500, 500, 500, 500, 500],
        "legal_retained_earnings": [400, 400, 400, 400, 400],
        "other_equity": [1800, 1650, 130, -280, -1480],
        "revenue": [11800, 11200, 10400, 9700, 9100],
        "depreciation": [600, 590, 570, 550, 520],
        "ebit": [420, -40, -1290, -260, -900],
        "interest_expense": [110, 130, 180, 230, 290],
        "net_income": [260, -150, -1520, -410, -1200],
        "operating_cash_flow": [780, 260, -350, -180, -420],
    },
    "Seeland Foods AG (healthy)": {
        "cash": [1400, 1650, 1900, 2150, 2400],
        "receivables": [1900, 1950, 2000, 2100, 2150],
        "inventories": [1100, 1120, 1150, 1180, 1200],
        "other_current_assets": [200, 200, 210, 210, 220],
        "non_current_assets": [6100, 6200, 6300, 6400, 6500],
        "st_interest_debt": [300, 300, 250, 250, 200],
        "other_current_liabilities": [1700, 1750, 1800, 1850, 1900],
        "lt_interest_debt": [2500, 2300, 2100, 1900, 1700],
        "other_non_current_liabilities": [500, 500, 520, 540, 560],
        "share_capital": [2500, 2500, 2500, 2500, 2500],
        "legal_capital_reserves": [600, 600, 600, 600, 600],
        "legal_retained_earnings": [700, 750, 800, 850, 900],
        "other_equity": [1900, 2420, 2990, 3550, 4110],
        "revenue": [14200, 14700, 15300, 15800, 16400],
        "depreciation": [700, 710, 720, 730, 740],
        "ebit": [1250, 1330, 1420, 1480, 1560],
        "interest_expense": [80, 75, 70, 62, 55],
        "net_income": [920, 990, 1060, 1110, 1170],
        "operating_cash_flow": [1580, 1660, 1740, 1800, 1880],
    },
}

# Suggested questionnaire answers for the distressed sample
SAMPLE_ANSWERS = {
    "Alpenwerk Machines AG (distressed)": {"F1": False, "F2": True, "F5": True, "O2": True,
                                           "M2": True},
    "Seeland Foods AG (healthy)": {},
}


# Company profiles of the samples (fictitious)
SAMPLE_PROFILES = {
    "Alpenwerk Machines AG (distressed)": {
        "industry": "Manufacturing", "canton": "SG", "founded": 1987, "employees": 70,
        "group": True, "support_letter": False,
        "description": "Manufacturer of precision machine components for the automotive industry.",
        "key_risks": "Dependence on two German automotive customers; rising energy costs."},
    "Seeland Foods AG (healthy)": {
        "industry": "Manufacturing", "canton": "BE", "founded": 1962, "employees": 85,
        "description": "Producer of chilled convenience food for Swiss retailers.",
        "key_risks": "Price pressure from retailers."},
}


def sample_table(name):
    data = SAMPLES[name]
    df = pd.DataFrame({y: [data[k][i] * 1000.0 for k in KEYS] for i, y in enumerate(YEARS)},
                      index=KEYS)
    df.index.name = "item"
    return df


# ============================================================================
# AI import: standardises uploaded annual reports with the Claude API.
#
# Annual reports look different in every company and follow different
# accounting standards. The AI reads the uploaded files (PDF, Excel, CSV) and
# maps every line item onto our standard format (section 1 of this file).
#
# How we keep the AI output reliable:
#     1. A fixed JSON schema forces the answer into the same structure every time.
#     2. The AI documents which original line items it mapped to which standard item.
#     3. Our own code checks the result (balance sheet must balance).
#     4. The auditor reviews and can correct every number before the analysis.
# ============================================================================

DEFAULT_MODEL = "claude-sonnet-5-5"

ITEM_LIST = "\n".join(f"- {k}: {label} ({stmt})" for k, (label, stmt) in LINE_ITEMS.items())

SYSTEM_PROMPT = f"""You are an expert in financial reporting (Swiss CO, Swiss GAAP FER, IFRS,
German HGB, US GAAP). You receive the annual report of a company (balance sheet,
income statement and, if available, cash flow statement) in any layout.
Map every line item onto the following standard items and add up where necessary:

{ITEM_LIST}

Rules:
1. Report all amounts in full units of the original currency. If the report says
   "in thousands" / "TCHF" multiply by 1,000; "in millions" by 1,000,000.
2. Signs: assets, liabilities, revenue, depreciation and interest expense are positive.
   Losses, loss carry-forwards and negative results are negative.
3. Equity split: share capital (or nominal capital); legal capital reserves (share premium);
   legal retained earnings; everything else (voluntary reserves, retained earnings or
   losses brought forward, result of the year, treasury shares) goes to other_equity.
4. Interest-bearing liabilities are bank loans, bonds, leasing and other loans. Trade
   payables, accruals and other non-interest-bearing items go to the "other" items.
   Provisions go to short- or long-term according to their maturity (long-term if unclear).
5. If EBIT is not shown, calculate it (e.g. earnings before tax + interest expense -
   financial income) and add a note.
6. If there is no cash flow statement set has_cash_flow_statement = false and
   operating_cash_flow = 0.
7. Never invent numbers. If a value is missing and cannot be derived, use 0 and add a note.
8. Capture every financial year contained in the documents (usually current and prior year).
9. In "mappings" document which original line items went into which standard item.
10. State the accounting standard the report is prepared under."""

_year_schema = {
    "type": "object",
    "properties": {
        "year": {"type": "string", "description": "Financial year, e.g. 2025"},
        "has_cash_flow_statement": {"type": "boolean"},
        **{k: {"type": "number", "description": label} for k, (label, _) in LINE_ITEMS.items()},
    },
    "required": ["year", "has_cash_flow_statement", *KEYS],
    "additionalProperties": False,
}

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "company": {"type": "string"},
        "currency": {"type": "string"},
        "standard": {"type": "string",
                     "enum": ["Swiss CO", "Swiss GAAP FER", "IFRS", "HGB", "US GAAP", "unknown"]},
        "years": {"type": "array", "items": _year_schema},
        "mappings": {"type": "array", "items": {
            "type": "object",
            "properties": {"standard_item": {"type": "string", "enum": KEYS},
                           "original_items": {"type": "string"}},
            "required": ["standard_item", "original_items"],
            "additionalProperties": False}},
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["company", "currency", "standard", "years", "mappings", "notes"],
    "additionalProperties": False,
}


def file_to_content(name, data: bytes):
    """Converts one uploaded file into content blocks for the Claude API."""
    ext = name.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        return [{"type": "text", "text": f"File: {name}"},
                {"type": "document", "source": {
                    "type": "base64", "media_type": "application/pdf",
                    "data": base64.standard_b64encode(data).decode()}}]
    if ext in ("xlsx", "xls"):
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None)
        text = "\n\n".join(f"### Sheet: {s}\n{df.dropna(how='all').to_csv(index=False, header=False)}"
                           for s, df in sheets.items())
        return [{"type": "text", "text": f"File: {name}\n{text}"}]
    if ext in ("csv", "txt"):
        return [{"type": "text", "text": f"File: {name}\n" + data.decode("utf-8", errors="replace")}]
    raise ValueError(f"File type .{ext} is not supported (use PDF, Excel or CSV).")


def call_claude(content, api_key=None, model=DEFAULT_MODEL, client=None):
    """Sends the files to Claude and returns the parsed JSON answer."""
    if client is None:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": [
            *content,
            {"type": "text", "text": "Convert these financial statements into the standard format."},
        ]}],
        output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def answer_to_table(answer):
    """AI answer -> input table (rows = items, columns = years, oldest left)."""
    years = sorted(answer["years"], key=lambda y: y["year"])[-MAX_YEARS:]
    if not years:
        raise ValueError("The AI did not find any financial year in the documents.")
    df = pd.DataFrame(index=KEYS)
    df.index.name = "item"
    for y in years:
        col = [float(y[k]) for k in KEYS]
        if not y["has_cash_flow_statement"]:
            col[KEYS.index("operating_cash_flow")] = float("nan")  # -> approximation
        df[str(y["year"])] = col
    return df


def check_balance(df):
    """Own check without AI: do assets equal liabilities + equity in every year?"""
    warnings = []
    for col in df.columns:
        fy = FinancialYear(col, df[col].to_dict())
        diff = fy.balance_difference
        if abs(diff) > max(1.0, 0.005 * abs(fy.total_assets)):
            warnings.append(f"{col}: assets ({fy.total_assets:,.0f}) and liabilities + equity "
                            f"({fy.total_liabilities + fy.equity:,.0f}) differ by {diff:,.0f}.")
    return warnings


def standardise(files, api_key=None, model=DEFAULT_MODEL, client=None):
    """Complete pipeline. files: list of (file name, bytes).
    Returns (table, AI answer, list of balance check warnings)."""
    content = [block for name, data in files for block in file_to_content(name, data)]
    answer = call_claude(content, api_key, model, client)
    table = answer_to_table(answer)
    return table, answer, check_balance(table)
