from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

MODEL_PATH = Path(__file__).with_name("profit_model.pkl")
FEATURES = ["month", "time_index", "revenue", "expenses", "lag_profit"]


def prepare_monthly_financials(sales, expenses):
    months = {}
    for sale in sales:
        key = sale.sale_date.strftime("%Y-%m")
        months.setdefault(key, {"revenue": 0.0, "expenses": 0.0})["revenue"] += sale.revenue
    for expense in expenses:
        key = expense.expense_date.strftime("%Y-%m")
        months.setdefault(key, {"revenue": 0.0, "expenses": 0.0})["expenses"] += expense.amount
    rows = [{"month": pd.Timestamp(key + "-01"), **value, "profit": value["revenue"] - value["expenses"]}
            for key, value in sorted(months.items())]
    return pd.DataFrame(rows)


def create_features(monthly):
    frame = monthly.copy().sort_values("month").reset_index(drop=True)
    if frame.empty:
        return frame
    frame["month"] = pd.to_datetime(frame["month"]).dt.month
    frame["time_index"] = np.arange(len(frame))
    frame["lag_profit"] = frame["profit"].shift(1)
    return frame.dropna().reset_index(drop=True)


def train_profit_model(sales, expenses, save=True, save_path=None):
    monthly = prepare_monthly_financials(sales, expenses)
    if len(monthly) < 6:
        raise ValueError("At least 6 months of financial history are required to train a profit model.")
    data = create_features(monthly)
    split = max(2, int(len(data) * .8))
    model = RandomForestRegressor(n_estimators=150, min_samples_leaf=2, random_state=42)
    model.fit(data[FEATURES].iloc[:split], data["profit"].iloc[:split])
    pred, actual = model.predict(data[FEATURES].iloc[split:]), data["profit"].iloc[split:]
    metrics = {"mae": float(mean_absolute_error(actual, pred)), "rmse": float(np.sqrt(mean_squared_error(actual, pred))),
               "r2": float(r2_score(actual, pred)) if len(actual) > 1 else None}
    model.fit(data[FEATURES], data["profit"])
    if save:
        output = Path(save_path) if save_path else MODEL_PATH
        output.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, output)
    return model, metrics


def predict_next_month_profit(sales, expenses):
    monthly = prepare_monthly_financials(sales, expenses)
    if len(monthly) < 6:
        return {"available": False, "reason": "Insufficient historical data. Provide at least 6 months of sales and expense data."}
    model, metrics = train_profit_model(sales, expenses, save=False)
    last = monthly.iloc[-1]
    row = pd.DataFrame([{"month": (last["month"] + pd.offsets.MonthBegin(1)).month, "time_index": len(monthly),
                         "revenue": last["revenue"], "expenses": last["expenses"], "lag_profit": last["profit"]}])
    predicted = float(model.predict(row[FEATURES])[0])
    return {"available": True, "current": float(last["profit"]), "predicted": predicted,
            "metrics": metrics}
