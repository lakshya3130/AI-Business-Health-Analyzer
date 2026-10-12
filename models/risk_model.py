from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

MODEL_PATH = Path(__file__).with_name("risk_model.pkl")
FEATURES = ["revenue", "expenses", "profit", "margin", "revenue_growth", "expense_growth"]


def financial_history(sales, expenses):
    months = {}
    for row in sales:
        key = row.sale_date.strftime("%Y-%m")
        months.setdefault(key, [0.0, 0.0])[0] += row.revenue
    for row in expenses:
        key = row.expense_date.strftime("%Y-%m")
        months.setdefault(key, [0.0, 0.0])[1] += row.amount
    frame = pd.DataFrame([{"month": k, "revenue": v[0], "expenses": v[1]} for k, v in sorted(months.items())])
    if frame.empty:
        return frame
    frame["profit"] = frame.revenue - frame.expenses
    frame["margin"] = np.where(frame.revenue != 0, frame.profit / frame.revenue * 100, 0)
    frame["revenue_growth"] = frame.revenue.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0) * 100
    frame["expense_growth"] = frame.expenses.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0) * 100
    # Documented proxy label: sustained operating losses, thin margins, or sharp revenue contraction.
    frame["distress"] = ((frame.profit < 0) | ((frame.margin < 5) & (frame.revenue_growth < 0)) |
                          ((frame.expense_growth > 30) & (frame.revenue_growth < 0))).astype(int)
    return frame


def train_risk_model(sales, expenses, save=True, save_path=None):
    data = financial_history(sales, expenses)
    if len(data) < 8 or data.distress.nunique() < 2:
        raise ValueError("Risk model needs at least 8 months of financial history containing both stable and stressed conditions.")
    split = max(6, int(len(data) * .8))
    if split >= len(data):
        split = len(data) - 1
    if data.distress.iloc[:split].nunique() < 2:
        raise ValueError("The chronological training window does not include both stable and stressed periods yet. Add more varied history.")
    model = make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42))
    model.fit(data[FEATURES].iloc[:split], data.distress.iloc[:split])
    test_x, test_y = data[FEATURES].iloc[split:], data.distress.iloc[split:]
    pred = model.predict(test_x)
    prob = model.predict_proba(test_x)[:, 1]
    metrics = {"accuracy": float(accuracy_score(test_y, pred)), "precision": float(precision_score(test_y, pred, zero_division=0)),
               "recall": float(recall_score(test_y, pred, zero_division=0)), "f1": float(f1_score(test_y, pred, zero_division=0)),
               "roc_auc": float(roc_auc_score(test_y, prob)) if test_y.nunique() > 1 else None}
    model.fit(data[FEATURES], data.distress)
    if save:
        output = Path(save_path) if save_path else MODEL_PATH
        output.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, output)
    return model, metrics


def predict_risk(sales, expenses):
    data = financial_history(sales, expenses)
    if len(data) < 8 or data.distress.nunique() < 2:
        return {"available": False, "reason": "Insufficient history for risk modeling: provide at least 8 months with varied financial conditions."}
    try:
        model, metrics = train_risk_model(sales, expenses, save=False)
    except ValueError as exc:
        return {"available": False, "reason": str(exc)}
    probability = float(model.predict_proba(data[FEATURES].tail(1))[0, 1])
    return {"available": True, "probability": probability,
            "level": "High" if probability >= .65 else "Medium" if probability >= .35 else "Low", "metrics": metrics}
