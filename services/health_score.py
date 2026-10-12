def calculate(financial, inventory_rows, risk_probability=None):
    growth = financial.get("revenue_growth")
    margin = financial["profit_margin"]
    growth_score = 10 if growth is None else max(0, min(20, 10 + growth * 0.25))
    margin_score = max(0, min(20, margin))
    cash_score = 20 if financial["cash_flow"] == "Positive" else 10 if financial["cash_flow"] == "Neutral" else 0
    if inventory_rows:
        risk_count = sum(1 for row in inventory_rows if row["status"] in ("Reorder", "At risk"))
        inventory_score = max(0, 20 * (1 - risk_count / len(inventory_rows)))
    else:
        inventory_score = 10
    stability_score = 10 if risk_probability is None else max(0, min(20, 20 * (1 - risk_probability)))
    score = round(growth_score + margin_score + cash_score + inventory_score + stability_score)
    category = "Excellent" if score >= 80 else "Good" if score >= 60 else "Moderate" if score >= 40 else "Poor"
    return {"score": score, "category": category, "components": {
        "Revenue growth": round(growth_score), "Profit margin": round(margin_score),
        "Cash flow": cash_score, "Inventory health": round(inventory_score),
        "Financial stability": round(stability_score)}}
