def recommendations(financial, expenses, inventory, predictions, risk, health):
    items = []
    rg, eg = financial.get("revenue_growth"), financial.get("expense_growth")
    if rg is not None and eg is not None and eg > rg:
        items.append(f"Expenses grew {eg:.1f}% while revenue grew {rg:.1f}%; review the fastest-growing cost categories before expanding spend.")
    if financial["profit_margin"] < 10:
        items.append(f"Profit margin is {financial['profit_margin']:.1f}%; review pricing and controllable operating costs to improve the amount retained from each sale.")
    for change in expenses["changes"]:
        if change["change_pct"] > 0:
            items.append(f"{change['category']} expenses increased {change['change_pct']:.1f}% month over month; inspect recent invoices and usage.")
    urgent = [row for row in inventory if row["status"] in ("Reorder", "At risk")]
    if urgent:
        names = ", ".join(row["product"] for row in urgent[:3])
        items.append(f"Check replenishment for {names}; current stock is at or near the configured reorder point or estimated demand cover is short.")
    if predictions.get("profit", {}).get("available") and predictions["profit"]["predicted"] < predictions["profit"]["current"]:
        items.append("The model projects lower profit next month; review the revenue and expense assumptions behind the recent trend.")
    if risk.get("available") and risk["level"] == "High":
        items.append("The financial risk model flags elevated stress; prioritize cash preservation and review upcoming obligations with a qualified adviser.")
    if not items:
        items.append(f"Current indicators are broadly stable (health score {health['score']}/100). Keep reviewing monthly margins, cash flow, and stock cover.")
    return items
