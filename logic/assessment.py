"""
ASSESSMENT - qualitative questions and the overall conclusion.

Sections:
    1. ISA 570 questionnaire (events and conditions, next 12 months)
    2. Combination of all results into one going concern risk
    3. Auditor's conclusion -> implication for the auditor's report
"""

# Questions for page 4, the overall risk shown on page 7 and the implication for the auditor's report.
# Use of generative AI:
# - Code: parts of the code in this file were written with the help of Claude (Anthropic). We reviewed, tested and adjusted them.
# - Comments: Claude was used as support for writing the comments and making sure that the structure fits. We checked and partly adjusted them.

from dataclasses import dataclass

from logic import analysis
from logic.analysis import AMBER, GREEN, RED
from logic.data_input import profile_signals


# --- ISA 570 questionnaire ---
# Events and conditions of ISA 570.A3 (financial, operating, other) plus management's assessment
# and plans (ISA 570.12-16), each for the next 12 months.
# "Yes" = risk indicator present. Weight 1 = weak, 2 = medium, 3 = strong indicator.
# Knock-out (KO) questions set the overall risk to "High" regardless of the other results.
# Score (from our project concept): share of the weighted points answered "Yes", e.g. 6 of 10 = 60 %.

@dataclass(frozen=True)
class Question:
    id: str
    category: str
    text: str
    reference: str
    weight: int
    knock_out: bool = False


