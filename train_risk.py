import argparse
from pathlib import Path

from models.risk_model import train_risk_model


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train a financial stress model for one company.")
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
        path = Path("models") / f"risk_model_company_{company.id}.pkl"
        _, metrics = train_risk_model(sales, expenses, save_path=path)
    print("Risk model saved. Chronological holdout metrics:", metrics)
