"""
MACHINE LEARNING - our own bankruptcy prediction model.

Trained on the Polish Companies Bankruptcy dataset (UCI). Uses only ratios that
can be computed exactly from our standardised financial statements.
"""

# Training, saving and prediction of the bankruptcy model. Used on page 6 and, via shared.ml_score,
# in the overall assessment (page 7) and the PDF.
# Use of generative AI:
# - Code: parts of the code in this file were written with the help of Claude (Anthropic). We reviewed, tested and adjusted them.
# - Comments: Claude was used as support for writing the comments and making sure that the structure fits. We checked and partly adjusted them.

import glob
import math
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


# --- Model and features ---
# Dataset: UCI, Tomczak et al. 2016, 64 ratios Attr1-Attr64.
# We only use ratios that can be computed EXACTLY from our standardised statements, so the model
# sees the same kind of numbers for an uploaded client as during training.
# Logistic regression because it is interpretable (one weight per ratio, which an auditor can
# document); a random forest is trained as a benchmark only.

# ROOT = project folder (two levels above this file)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
MODEL_PATH = os.path.join(DATA_DIR, "bankruptcy_model.joblib")


# nan instead of an error if the denominator is 0; filled in later by the imputer (median)
def _d(a, b):
    return a / b if b else float("nan")


# Polish attribute -> (description, formula on a FinancialYear).
# These 13 of the 64 Polish ratios are the features of the model.
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
FEATURE_NAMES = list(FEATURES)                 # fixed column order for training and prediction


class Clipper(BaseEstimator, TransformerMixin):
    """Caps extreme values at the 1st/99th percentile. The Polish data contains
    huge outliers (e.g. division by almost zero) that would distort the model."""

    def __init__(self, low=0.01, high=0.99):
        self.low = low
        self.high = high

    # limits are learned from the training data only and reused for the client
    def fit(self, X, y=None):
        X = np.asarray(X, dtype=float)
        self.lo_ = np.nanquantile(X, self.low, axis=0)
        self.hi_ = np.nanquantile(X, self.high, axis=0)
        return self

    def transform(self, X):
        return np.clip(np.asarray(X, dtype=float), self.lo_, self.hi_)


# The pipeline applies the same preparation steps to the training data and later to the client.
def build_pipeline():
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("clip", Clipper()),
        ("scale", StandardScaler()),                    # needed so the coefficients are comparable
        # class_weight="balanced": only ~5 % of the firms went bankrupt
        ("logreg", LogisticRegression(class_weight="balanced", max_iter=3000)),
    ])


def load_polish_data(folder=DATA_DIR):
    """Loads 1year.arff ... 5year.arff (or CSV files with columns Attr1..Attr64
    and class) from the data folder."""
    from scipy.io import arff

    frames = []
    for path in sorted(glob.glob(os.path.join(folder, "*.arff"))):
        raw, _ = arff.loadarff(path)
        df = pd.DataFrame(raw)
        # target: 1 = bankrupt, 0 = active; stored as bytes in the arff file
        df["class"] = df["class"].apply(lambda v: int(v.decode() if isinstance(v, bytes) else v))
        frames.append(df)
    # CSV variant: "?" = missing value, column names are unified to Attr1..Attr64
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
    return pd.concat(frames, ignore_index=True)


def load_model():
    """Returns the trained model package or None if the model was not trained yet."""
    return joblib.load(MODEL_PATH) if os.path.exists(MODEL_PATH) else None


# One row with the 13 ratios of one financial year; ratios that cannot be computed become nan.
def features_for(fy):
    row = {}
    for name, (_, fn) in FEATURES.items():
        v = fn(fy)
        row[name] = v if v is not None and math.isfinite(v) else np.nan
    return pd.DataFrame([row], columns=FEATURE_NAMES)


def predict(package, fy):
    """Risk score (0-1) for one financial year plus the contribution of each
    ratio (coefficient x standardised value) to explain the result."""
    pipe = package["pipeline"]
    X = features_for(fy)
    score = float(pipe.predict_proba(X)[0, 1])    # probability of class 1 (= bankrupt)
    z = pipe[:-1].transform(X)[0]                 # all steps except the model -> standardised values
    coef = pipe.named_steps["logreg"].coef_[0]
    # positive contribution = increases the risk
    contrib = pd.DataFrame({
        "Feature": FEATURE_NAMES,
        "Description": [FEATURES[f][0] for f in FEATURE_NAMES],
        "Value": X.iloc[0].values,
        "Contribution": coef * z,
    }).sort_values("Contribution", ascending=False)
    return score, contrib


# --- Training (button on page 6, or in the terminal: python -m logic.ml_model) ---
# 1. load data  2. split 75/25  3. train logistic regression + random forest benchmark
# 4. evaluate on the test data  5. retrain on all data and save

def training_data_available():
    return bool(glob.glob(os.path.join(DATA_DIR, "*.arff")) or glob.glob(os.path.join(DATA_DIR, "*.csv")))


def train():
    df = load_polish_data()
    X, y = df[FEATURE_NAMES], df["class"].astype(int)
    # stratify keeps the share of bankrupt firms equal in both parts; random_state makes it reproducible
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=42)

    logreg = build_pipeline().fit(X_tr, y_tr)
    p_lr = logreg.predict_proba(X_te)[:, 1]
    pred = (p_lr >= 0.5).astype(int)              # from 50 % on the firm counts as "bankrupt"

    # Benchmark only: usually more accurate, but a "black box"
    rf = Pipeline([("impute", SimpleImputer(strategy="median")),
                   ("rf", RandomForestClassifier(n_estimators=300, min_samples_leaf=5,
                                                 class_weight="balanced", n_jobs=-1,
                                                 random_state=42))]).fit(X_tr, y_tr)

    # Measured on the TEST data (not seen during training):
    #   ROC-AUC 1.0 = perfect ranking, 0.5 = random; recall = share of bankrupt firms detected
    metrics = {"auc_logreg": roc_auc_score(y_te, p_lr), "recall_logreg": recall_score(y_te, pred),
               "auc_rf": roc_auc_score(y_te, rf.predict_proba(X_te)[:, 1]),
               "confusion_matrix": confusion_matrix(y_te, pred).tolist(),
               "n": len(df), "bankrupt_share": float(y.mean())}

    # The saved model is trained on all data; the metrics above come from the split
    joblib.dump({"pipeline": build_pipeline().fit(X, y), "metrics": metrics}, MODEL_PATH)
    return metrics


if __name__ == "__main__":
    # Import via the package name, so the saved model refers to logic.ml_model
    # (and not to "__main__") and can be loaded by the app later.
    from logic import ml_model
    m = ml_model.train()
    print(f"Trained on {m['n']:,} companies | ROC-AUC {m['auc_logreg']:.3f} "
          f"(random forest {m['auc_rf']:.3f}) | saved to {MODEL_PATH}")
