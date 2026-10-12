from collections import defaultdict
from datetime import date


def analyze(inventory, sales):
    sold = defaultdict(float)
    for sale in sales:
        sold[sale.product.strip().casefold()] += sale.quantity
    today = date.today()
    rows = []
    for item in inventory:
        age_days = max(1, (today - min((s.sale_date for s in sales), default=today)).days + 1)
        daily = sold[item.product.strip().casefold()] / age_days
        coverage = item.current_stock / daily if daily else None
        status = "Reorder" if item.current_stock <= item.reorder_level else "At risk" if coverage is not None and coverage <= 14 else "Overstocked" if coverage is not None and coverage > 90 else "Healthy"
        rows.append({"product": item.product, "stock": item.current_stock, "reorder_level": item.reorder_level,
                     "daily_demand": daily, "coverage_days": coverage, "units_sold": sold[item.product.strip().casefold()], "status": status})
    return sorted(rows, key=lambda row: (row["status"] not in ("Reorder", "At risk"), -row["units_sold"]))
