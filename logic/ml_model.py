"""
MACHINE LEARNING - our own bankruptcy prediction model.

Trained on the Polish Companies Bankruptcy dataset (UCI). Uses only ratios that
can be computed exactly from our standardised financial statements.
"""

# Use of generative AI: the comments in this file were written with the help of Claude (Anthropic) and checked by us.

import glob                                   # find files by pattern, e.g. "*.arff"
import math                                   # isfinite: test for infinite values
import os                                     # file paths

import joblib                                 # save / load the trained model as a file
import numpy as np                            # numerical arrays
import pandas as pd                           # tables (DataFrames)
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


# ============================================================================
# Machine learning: bankruptcy prediction trained on the Polish Companies
# Bankruptcy dataset (UCI, Tomczak et al. 2016, 64 ratios Attr1-Attr64).
#
# We only use ratios that can be computed EXACTLY from our standardised
# financial statements, so the model sees the same kind of numbers when it is
# applied to an uploaded company as during training.
#
# Model: logistic regression (interpretable: every ratio gets a weight, which
# an auditor can understand and document). A random forest is trained as a
# benchmark only.
# ============================================================================

# Paths: ROOT = project folder (two levels above this file), the data and the model are stored in data/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
MODEL_PATH = os.path.join(DATA_DIR, "bankruptcy_model.joblib")   # file of the trained model


# Safe division: returns "not a number" (nan) instead of an error if the denominator is 0.
# nan values are filled in later by the imputer (median).
def _d(a, b):
    return a / b if b else float("nan")


# Polish attribute -> (description, formula on a FinancialYear)
# These 13 of the 64 Polish ratios are the input variables (features) of the model.
# "lambda f: ..." is a small function: it receives one financial year f of the client
# and computes the ratio from our standardised line items.
FEATURES = {
    "Attr1": ("Net income / total assets", lambda f: _d(f.net_income, f.total_assets)),
    "Attr2": ("Total liabilities / total assets", lambda f: _d(f.total_liabilities, f.total_assets)),
    "Attr3": ("Working capital / total assets",
              lambda f: _d(f.current_assets - f.current_liabilities, f.total_assets)),
    "Attr4": ("Current assets / short-term liabilities",
              lambda f: _d(f.current_assets, f.current_liabilities)),
    "Attr7": ("EBIT / total assets", lambda f: _d(f.ebit, f.total_assets)),
    "Attr9": ("Sales / total assets", lambda f: _d(f.revenue, f.total_assets)),
    "Attr10": ("Equity / total assets", lambda f: _d(f.equity, f.total_assets)),
    "Attr26": ("(Net income + depreciation) / total liabilities",
               lambda f: _d(f.net_income + f.depreciation, f.total_liabilities)),
    "Attr27": ("Operating profit / financial expenses", lambda f: _d(f.ebit, f.interest_expense)),
    "Attr40": ("(Current assets - inventory - receivables) / short-term liabilities",
               lambda f: _d(f.current_assets - f.inventories - f.receivables, f.current_liabilities)),
    "Attr44": ("Receivables x 365 / sales", lambda f: _d(f.receivables * 365, f.revenue)),
    "Attr46": ("(Current assets - inventory) / short-term liabilities",
               lambda f: _d(f.current_assets - f.inventories, f.current_liabilities)),
    "Attr51": ("Short-term liabilities / total assets",
               lambda f: _d(f.current_liabilities, f.total_assets)),
}
FEATURE_NAMES = list(FEATURES)                 # ["Attr1", "Attr2", ...] in a fixed order


class Clipper(BaseEstimator, TransformerMixin):
    """Caps extreme values at the 1st/99th percentile. The Polish data contains
    huge outliers (e.g. division by almost zero) that would distort the model."""

    def __init__(self, low=0.01, high=0.99):
        self.low = low
        self.high = high

    # fit = learn the limits from the training data (1st and 99th percentile of every column)
    def fit(self, X, y=None):
        X = np.asarray(X, dtype=float)
        self.lo_ = np.nanquantile(X, self.low, axis=0)
        self.hi_ = np.nanquantile(X, self.high, axis=0)
        return self

    # transform = cap every value at these limits (np.clip)
    def transform(self, X):
        return np.clip(np.asarray(X, dtype=float), self.lo_, self.hi_)


# A pipeline chains the preparation steps and the model. The same steps are applied
# automatically to the training data and later to the uploaded client.
def build_pipeline():
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),   # fill missing values
        ("clip", Clipper()),                            # cap outliers
        ("scale", StandardScaler()),                    # same scale for all ratios
        # class_weight="balanced": only ~5 % of the firms went bankrupt
        ("logreg", LogisticRegression(class_weight="balanced", max_iter=3000)),
    ])