QUESTIONS = [
    # --- Financial events or conditions (ISA 570.A3) ---
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
    # --- Operating events or conditions ---
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
    # --- Other events or conditions ---
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
    # --- Management's assessment and plans (ISA 570.12-16) ---
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
CATEGORIES = list(dict.fromkeys(q.category for q in QUESTIONS))   # unique, in order of appearance


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


# --- Overall going concern risk ---
# Weighted average of the quantitative score (ratios), the qualitative score (questionnaire) and
# the ML score. All three use the same scale (0 = no risk, 1 = maximum risk), so they can be averaged.
# Knock-out criteria override the average and set the risk to "High".
# The app SUPPORTS the auditor; the conclusion is professional judgement (ISA 570.17).
# Example (ML model not trained, default weights 0.4 / 0.4):
#     (0.4 * 0.70 + 0.4 * 0.50) / (0.4 + 0.4) = 0.60 -> "High"
# level_for(), score_breakdown() and weight_sensitivity() were written with the help of Claude (see header).

# Ratios (past, annual report) and questionnaire (next 12 months, ISA 570.A3) count the same.
# The ML model counts less because it is trained on Polish companies and only partly transferable
# to Swiss firms. The auditor can change the weights on page 7.
DEFAULT_WEIGHTS = {"quantitative": 0.4, "qualitative": 0.4, "ml": 0.2}

COMPONENT_LABELS = {"quantitative": "Ratios", "qualitative": "ISA 570 questionnaire",
                    "ml": "ML model"}

# (upper limit of the score, name, colour): below 0.30 Low, below 0.60 Medium, else High.
# The last limit is 1.01 so that a score of exactly 1.0 is still "High".
LEVELS = [(0.30, "Low", GREEN), (0.60, "Medium", AMBER), (1.01, "High", RED)]

# What the auditor has to do at each level
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


def level_for(score):
    """Turns a score (0-1) into a risk level, e.g. 0.45 -> ("Medium", "amber").

    Goes through LEVELS from low to high and returns the first level whose
    upper limit is above the score."""
    for limit, name, colour in LEVELS:
        if score < limit:
            return name, colour
    return LEVELS[-1][1], LEVELS[-1][2]            # safety net: scores above 1 count as "High"


def assess(years, answers, liquidity_result=None, ml_score=None, weights=None, profile=None):
    """Combines the results of all modules into one going concern risk.

    years             list of financial years, oldest first (from the ratio analysis)
    answers           dict question id -> True (Yes) / False (No)
    liquidity_result  result of the liquidity planner (None if not prepared)
    ml_score          bankruptcy probability of the ML model, 0-1 (None if not trained)
    weights           dict with the weights of the three sources (None = default)
    profile           company profile (adds warning signals, e.g. for start-ups)

    Returns a dict with the overall score (0-1), the risk level and its colour,
    the score of each source, the weights used, the triggered knock-out criteria,
    all warning signals and the recommendation text."""

    # --- Step 1: weights ---
    weights = dict(weights or DEFAULT_WEIGHTS)     # copy, so the slider values in the session state stay unchanged
    if ml_score is None:
        weights["ml"] = 0.0                        # model not available -> ignore
    total_w = sum(weights.values()) or 1.0         # avoids dividing by 0 if all sliders are at 0

    # --- Step 2: one score (0-1) per source ---
    latest = years[-1]
    quant = analysis.quantitative_score(years)
    qual = evaluate_questionnaire(answers)
    parts = {"quantitative": quant, "qualitative": qual["score"], "ml": ml_score or 0.0}

    # --- Step 3: weighted average ---
    # dividing by the sum of the weights normalises them, so the sliders do not have to add up to 1
    score = sum(weights[k] * parts[k] for k in parts) / total_w

    # --- Step 4: knock-out criteria ---
    # Some facts are so serious that an average would hide them, e.g. good ratios but
    # no cash in month 3.
    knock_outs = []
    if analysis.over_indebtedness(latest)["status"] == RED:
        knock_outs.append("Over-indebtedness (CO Art. 725b)")
    if liquidity_result and liquidity_result["first_shortfall_measures"] is not None:
        # shortfall even after the restructuring measures
        knock_outs.append(f"Liquidity shortfall in month {liquidity_result['first_shortfall_measures']} "
                          "(after planned restructuring measures, CO Art. 725)")
    knock_outs += [f"{q.id}: {q.text}" for q in qual["knock_outs"]]

    # --- Step 5: risk level ---
    level, colour = level_for(score)
    if knock_outs:
        level, colour = "High", RED

    # --- Step 6: warning signals (explain WHY the risk is what it is) ---
    signals = []
    for r in analysis.RATIOS:
        if r.weight and r.status(latest) == RED:   # only ratios that count for the score
            signals.append(("Ratio", f"{r.name}: {analysis.display(r, latest)}"))
    # (trends are shown on page 3, not repeated as warning signals)
    cap = analysis.capital_loss(latest)
    if cap["status"] != GREEN:
        signals.append(("Legal", cap["result"] + " (CO Art. 725a)"))
    for q in qual["yes"]:
        signals.append(("Questionnaire", f"{q.id}: {q.text}"))
    if profile:
        signals += profile_signals(profile)        # e.g. young company, dependence on the group

    return {"score": score, "level": level, "colour": colour, "parts": parts,
            "weights": weights, "knock_outs": knock_outs, "signals": signals,
            "text": LEVEL_TEXT[level], "questionnaire": qual}


def score_breakdown(result):
    """Shows how the overall score is made up.

    result: the dict returned by assess().
    Returns one dict per source with its score, its normalised weight and its
    contribution to the overall score (weight x score). The contributions add
    up to the overall score, e.g. 0.35 (ratios) + 0.25 (questionnaire) = 0.60."""
    total_w = sum(result["weights"].values()) or 1.0
    rows = []
    for key, label in COMPONENT_LABELS.items():
        weight = result["weights"][key] / total_w
        rows.append({"key": key, "label": label, "score": result["parts"][key],
                     "weight": weight, "contribution": weight * result["parts"][key]})
    return rows


def weight_sensitivity(result, steps=11):
    """Tests whether the risk level depends on the chosen weighting.

    The weighting between ratios and questionnaire is a judgement call. This
    function therefore recalculates the score for every split between the two,
    from "questionnaire only" (ratio share 0 %) to "ratios only" (100 %).
    The share of the ML model stays as chosen by the auditor.

    result: the dict returned by assess().
    Returns a list of dicts: ratio_share (0-1), score (0-1), level.
    If the level is the same in every row, the result is robust."""
    parts = result["parts"]
    total_w = sum(result["weights"].values()) or 1.0
    ml_share = result["weights"]["ml"] / total_w
    rest = 1.0 - ml_share                                      # split between ratios and questionnaire
    rows = []
    for i in range(steps):
        ratio_share = i / (steps - 1)                          # 0.0, 0.1, ..., 1.0 for steps = 11
        score = (rest * ratio_share * parts["quantitative"]
                 + rest * (1 - ratio_share) * parts["qualitative"]
                 + ml_share * parts["ml"])
        level = "High" if result["knock_outs"] else level_for(score)[0]   # knock-outs always win
        rows.append({"ratio_share": ratio_share, "score": score, "level": level})
    return rows


# --- Auditor's conclusion -> implication for the auditor's report (ISA 570.21-23) ---
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
