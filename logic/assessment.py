"""
ASSESSMENT - qualitative questions and the overall conclusion.

Sections:
    1. ISA 570 questionnaire (events and conditions, next 12 months)
    2. Combination of all results into one going concern risk
    3. Auditor's conclusion -> implication for the auditor's report
"""

from dataclasses import dataclass

from logic import analysis
from logic.analysis import AMBER, GREEN, RED
from logic.data_input import profile_signals


# ============================================================================
# Qualitative going concern questionnaire derived from ISA 570 (Revised).
#
# The questions cover the events and conditions listed in ISA 570.A3
# (financial, operating, other) and the evaluation of management's assessment
# and plans (ISA 570.12-16). They refer to the next 12 months.
#
# Answer "Yes" = risk indicator present. Each question has a weight
# (1 = weak, 2 = medium, 3 = strong indicator). Knock-out (KO) questions
# set the overall risk to "high" regardless of the other results.
#
# Score idea (from our project concept): every "Yes" gives points; the share
# of points reached is the qualitative risk, e.g. 6 of 10 points = 60 %.
# ============================================================================

@dataclass(frozen=True)
class Question:
    id: str
    category: str
    text: str
    reference: str
    weight: int
    knock_out: bool = False


QUESTIONS = [
    # --- Financial events or conditions (ISA 570.A3) -------------------------
    Question("F1", "Financial",
             "Do borrowings or credit lines fall due within the next 12 months without "
             "realistic prospects of renewal or repayment?", "ISA 570.A3", 3, True),
    Question("F2", "Financial",
             "Has the entity breached, or is it likely to breach, loan covenants?",
             "ISA 570.A3", 2),
    Question("F3", "Financial",
             "Are there arrears in taxes or social security contributions (e.g. AHV/AVS)?",
             "ISA 570.A3", 3, True),
    Question("F4", "Financial",
             "Is the entity unable to pay creditors on their due dates?", "ISA 570.A3", 3),
    Question("F5", "Financial",
             "Have suppliers changed from credit terms to cash on delivery or prepayment?",
             "ISA 570.A3", 2),
    Question("F6", "Financial",
             "Has financial support from lenders, shareholders or the group been "
             "withdrawn or not been confirmed?", "ISA 570.A3", 2),
    Question("F7", "Financial",
             "Is the entity unable to obtain financing for essential investments or "
             "new product development?", "ISA 570.A3", 1),
    Question("F8", "Financial",
             "Have dividends been suspended or are there arrears in dividends?",
             "ISA 570.A3", 1),
    # --- Operating events or conditions ---------------------------------------
    Question("O1", "Operating",
             "Does management intend to liquidate the entity or to cease operations?",
             "ISA 570.A3", 3, True),
    Question("O2", "Operating",
             "Has the entity lost a major market, key customer, licence, franchise or "
             "principal supplier?", "ISA 570.A3", 2),
    Question("O3", "Operating",
             "Has key management left without replacement?", "ISA 570.A3", 1),
    Question("O4", "Operating",
             "Are there labour difficulties or shortages of important supplies?",
             "ISA 570.A3", 1),
    Question("O5", "Operating",
             "Has a highly successful competitor emerged?", "ISA 570.A3", 1),
    # --- Other events or conditions --------------------------------------------
    Question("X1", "Other",
             "Are there pending legal or regulatory proceedings that could result in "
             "claims the entity is unlikely to be able to satisfy?", "ISA 570.A3", 2),
    Question("X2", "Other",
             "Is the entity in non-compliance with capital or other statutory "
             "requirements?", "ISA 570.A3", 2),
    Question("X3", "Other",
             "Are changes in law, regulation or government policy expected to adversely "
             "affect the entity?", "ISA 570.A3", 1),
    Question("X4", "Other",
             "Has an uninsured or underinsured catastrophe occurred?", "ISA 570.A3", 1),
    # --- Management's assessment and plans (ISA 570.12-16) ---------------------
    Question("M1", "Management's assessment",
             "Is management's going concern assessment missing or shorter than "
             "12 months from the balance sheet date?", "ISA 570.13", 2),
    Question("M2", "Management's assessment",
             "Are management's plans for future actions not feasible or not supported "
             "by sufficient evidence?", "ISA 570.16(b)", 3),
    Question("M3", "Management's assessment",
             "Is the cash flow forecast based on assumptions that are not reasonable or "
             "not supportable?", "ISA 570.16(c)", 2),
]
QUESTION_BY_ID = {q.id: q for q in QUESTIONS}
CATEGORIES = list(dict.fromkeys(q.category for q in QUESTIONS))


