# Going Concern Audit

A Streamlit web app that supports auditors in the **going concern procedure under ISA 570**
and the Swiss Code of Obligations (CO Art. 725–725b).

**Problem:** In every audit the auditor must conclude whether the company can continue as a
going concern. Annual reports look different in every company, and ratios, ISA 570
checklists, liquidity plans and documentation are usually spread over several spreadsheets.
**Solution:** one app that guides the auditor from the uploaded annual report to a documented
conclusion.

---

## Folder structure

```
going-concern-audit/
├── app.py                 Start of the app: navigation and sidebar
├── shared.py              Things all pages need (session state, traffic-light card)
│
├── pages/                 WHAT THE USER SEES – one file per step of the audit
│   ├── 0_home.py
│   ├── 1_company_profile.py
│   ├── 2_financial_statements.py
│   ├── 3_ratio_analysis.py
│   ├── 4_questionnaire.py
│   ├── 5_liquidity_planner.py
│   ├── 6_bankruptcy_model.py
│   ├── 7_assessment_report.py
│   └── 8_audit_files.py
│
├── logic/                 THE CALCULATIONS – no layout, only business logic
│   ├── data_input.py      Standard format, company profile, sample companies, AI import
│   ├── analysis.py        Legal tests (CO), ratios, trends, liquidity plan
│   ├── assessment.py      ISA 570 questionnaire, overall risk, auditor's conclusion
│   ├── ml_model.py        Machine learning: training and prediction
│   └── documentation.py   PDF working paper and database (audit files)
│
├── data/                  Polish dataset, trained model and database are stored here
├── .streamlit/            Design (config.toml) and API key (secrets.toml)
├── requirements.txt       Python packages
└── README.md              This file
```

**Rule of thumb:** If you want to change *what is shown*, open `pages/`.
If you want to change *how something is calculated*, open `logic/`.

---

## Setup (Mac, Python 3.14)

Type these commands in the VS Code terminal (*Terminal → New Terminal*):

```bash
python3.14 -m venv .venv          # 1. create the environment (only once)
source .venv/bin/activate         # 2. activate it (every time)
pip install -r requirements.txt   # 3. install the packages (only once)
streamlit run app.py              # 4. start the app
```

### AI import (Claude API)
1. Create an API key on https://console.anthropic.com.
2. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and insert the key.
3. Never upload `secrets.toml` to GitHub (it is excluded in `.gitignore`).

### Machine learning model
1. Download the *Polish Companies Bankruptcy* dataset:
   https://archive.ics.uci.edu/dataset/365/polish+companies+bankruptcy+data
2. Copy `1year.arff` … `5year.arff` into the folder `data/`.
3. Open page **6 · Bankruptcy model** in the app and click **Train model now**.

Without API key and model the app still works with the sample companies.

---

## The audit procedure in the app

| Step | What happens |
|---|---|
| 1 Company profile | Engagement data, industry, size, group. The industry changes the ratio thresholds; the size check suggests the audit type (CO Art. 727). |
| 2 Financial statements | Upload PDF/Excel (3–5 years). The Claude API converts it into a standard format; the auditor reviews every figure. |
| 3 Ratio analysis | Capital loss, over-indebtedness, 11 ratios with traffic lights, trends over 3–5 years |
| 4 Questionnaire | 20 yes/no questions from ISA 570 for the next 12 months, with knock-out criteria |
| 5 Liquidity planner | 12-month plan with and without restructuring measures (CO Art. 725) |
| 6 Bankruptcy model | Own ML model (logistic regression) with explanation per ratio |
| 7 Assessment & report | Overall risk, auditor's conclusion → auditor's report, PDF download, save |
| Audit files | Saved assessments in a SQLite database |

## Grading requirements – where to find them

| Requirement | Where |
|---|---|
| 1. Problem statement | Home page, this README |
| 2. API / database | Claude API (`logic/data_input.py`), SQLite (`logic/documentation.py`) |
| 3. Visualisation | Traffic lights, trend charts, liquidity chart, ML explanation, risk gauge |
| 4. User interaction | Company profile, upload, editable tables, questionnaire, liquidity planner, weight sliders, conclusion, PDF, save/load |
| 5. Machine learning | `logic/ml_model.py`, page 6 |
| 6. Comments | All files |
| 7. Contributions & GenAI | Table below (present it in the video) |
| 8. Video | 4 minutes, own voice |

## Contribution matrix

| Part | Files | Franco | Juled | Maiara | Nicole | Zehra |
|---|---|---|---|---|---|---|
| Concept, problem statement | `0_home.py`, README | | | | |x|
| Company profile | `1_company_profile.py`, `data_input.py` | | | | |x|
| Financial statements & AI | `2_financial_statements.py`, `data_input.py` |x| | | |x|
| Ratios & legal tests | `3_ratio_analysis.py`, `analysis.py` | |x| | | |
| ISA 570 questionnaire | `4_questionnaire.py`, `assessment.py` | | | |x| |
| Liquidity planner | `5_liquidity_planner.py`, `analysis.py` | | |x| | |
| Machine learning | `6_bankruptcy_model.py`, `ml_model.py` | | | | | |
| Assessment, PDF, database | `7_assessment_report.py`, `8_audit_files.py`, `assessment.py`, `documentation.py` | | | | |x|
| Video | – | | | | | |

**Use of generative AI** – answer in the video: Which tools did we use? For which parts?
What did we change or write ourselves? How did we check the AI output? What did we learn?

## Limitations

- Ratio thresholds (also per industry) are rules of thumb; the auditor decides.
- Over-indebtedness is tested at book values only (law: going concern and liquidation values).
- The ML model is trained on Polish companies (2000–2013); transfer to Swiss firms is limited.
- AI output can be wrong – every figure must be checked against the annual report.
