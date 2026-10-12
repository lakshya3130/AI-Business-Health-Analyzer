# AI Business Health Analyzer

A standalone Flask financial intelligence application for small businesses. It supports per-user workspaces, sales and expense tracking, inventory and employee records, CSV/XLSX imports, financial analysis, time-series model forecasts, a financial stress screening estimate, recommendations, charts, and a downloadable PDF summary.

## Features

- User registration, password hashing, login sessions, CSRF protection, and company-scoped data.
- Manual data entry and validated CSV/XLSX import for sales, expenses, inventory, and employees.
- Revenue, expenses, profit, margin, growth, monthly trends, and cash flow status.
- XGBoost monthly revenue prediction, Random Forest profit prediction, and Logistic Regression financial stress model with chronological holdout metrics.
- Deterministic 0–100 health score, category expense changes, demand-based inventory coverage, and data-driven advisor recommendations.
- Responsive Chart.js dashboard and analytics, predictions and risk views, and ReportLab PDF export.

## Architecture

`app.py` wires Flask routes, authentication, and page views. `database/models.py` defines relational SQLAlchemy models. Financial calculations live in `services/`; separate estimators and feature pipelines live in `models/`. Templates and static assets provide the user interface. Training commands are `train_revenue.py`, `train_profit.py`, and `train_risk.py`.

## Requirements

- Python 3.10 or newer (Python 3.11 recommended)
- MySQL 8+ for shared/persistent deployments. For a quick local demo, the default is SQLite in `instance/business_health.db`.

## Setup on Windows

From this directory in PowerShell:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set a private `SECRET_KEY`. `DATABASE_URL` can be left unset for SQLite or set to a MySQL connection string, for example:

```text
DATABASE_URL=mysql+pymysql://username:password@localhost/business_health_analyzer?charset=utf8mb4
```

Create the MySQL database before launching:

```sql
CREATE DATABASE business_health_analyzer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Start the app:

```powershell
python app.py
```

Open `http://127.0.0.1:5000` and create a new account. There are no default credentials. Tables are initialized automatically. Do not commit `.env` or production model artifacts; `.gitignore` excludes them.

## Importing data

Choose a dataset type under **Data upload**. Files must be CSV or XLSX and no larger than 16 MB. Headers are case-insensitive; spaces are converted to underscores. Dates must be parseable, numeric values non-negative, sales quantities positive, and required labels non-empty. Exact duplicate rows within an import are removed. The result reports rows read, accepted, and rejected; rejected rows are skipped rather than silently altered. Import the supplied samples in `samples/` to explore the dashboard.

Expected columns:

| Type | Required columns |
| --- | --- |
| Sales | `sale_date`, `product`, `quantity`, `revenue` |
| Expenses | `expense_date`, `category`, `amount` |
| Inventory | `product`, `current_stock`, `reorder_level`, `unit_cost` |
| Employees | `name`, `salary`, `joining_date` |

## Machine learning methodology

Revenue is summed by month and the XGBoost regressor uses calendar month/year, time index, prior monthly revenue, and a trailing revenue mean. The Random Forest profit model predicts monthly `revenue - expenses` using month/time index and lagged profit alongside recorded revenue and expenses. Both models require at least six months, use chronological holdouts, calculate MAE, RMSE, and R² where defined, and return an explicit unavailable reason when history is inadequate.

The Logistic Regression risk model requires at least eight months and both labels. Since external insolvency labels are not expected in small-business ledgers, training labels are a transparent proxy derived only from observed financial records: a negative-profit month, or thin margin with falling revenue, or expense growth above 30% alongside falling revenue. It reports accuracy, precision, recall, F1, and ROC-AUC when the holdout supports it. This is a financial stress screening estimate, not a true bankruptcy probability or professional financial advice.

Retrain from the command line with:

```powershell
python train_revenue.py --company-id 1
python train_profit.py --company-id 1
python train_risk.py --company-id 1
```

Each script requires a company ID, reads only that company's records, and saves a company-specific joblib file in `models/`. The app fits predictions from the authenticated company's records without writing a shared model file. A dataset without adequate history does not receive a synthetic prediction.

## Health score and interpretation

The health score adds five capped components: revenue growth, margin, cash flow, inventory stock risk, and financial stability from the model probability when available (neutral points when no risk model is available). Component details are displayed in Analytics. Cash flow is positive, neutral, or negative based on latest monthly profit. Inventory demand uses recorded product quantities divided by the elapsed sales-history days; coverage bands flag low and unusually high stock.

## Privacy and security

All record queries scope to the authenticated user's company. Passwords are hashed, mutations use CSRF tokens, uploads use extension validation and a size limit, and ORM queries use SQLAlchemy parameterization. For deployment, set a high-entropy secret, use MySQL credentials with least privilege, enable HTTPS, configure a production WSGI server, and use database backups. The built-in Flask server is for local use.

## Project layout

```text
app.py                 Flask application and routes
config.py              Environment configuration
database/models.py     Relational schema
services/              Cleaning, financial, expense, inventory, health, advisor
models/                Revenue, profit, and risk ML pipelines
templates/             Authentication and application pages
static/                Responsive CSS and Chart.js setup
samples/                Example CSV datasets
train_*.py              Command-line training entry points
```