def evaluate_questionnaire(answers):
    """answers: dict question id -> True (Yes) / False (No).

    Returns the qualitative risk score (0-1), the list of risk indicators
    answered with Yes and the triggered knock-out questions."""
    total = sum(q.weight for q in QUESTIONS)
    yes = [q for q in QUESTIONS if answers.get(q.id)]
    points = sum(q.weight for q in yes)
    return {
        "score": points / total if total else 0.0,
        "points": points,
        "max_points": total,
        "yes": yes,
        "knock_outs": [q for q in yes if q.knock_out],
        "answered": len(answers),
    }


# ============================================================================
# Combination of ratios, questionnaire, liquidity plan and ML model into one
# going concern risk assessment - and the link to the auditor's conclusion
# under ISA 570.
#
# Overall risk = weighted average of
#     quantitative score (ratios, latest year)
#     qualitative score  (ISA 570 questionnaire)
#     ML score           (bankruptcy model, if trained)
# Knock-out criteria override the average and set the risk to "High".
#
# The app SUPPORTS the auditor. The final conclusion is a matter of professional
# judgement (ISA 570.17) and is recorded separately by the auditor.
# ============================================================================

DEFAULT_WEIGHTS = {"quantitative": 0.4, "qualitative": 0.4, "ml": 0.2}
LEVELS = [(0.30, "Low", GREEN), (0.60, "Medium", AMBER), (1.01, "High", RED)]

LEVEL_TEXT = {
    "Low": ("No significant events or conditions identified. The going concern basis of "
            "accounting appears appropriate. Document the assessment (ISA 570.10-12)."),
    "Medium": ("Events or conditions identified that may cast significant doubt. Perform "
               "additional audit procedures: evaluate management's plans and the cash flow "
               "forecast, obtain written representations (ISA 570.16)."),
    "High": ("Significant doubt about the entity's ability to continue as a going concern. "
             "Determine whether a material uncertainty exists, assess the adequacy of the "
             "disclosures and the impact on the auditor's report (ISA 570.18-23)."),
}


def assess(years, answers, liquidity_result=None, ml_score=None, weights=None, profile=None):
    weights = dict(weights or DEFAULT_WEIGHTS)
    if ml_score is None:
        weights["ml"] = 0.0                       # model not available -> ignore
    total_w = sum(weights.values()) or 1.0

    latest = years[-1]
    quant = analysis.quantitative_score(years)
    qual = evaluate_questionnaire(answers)
    parts = {"quantitative": quant, "qualitative": qual["score"], "ml": ml_score or 0.0}
    score = sum(weights[k] * parts[k] for k in parts) / total_w

    # ---- Knock-out criteria ------------------------------------------------
    knock_outs = []
    if analysis.over_indebtedness(latest)["status"] == RED:
        knock_outs.append("Over-indebtedness (CO Art. 725b)")
    if liquidity_result and liquidity_result["first_shortfall_measures"] is not None:
        knock_outs.append(f"Liquidity shortfall in month {liquidity_result['first_shortfall_measures']} "
                          "(after planned restructuring measures, CO Art. 725)")
    knock_outs += [f"{q.id}: {q.text}" for q in qual["knock_outs"]]

    level, colour = next((name, col) for limit, name, col in LEVELS if score < limit)
    if knock_outs:
        level, colour = "High", RED

    # ---- Warning signals for the report -------------------------------------
    signals = []
    for r in analysis.RATIOS:
        if r.weight and r.status(latest) == RED:
            signals.append(("Ratio", f"{r.name}: {analysis.display(r, latest)}"))
    # (Trends are shown on the ratio analysis page, not repeated as warning signals)
    cap = analysis.capital_loss(latest)
    if cap["status"] != GREEN:
        signals.append(("Legal", cap["result"] + " (CO Art. 725a)"))
    for q in qual["yes"]:
        signals.append(("Questionnaire", f"{q.id}: {q.text}"))
    if profile:
        signals += profile_signals(profile)

    return {"score": score, "level": level, "colour": colour, "parts": parts,
            "weights": weights, "knock_outs": knock_outs, "signals": signals,
            "text": LEVEL_TEXT[level], "questionnaire": qual}


# ---------------------------------------------------------------------------
# Auditor's conclusion -> implication for the auditor's report (ISA 570.21-23)
# ---------------------------------------------------------------------------
def report_implication(basis_appropriate, material_uncertainty, adequately_disclosed):
    if not basis_appropriate:
        return ("Adverse opinion",
                "The going concern basis of accounting is inappropriate (ISA 570.21).")
    if not material_uncertainty:
        return ("Unmodified opinion",
                "No material uncertainty related to going concern (ISA 570.17).")
    if adequately_disclosed:
        return ("Unmodified opinion with a 'Material Uncertainty Related to Going Concern' section",
                "Material uncertainty adequately disclosed in the notes (ISA 570.22).")
    return ("Qualified or adverse opinion",
            "Material uncertainty not adequately disclosed (ISA 570.23).")
