import argparse
from pathlib import Path

from models.profit_model import train_profit_model


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train a profit forecaster for one company.")
    parser.add_argument("--company-id", type=int, required=True)
    args = parser.parse_args()
    from app import app
    from database import db
    from database.models import Company, Expense, Sale

    with app.app_context():
        company = db.session.get(Company, args.company_id)
        if not company:
            raise SystemExit("Company ID was not found.")
        sales = Sale.query.filter_by(company_id=company.id).order_by(Sale.sale_date).all()
        expenses = Expense.query.filter_by(company_id=company.id).order_by(Expense.expense_date).all()
        path = Path("models") / f"profit_model_company_{company.id}.pkl"
        _, metrics = train_profit_model(sales, expenses, save_path=path)
    print("Profit model saved. Holdout metrics:", metrics)
