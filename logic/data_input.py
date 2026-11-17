"""
DATA INPUT - everything that describes the client and its financial statements.

Sections:
    1. Standard format of the financial statements (line items, FinancialYear)
    2. Company profile (industry thresholds, audit type check CO Art. 727)
    3. Sample companies for testing and the demo
    4. AI import with the Claude API (any annual report -> standard format)
"""

# imports the necessary libraries for the code. 
import base64                           # converts files (PDF, Excel, CSV) into text needed to send to the Claude API
import io                               # treats data in memory like a file, so it can be read by pandas (Excel, CSV)
import json                             # concerts JSON text answer of AI into a Python dictionary
import math                             # math helpers, e.g. math.isnan() to check if there are empty table cells
from dataclasses import dataclass       # short way to define class FinancialYear (one financial year)
from datetime import date               # today's date, used to calculate age of the company

import pandas as pd                     # external library for dataframes (tables) -> (financial statements: line items x years)


# ============================================================================
# First the financial statements (balance sheet, income statement and cash flow statement) need to be mapped into a standard format, so that the analysis can be done in a uniform way.
#
# Every uploaded annual report - whatever its layout or accounting standard
# (Swiss CO, Swiss GAAP FER, IFRS, ...) - is mapped onto the line items below.
# All ratios, the questionnaire logic and the ML model work with this format only.
# ============================================================================

