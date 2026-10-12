from collections import defaultdict
from datetime import date

import pandas as pd


def monthly_financials(sales, expenses):
    rev = defaultdict(float)
    cost = defaultdict(float)
    for item in sales:
        rev[item.sale_date.strftime("%Y-%m")] += item.revenue
    for item in expenses:
        cost[item.expense_date.strftime("%Y-%m")] += item.amount
    keys = sorted(set(rev) | set(cost))
    return [{"month": k, "revenue": rev[k], "expenses": cost[k], "profit": rev[k] - cost[k]}
            for k in keys]


def analyze(sales, expenses):
    rows = monthly_financials(sales, expenses)
    revenue = sum(r["revenue"] for r in rows)
    costs = sum(r["expenses"] for r in rows)
    profit = revenue - costs
    last = rows[-1] if rows else {"revenue": 0, "expenses": 0, "profit": 0}
    prev = rows[-2] if len(rows) > 1 else {"revenue": 0, "expenses": 0, "profit": 0}
    def growth(current, previous):
        return ((current - previous) / previous * 100) if previous else None
    margin = profit / revenue * 100 if revenue else 0
    flow = "Positive" if profit > 0 else "Negative" if profit < 0 else "Neutral"
    return {"monthly": rows, "total_revenue": revenue, "total_expenses": costs,
            "total_profit": profit, "profit_margin": margin,
            "revenue_growth": growth(last["revenue"], prev["revenue"]),
            "expense_growth": growth(last["expenses"], prev["expenses"]),
            "current_revenue": last["revenue"], "current_expenses": last["expenses"],
            "current_profit": last["profit"], "cash_flow": flow}
