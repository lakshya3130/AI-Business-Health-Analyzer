from collections import defaultdict


def analyze(expenses, threshold=20):
    by_category, by_month = defaultdict(float), defaultdict(float)
    for item in expenses:
        by_category[item.category] += item.amount
        by_month[(item.expense_date.strftime("%Y-%m"), item.category)] += item.amount
    months = sorted({m for m, _ in by_month})
    changes = []
    if len(months) > 1:
        previous, current = months[-2:]
        for category in sorted({c for _, c in by_month}):
            old, new = by_month[(previous, category)], by_month[(current, category)]
            pct = (new - old) / old * 100 if old else None
            if pct is not None and abs(pct) >= threshold:
                changes.append({"category": category, "previous": old, "current": new, "change_pct": pct})
    return {"by_category": dict(by_category), "monthly": dict(by_month),
            "highest": sorted(by_category.items(), key=lambda item: item[1], reverse=True), "changes": changes}
