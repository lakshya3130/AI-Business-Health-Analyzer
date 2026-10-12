from datetime import date

import pandas as pd


REQUIRED = {
    "sales": {"date": "sale_date", "sale_date": "sale_date", "product": "product", "quantity": "quantity", "revenue": "revenue"},
    "expenses": {"date": "expense_date", "expense_date": "expense_date", "category": "category", "amount": "amount"},
    "inventory": {"product": "product", "current_stock": "current_stock", "stock": "current_stock", "reorder_level": "reorder_level", "unit_cost": "unit_cost"},
    "employees": {"name": "name", "salary": "salary", "joining_date": "joining_date", "date": "joining_date"},
}


def clean_frame(frame, kind):
    frame = frame.copy()
    uploaded_count = len(frame)
    frame.columns = [str(c).strip().lower().replace(" ", "_") for c in frame.columns]
    mapping = {col: REQUIRED[kind][col] for col in frame.columns if col in REQUIRED[kind]}
    frame = frame.rename(columns=mapping)
    required = {"sales": {"sale_date", "product", "quantity", "revenue"},
                "expenses": {"expense_date", "category", "amount"},
                "inventory": {"product", "current_stock", "reorder_level", "unit_cost"},
                "employees": {"name", "salary", "joining_date"}}[kind]
    missing = required - set(frame.columns)
    if missing:
        raise ValueError("Required columns missing: " + ", ".join(sorted(missing)))
    duplicate_count = int(frame.duplicated().sum())
    frame = frame.drop_duplicates()
    frame["_original_index"] = range(len(frame))
    text_cols = [c for c in ("product", "category", "name") if c in frame]
    for col in text_cols:
        frame[col] = frame[col].fillna("").astype(str).str.strip()
    date_col = {"sales": "sale_date", "expenses": "expense_date", "employees": "joining_date"}.get(kind)
    if date_col:
        frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce").dt.date
    numeric = {"sales": ["quantity", "revenue"], "expenses": ["amount"],
               "inventory": ["current_stock", "reorder_level", "unit_cost"], "employees": ["salary"]}[kind]
    for col in numeric:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    valid = pd.Series(True, index=frame.index)
    if date_col:
        valid &= frame[date_col].notna()
    for col in text_cols:
        valid &= frame[col].ne("")
    for col in numeric:
        valid &= frame[col].notna() & (frame[col] >= 0)
    if kind == "sales":
        valid &= frame.quantity.gt(0)
    good = frame.loc[valid].drop(columns="_original_index")
    return good.to_dict(orient="records"), {"uploaded": uploaded_count, "valid": len(good),
                                               "invalid": len(frame) - len(good),
                                               "duplicates": duplicate_count}


def parse_upload(file_storage):
    name = file_storage.filename or ""
    if "." not in name or name.rsplit(".", 1)[1].lower() not in {"csv", "xlsx"}:
        raise ValueError("Choose a CSV or XLSX file.")
    try:
        frame = pd.read_csv(file_storage) if name.lower().endswith(".csv") else pd.read_excel(file_storage)
    except Exception as exc:
        raise ValueError("The file could not be read. Check that it is a valid CSV or XLSX file.") from exc
    if frame.empty:
        raise ValueError("The uploaded file is empty.")
    return frame