def load_polish_data(folder=DATA_DIR):
    """Loads 1year.arff ... 5year.arff (or CSV files with columns Attr1..Attr64
    and class) from the data folder."""
    from scipy.io import arff

    frames = []                                   # one table per file
    for path in sorted(glob.glob(os.path.join(folder, "*.arff"))):   # 1year.arff ... 5year.arff
        raw, _ = arff.loadarff(path)
        df = pd.DataFrame(raw)
        # target variable: 1 = went bankrupt, 0 = still active (stored as bytes in the arff file)
        df["class"] = df["class"].apply(lambda v: int(v.decode() if isinstance(v, bytes) else v))
        frames.append(df)
    # CSV variant of the dataset: "?" = missing value, column names are unified to Attr1..Attr64
    for path in sorted(glob.glob(os.path.join(folder, "*.csv"))):
        df = pd.read_csv(path, na_values=["?"])
        df.columns = [c if c == "class" else "Attr" + "".join(ch for ch in c if ch.isdigit())
                      for c in df.columns]
        frames.append(df)
    if not frames:
        raise FileNotFoundError(
            f"No .arff or .csv files found in {folder}. Download the Polish Companies "
            "Bankruptcy dataset from the UCI repository and copy 1year.arff ... 5year.arff "
            "into the data folder.")
    return pd.concat(frames, ignore_index=True)   # all years in one table


def load_model():
    """Returns the trained model package or None if the model was not trained yet."""
    return joblib.load(MODEL_PATH) if os.path.exists(MODEL_PATH) else None


# Computes the 13 ratios for one financial year of the client (one row, same columns as in training).
# Ratios that cannot be computed (e.g. division by 0) become nan.
def features_for(fy):
    row = {}
    for name, (_, fn) in FEATURES.items():
        v = fn(fy)
        row[name] = v if v is not None and math.isfinite(v) else np.nan
    return pd.DataFrame([row], columns=FEATURE_NAMES)


def predict(package, fy):
    """Risk score (0-1) for one financial year plus the contribution of each
    ratio (coefficient x standardised value) to explain the result."""
    pipe = package["pipeline"]                    # trained pipeline
    X = features_for(fy)                          # ratios of the client
    score = float(pipe.predict_proba(X)[0, 1])    # probability of class 1 (= bankrupt)
    z = pipe[:-1].transform(X)[0]                 # all steps except the model -> standardised values
    coef = pipe.named_steps["logreg"].coef_[0]    # learned weight of every ratio
    # Contribution = weight x standardised value; positive = increases the risk
    contrib = pd.DataFrame({
        "Feature": FEATURE_NAMES,
        "Description": [FEATURES[f][0] for f in FEATURE_NAMES],
        "Value": X.iloc[0].values,
        "Contribution": coef * z,
    }).sort_values("Contribution", ascending=False)
    return score, contrib


# ============================================================================
# Training (button on page 6, or in the terminal: python -m logic.ml_model)
#   1. Load the Polish data   2. Split 75 % training / 25 % test
#   3. Train logistic regression (used) and random forest (benchmark only)
#   4. Evaluate on the test data   5. Retrain on all data and save
# ============================================================================

# True if the Polish dataset is in the data folder (page 6 then shows the button "Train model now")
def training_data_available():
    return bool(glob.glob(os.path.join(DATA_DIR, "*.arff")) or glob.glob(os.path.join(DATA_DIR, "*.csv")))


def train():
    df = load_polish_data()
    X, y = df[FEATURE_NAMES], df["class"].astype(int)     # X = 13 ratios, y = bankrupt yes/no
    # 75 % training, 25 % test; stratify=y keeps the share of bankrupt firms equal in both parts;
    # random_state=42 makes the split reproducible (same result every time)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=42)

    # Main model: logistic regression (interpretable)
    logreg = build_pipeline().fit(X_tr, y_tr)
    p_lr = logreg.predict_proba(X_te)[:, 1]       # predicted probability for the test firms
    pred = (p_lr >= 0.5).astype(int)              # from 50 % on the firm is classified as "bankrupt"

    # Benchmark: random forest (usually more accurate, but a "black box")
    rf = Pipeline([("impute", SimpleImputer(strategy="median")),
                   ("rf", RandomForestClassifier(n_estimators=300, min_samples_leaf=5,
                                                 class_weight="balanced", n_jobs=-1,
                                                 random_state=42))]).fit(X_tr, y_tr)

    # Quality measures on the TEST data (data the model has not seen):
    #   ROC-AUC: 1.0 = perfect ranking, 0.5 = random
    #   recall:  share of the bankrupt firms that the model detects
    #   confusion matrix: correct and wrong classifications
    metrics = {"auc_logreg": roc_auc_score(y_te, p_lr), "recall_logreg": recall_score(y_te, pred),
               "auc_rf": roc_auc_score(y_te, rf.predict_proba(X_te)[:, 1]),
               "confusion_matrix": confusion_matrix(y_te, pred).tolist(),
               "n": len(df), "bankrupt_share": float(y.mean())}

    # Final model trained on all data
    joblib.dump({"pipeline": build_pipeline().fit(X, y), "metrics": metrics}, MODEL_PATH)
    return metrics


if __name__ == "__main__":
    # Import via the package name, so the saved model refers to logic.ml_model
    # (and not to "__main__") and can be loaded by the app later.
    from logic import ml_model
    m = ml_model.train()
    print(f"Trained on {m['n']:,} companies | ROC-AUC {m['auc_logreg']:.3f} "
          f"(random forest {m['auc_rf']:.3f}) | saved to {MODEL_PATH}")
