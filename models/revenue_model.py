from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

MODEL_PATH = Path(__file__).with_name("revenue_model.pkl")
FEATURES = ["month", "year", "time_index", "lag_1", "lag_2", "rolling_3"]


def prepare_monthly_sales(sales):
    frame = pd.DataFrame([{"date": s.sale_date, "revenue": s.revenue} for s in sales])
    if frame.empty:
        return pd.DataFrame(columns=["month", "revenue"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna().set_index("date").sort_index()
    return frame["revenue"].resample("MS").sum().rename("revenue").reset_index().rename(columns={"date": "month"})


def create_features(monthly):
    frame = monthly.copy().sort_values("month").reset_index(drop=True)
    frame["month"] = pd.to_datetime(frame["month"])
    frame["year"] = frame["month"].dt.year
    frame["month"] = frame["month"].dt.month
    frame["time_index"] = np.arange(len(frame))
    frame["lag_1"] = frame["revenue"].shift(1)
    frame["lag_2"] = frame["revenue"].shift(2)
    frame["rolling_3"] = frame["revenue"].shift(1).rolling(3, min_periods=2).mean()
    return frame.dropna().reset_index(drop=True)


def train_revenue_model(sales, save=True, save_path=None):
    try:
        from xgboost import XGBRegressor
    except ImportError as exc:
        raise ValueError("XGBoost is not installed. Install project dependencies with pip install -r requirements.txt.") from exc
    monthly = prepare_monthly_sales(sales)
    if len(monthly) < 6:
        raise ValueError("At least 6 months of sales history are required to train a revenue model.")
    data = create_features(monthly)
    if len(data) < 4:
        raise ValueError("At least 6 months of sales history are required to evaluate a revenue model.")
    split = max(2, int(len(data) * .8))
    model = XGBRegressor(n_estimators=120, max_depth=2, learning_rate=.04, objective="reg:squarederror", random_state=42)
    model.fit(data[FEATURES].iloc[:split], data["revenue"].iloc[:split])
    pred = model.predict(data[FEATURES].iloc[split:])
    actual = data["revenue"].iloc[split:]
    metrics = {"mae": float(mean_absolute_error(actual, pred)), "rmse": float(np.sqrt(mean_squared_error(actual, pred))),
               "r2": float(r2_score(actual, pred)) if len(actual) > 1 else None}
    model.fit(data[FEATURES], data["revenue"])
    if save:
        output = Path(save_path) if save_path else MODEL_PATH
        output.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, output)
    return model, metrics


def predict_next_month(sales):
    monthly = prepare_monthly_sales(sales)
    if len(monthly) < 6:
        return {"available": False, "reason": "Insufficient historical data. Provide at least 6 months of sales data."}
    try:
        model, metrics = train_revenue_model(sales, save=False)
    except ValueError as exc:
        return {"available": False, "reason": str(exc)}
    values = monthly["revenue"].to_list()
    last = pd.Timestamp(monthly.iloc[-1]["month"])
    next_month = last + pd.offsets.MonthBegin(1)
    row = pd.DataFrame([{"month": next_month.month, "year": next_month.year, "time_index": len(monthly),
                         "lag_1": values[-1], "lag_2": values[-2], "rolling_3": np.mean(values[-3:])}])
    amount = max(0, float(model.predict(row[FEATURES])[0]))
    return {"available": True, "current": values[-1], "predicted": amount,
            "growth_pct": (amount - values[-1]) / values[-1] * 100 if values[-1] else None, "metrics": metrics}