# ---------------------------------------------------------------------------
# Standard line items: key -> (label shown in the app, statement)
# so for example => "cash": ("Cash and cash equivalents", "Balance sheet"), means, that the key "cash" is used in the code, the label shown to the user is "Cash and cash equivalents" and it belongs to the balance sheet.
# this is done for all needed items in the balance sheet, income statement and cash flow statement.
# ---------------------------------------------------------------------------
LINE_ITEMS = {
    # Balance sheet: assets
    "cash": ("Cash and cash equivalents", "Balance sheet"),
    "receivables": ("Short-term receivables", "Balance sheet"),
    "inventories": ("Inventories", "Balance sheet"),
    "other_current_assets": ("Other current assets", "Balance sheet"),
    "non_current_assets": ("Non-current assets", "Balance sheet"),

    # Balance sheet:liabilities
    "st_interest_debt": ("Short-term interest-bearing liabilities", "Balance sheet"),
    "other_current_liabilities": ("Trade payables and other short-term liabilities", "Balance sheet"),
    "lt_interest_debt": ("Long-term interest-bearing liabilities", "Balance sheet"),
    "other_non_current_liabilities": ("Other long-term liabilities and provisions", "Balance sheet"),

    # Balance sheet:equity (split as required by Swiss CO Art. 725a)
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
KEYS = list(LINE_ITEMS)                                 #internal names of the line items, used in the code, e.g. "cash", "receivables", ..
LABELS = {k: v[0] for k, v in LINE_ITEMS.items()}       #internal name -> label shown in the app, e.g. "cash" -> "Cash and cash equivalents"
MAX_YEARS = 5                                           #the app analyses financial statements of 5 years max, from the oldest to the most recent year


def empty_table(years):                                                                 # This function creates an empty input table. 
    """Empty input table: rows = line items, columns = years (oldest left)."""          # The line items are the rows and the years are the columns, the oldest year is on the left
    df = pd.DataFrame({str(y): [float("nan")] * len(KEYS) for y in years}, index=KEYS)  # explanations: nan = "not a number" = empty cell, index = Keys => the rows are the (19) line items used in the code, e.g. "cash", "receivables"
    df.index.name = "item"                                                              # the name of the index (row labels) is defined as "item" 
    return df                                                                           


def _num(value):                                                                        # to be able to do calculations with the values in the table, we need to convert them to float. If a cell is empty, we count it as 0.
    """Convert a table cell to float; empty cells count as 0."""
    try:                                       # try-function = if the value can be converted to float, we do it, otherwise we return 0.0
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(v) else v


@dataclass                      # Python automatically generates the __init__() function, so we don't have to write it ourselves. The class FinancialYear represents one financial year with its line items and derived totals.
class FinancialYear: 
    """One financial year in the standard format, with derived totals."""

    year: str                     # Financial year as text, e.g. "2025"
    values: dict                  # all line items of this year, e.g. {"cash": 1000000.0, "receivables": 2000000.0}
    industry: str = "General"     # selects the traffic-light thresholds, according to the industry of the company

    def __getattr__(self, name):
        # Allows fy.cash, fy.revenue, ... instead of fy.values["cash"]
        # Python calls this function automatically when an attribute doesn't exist directly in the class
        if name in LINE_ITEMS:                      # is requested name one of our line items?
            return _num(self.values.get(name))      # yes: return its value as a number (empty cell = 0)
        raise AttributeError(name)                  # no: normal error "this attribute doesn't exist"

    # -- Derived totals -----------------------------------------------------
    # Values that are not entered but calculated from the line items. These are used in the analysis and ratios.
    # @property = value that is calculated each time it is used (fy.total_assets without brackes), instead of being stored in the object.
    # This way we always have the latest value in the table if the line items change.
    
    @property
    def current_assets(self):
        # current assts = cash + receivables + inventories + other current assets
        return self.cash + self.receivables + self.inventories + self.other_current_assets

    @property
    def total_assets(self):
        # total assets = current assets + non-current assets
        return self.current_assets + self.non_current_assets

    @property
    def current_liabilities(self):
        # current liabilities = short-term interest-bearing debt + other current liabilities (trade payables, accruals, provisions)
        return self.st_interest_debt + self.other_current_liabilities

    @property
    def total_liabilities(self):
        # total liabilities (Fremdkapital) = current (short-term) liabilities + long-term interest-bearing debt + other non-current liabilities
        return (self.current_liabilities + self.lt_interest_debt
                + self.other_non_current_liabilities)

    @property
    def interest_bearing_debt(self):
        # only debt that bears interest (bank loans, bonds, leasing, other loans) is relevant for the net debt / EBITDA ratio. Trade payables and accruals are not interest-bearing and therefore not included.
        return self.st_interest_debt + self.lt_interest_debt

    @property
    def equity(self):
        # equity = share capital + legal capital reserves + legal retained earnings + other equity (voluntary reserves, retained earnings / losses)
        return (self.share_capital + self.legal_capital_reserves
                + self.legal_retained_earnings + self.other_equity)

    @property
    def ebitda(self):
        # EBITDA = EBIT + depreciation and amortisation. 
        return self.ebit + self.depreciation

    @property
    def has_cash_flow_statement(self):
        # True if operating cash flow was entered, False if cell is empty
        v = self.values.get("operating_cash_flow")                              #value from the table, can be None if the cell is empty
        return v is not None and not (isinstance(v, float) and math.isnan(v))   # not missing and not NaN => cash flow statement is available

    @property
    def ocf(self):
        """Operating cash flow. If no cash flow statement is available we use
        the common approximation net income + depreciation."""
        if self.has_cash_flow_statement:                                        # if real value from the cash flow statement is available, we use it 
            return self.operating_cash_flow                                     
        return self.net_income + self.depreciation                              # if not, approximation 

    @property
    def balance_difference(self):
        """Assets minus (liabilities + equity); should be 0."""
        # used for balance check: difference means figures are wrong or incomplete
        return self.total_assets - (self.total_liabilities + self.equity)


def table_to_years(df, industry="General"):
    """Input table (DataFrame) -> list of FinancialYear, oldest first.
    Columns that are completely empty are ignored."""
    years = []                                                                  # empty list, filled with one FinancialYear per year
    for col in df.columns:                                                      # go through every column of table
        if df[col].isna().all():                                                # column completely empty?
            continue                                                            # skip and go to next year

        # create one FinancialYear: year dictionary {line item: value}, industry
        # df.at[k, col] = calue in row k (line item) and column col (year);
        # None if the line item is missing in a table
        years.append(FinancialYear(str(col), {k: df.at[k, col] if k in df.index else None       
                                                for k in KEYS}, industry))
    return years


# ============================================================================
# Company profile: qualitative master data entered by the auditor.
#
# The profile is not just "nice to know" - it changes the analysis:
#     - Industry      -> industry-specific traffic-light thresholds for the ratios
#                        (e.g. a retailer naturally has a lower quick ratio than an IT firm)
#     - Size / listed -> suggests the type of audit (CO Art. 727) and therefore the
#                        framework: ISA 570 / PS-CH 570 (ordinary) or SER (limited audit)
#     - Founding year -> young companies have a higher failure rate (extra signal)
#     - Group         -> dependence on group support without a support letter (signal)
# ============================================================================

# in the following blocks we define the possible values for the profile fields, so that the auditor can select them in the app. The actual values of a specific company are stored in a dict (see default_profile() and SAMPLE_PROFILES).
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
# Now we define the traffic-light thresholds for the ratios. The auditor can select the industry of the company and the app will use the corresponding thresholds for the analysis. 
# The thresholds are defined as tuples (green, red), values in between are yellow. 
# For "lower is better" ratios (e.g. for net debt / EBITDA): (green up to, red above).
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
    # .get(industry, GENERAL): take the threshold of this industry, if industry is unknown the general thresholds are used instead
    # [ratio_key]: pick thresholds of requested ratio
    return INDUSTRY_THRESHOLDS.get(industry, GENERAL)[ratio_key]


def default_profile():
    # these are the starting values of company profile (page 1) that get shown in the app before the users enter anything themselves
    return {"legal_form": LEGAL_FORMS[0], "industry": "General", "canton": "SG",
            "founded": 2000, "employees": 50, "currency": "CHF", "listed": False,
            "audit_type": AUDIT_TYPES[0], "group": False, "support_letter": False,
            "description": "", "key_risks": "", "notes": ""}

# ---------------------------------------------------------------------------
# Here we check the profile to see if an ordinary audit is required (CO Art. 727) or if a limited audit is possible (CO Art. 727a). 
# The thresholds are:
# CO Art. 727: ordinary audit if listed or if 2 of 3 thresholds are exceeded
# in two consecutive years (total assets 20m, revenue 40m, 250 FTE).
# if the listed criteria isn't met, a limited audit is possible (CO Art. 727a), unless the company opts in for an ordinary audit.
# ---------------------------------------------------------------------------
def audit_type_check(profile, years):
    def exceeded(fy):
        #One True/False per threshold -> e.g. [True, False, True] means 2 of 3 thresholds exceeded => ordinary audit required
        #                             -> e.g. [False, False, True] means 1 of 3 thresholds exceeded => limited audit possible
        return [fy.total_assets > 20e6, fy.revenue > 40e6, profile["employees"] > 250]
    if profile["listed"]:
        return True, "Listed company -> ordinary audit (CO Art. 727 para. 1 no. 1)."
    #If company isn't listed => For each of the last two years: Are at least 2 of the 3 thresholds exceeded? (total assets CHF 20m, revenue CHF 40m, 250 FTE)
    if len(years) >= 2:
        both = [sum(exceeded(fy)) >= 2 for fy in years[-2:]]
        if all(both):                                                                       #both years exceeded 2 of 3 thresholds -> ordinary audit required
            return True, ("2 of 3 size thresholds exceeded in two consecutive years "
                          "-> ordinary audit (CO Art. 727 para. 1 no. 2).")
    return False, ("Size thresholds (total assets CHF 20m, revenue CHF 40m, 250 FTE) not "  # thresholds aren't exceeded -> limited audit possible, unless company voluntarly wants to do ordinary audit (= opt in)
                   "exceeded -> limited audit possible (CO Art. 727a), unless opted in.")


def profile_signals(profile):
    """Additional warning signals derived from the profile."""
    signals = []                                        #list of (category,text) tuples
    age = date.today().year - int(profile["founded"])
    if age < 5:                                         #start-ups have a higher failure rate, so we add a warning signal if the company is younger than 5 years
        signals.append(("Profile", f"Young company ({age} years) - start-ups have a higher failure rate"))
    if profile["group"] and not profile["support_letter"]:  #if the company is part of a group but there is no support letter from the parent company, we add a warning signal as well, the audtior should check if the parent company is willing to support the subsidiary in case of financial distress
        signals.append(("Profile", "Group company without a confirmed parent support letter"))
    return signals


# ============================================================================
# to test it without uploading a real annual report, we provide two fictitious sample companies: one distressed and one healthy. The auditor can select one of these samples in the app and see how the analysis works.
# this also serves as a test for the AI import: the Claude API should be able to map the uploaded sample files onto the standard format and produce the same numbers as in the SAMPLES dict below.
# two Fictitious sample companies (5 years, amounts in CHF thousand x 1,000), one called "Alpenwerk Machines AG" (distressed) and one called "Seeland Foods AG" (healthy). 
# therefore the app can also be demonstrated without uploading a real annual report, if the API wouldn't be available or if the user doesn't want to upload a real annual report.
# ============================================================================

# We use the years 2021-2025, as it represents the last 5 fiscal years (as of now in 2026) and is a common time frame for financial analysis.
YEARS = ["2021", "2022", "2023", "2024", "2025"]

# Values per line item for the five years (in CHF thousand) are defined 
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

# For the questionnaire logic (4_questionnaire.py) we need to know which answers the auditor would have given for the distressed sample, so that the app can demonstrate the questionnaire and its effect on the analysis. 
# The healthy sample has no answers, so that the auditor can fill them in himself.
# Suggested questionnaire answers for the distressed sample:
SAMPLE_ANSWERS = {
    "Alpenwerk Machines AG (distressed)": {"F1": False, "F2": True, "F5": True, "O2": True,
                                           "M2": True},
    "Seeland Foods AG (healthy)": {},
}


# In the first part of the app, the auditor enters the company profile (industry, size, founding year, group, support letter, etc.).
# We've provided example company profiles of our two samples (completely fictitious)
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


def sample_table(name):                                                                          # turns a sample company into an input table, in same format as an uploaded and standardised annual report 
    data = SAMPLES[name]
    
    # Builds the table column by column: 
    # enumerate(Years) gives position and year (0, "2021") 
    # data[k][i] = value of line item k in year number i     
    #  * 1000.0 = converts from CHF thousands into full CHF                          
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

# We define which Claude model is used for the AI import (default: "claude-sonnet-5-5").
# Another model can be set without changing the code: AI_MODEL in .streamlit/secrets.toml
# (read in api_settings() on page 2).
DEFAULT_MODEL = "claude-sonnet-5-5"

#----------------------------------------------------------------------------
# First we create an instruction for the AI, which lists all standard line items and their labels. The AI will map the uploaded annual report onto these items.
# Then we define the accounting rules that the AI must follow
#----------------------------------------------------------------------------

# List of all standard line items as text, one per line, for the instructions to the AI.
# Example of one line: "- cash: Cash and cash equivalents (Balance sheet)"
# k = internal name, label = name shown in the app, stmt = statement it belongs to;
# "\n".join(...) puts all lines together, separated by line breaks.

ITEM_LIST = "\n".join(f"- {k}: {label} ({stmt})" for k, (label, stmt) in LINE_ITEMS.items())

# Prompt for the AI API: role, task, rules
SYSTEM_PROMPT = f"""You are an expert in financial reporting (Swiss CO, Swiss GAAP FER, IFRS). You receive the annual report of a company (balance sheet,
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

#----------------------------------------------------------------------------
# JSON shema for the AI output => JSON shema is a fixed "form" the AI must fill in
# The API guarantees that the AI answer will always follow this schema, so our code can read it reliably
# Answer = company, currency, accounting standard, one entry per financial year with all line items, the mapping (original item -> standard item) and notes
#----------------------------------------------------------------------------
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

# Here we define the JSON schema for the AI output

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

# In the following functions we convert the uploaded files into a format that the Claude API can understand, call the API and put the answer into our standard format.
def file_to_content(name, data: bytes):
    """Converts one uploaded file into content blocks for the Claude API."""
    ext = name.lower().rsplit(".", 1)[-1]                   #file extension, e.g. "pdf", "xlsx", "csv"
    if ext == "pdf":
        return [{"type": "text", "text": f"File: {name}"},
                {"type": "document", "source": {
                    "type": "base64", "media_type": "application/pdf",
                    "data": base64.standard_b64encode(data).decode()}}]
    # This function is called for every uploaded file. We support PDF, Excel and CSV files. The Claude API can read PDF files directly, but for Excel and CSV we convert them to text first, so that the AI can read them.
    if ext in ("xlsx", "xls"):
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None)
        text = "\n\n".join(f"### Sheet: {s}\n{df.dropna(how='all').to_csv(index=False, header=False)}"
                           for s, df in sheets.items())
        return [{"type": "text", "text": f"File: {name}\n{text}"}]
    
    # For CSV and TXT files we read them as text and send them to the Claude API. The AI will try to extract the financial statements.
    if ext in ("csv", "txt"):
        return [{"type": "text", "text": f"File: {name}\n" + data.decode("utf-8", errors="replace")}]
    raise ValueError(f"File type .{ext} is not supported (use PDF, Excel or CSV).")

# Here we call the Claude API with the content blocks we created from the uploaded files. The API will return a JSON answer that follows the schema we defined above. We parse the answer and return it as a Python dict.
def call_claude(content, api_key=None, model=DEFAULT_MODEL, client=None):
    """Sends the files to Claude and returns the parsed JSON answer."""
    if client is None:                                  #client can be replaced by a fake one in tests, so that we don't have to call the real API every time
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

    # The actual API request: model, maximum answer length, instruction (SYSTEM_PROMPT), files, and output_config = "Answer exactly in the form of RESPONSE_SCHEMA"
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
    text = next(b.text for b in response.content if b.type == "text")       #the JSON text is in the first text block of the answer, we extract it
    return json.loads(text)                                                 #JSON text -> Python dictionary 


def answer_to_table(answer):
    """AI answer -> input table (rows = items, columns = years, oldest left)."""
    # The AI answer contains a list of financial years, each with all line items. We sort the years by year and take the last MAX_YEARS (5) years. 
    years = sorted(answer["years"], key=lambda y: y["year"])[-MAX_YEARS:]
    if not years:
        raise ValueError("The AI did not find any financial year in the documents.")

    #Then we create a DataFrame with the line items as rows and the years as columns. We fill in the values from the AI answer. If a cash flow statement is missing, we set the operating cash flow to NaN (to indicate that it is an approximation).
    df = pd.DataFrame(index=KEYS)
    df.index.name = "item"
    for y in years:
        col = [float(y[k]) for k in KEYS]

    # if the AI answer indicates that there is no cash flow statement, we set the operating cash flow to NaN (not a number) to indicate that it is an approximation. 
    # Otherwise, we use the value provided by the AI.
        if not y["has_cash_flow_statement"]:
            col[KEYS.index("operating_cash_flow")] = float("nan")  # -> nan = approximation
        df[str(y["year"])] = col
    return df

# Now we check the balance sheet: assets must equal liabilities + equity. If there is a difference, we add a warning. We set a tolerance of 0.5% of total assets or 1 CHF, whichever is larger. If the difference is larger than this, we add a warning.
def check_balance(df):
    """Own check without AI: do assets equal liabilities + equity in every year?"""
    warnings = []
    for col in df.columns:
        fy = FinancialYear(col, df[col].to_dict())
        diff = fy.balance_difference
        if abs(diff) > max(1.0, 0.005 * abs(fy.total_assets)):                                      # tolereance of 0.5% of total assets or 1 CHF, whichever is larger.
            warnings.append(f"{col}: assets ({fy.total_assets:,.0f}) and liabilities + equity "
                            f"({fy.total_liabilities + fy.equity:,.0f}) differ by {diff:,.0f}.")
    return warnings

# Now we combine all the steps: the auditor uploads files, 1) we convert them to content blocks, call the Claude API, parse the answer into a table, and check the balance. 
# We return the table, the AI answer, and any balance check warnings.
def standardise(files, api_key=None, model=DEFAULT_MODEL, client=None): 
    """Complete pipeline. files: list of (file name, bytes).
    Returns (table, AI answer, list of balance check warnings)."""
    content = [block for name, data in files for block in file_to_content(name, data)]      # For every uploaded file we create content blocks for the Claude API, they're all combined into one list of content blocks
    answer = call_claude(content, api_key, model, client)                                   # The content blocks are sent to the Claude API, which returns a JSON answer that follows the schema we defined above. The answer gets put into a Python dictionary
    table = answer_to_table(answer)                                                         # The AI answer is converted into a DataFrame with the line items as rows and the years as columns. 
    return table, answer, check_balance(table)                                              # The function returns the table, the AI answer, and any balance check warnings. The auditor can then review the table and make any corrections before proceeding with the analysis.
