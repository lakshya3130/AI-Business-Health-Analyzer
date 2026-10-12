from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf.csrf import CSRFProtect
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.utils import secure_filename

from config import Config
from database import db
from database.models import Company, Employee, Expense, Inventory, Sale, User
from models.profit_model import predict_next_month_profit
from models.revenue_model import predict_next_month
from models.risk_model import predict_risk
from services.advisor import recommendations
from services.data_processor import clean_frame, parse_upload
from services.expense_analyzer import analyze as analyze_expenses
from services.financial_analysis import analyze as analyze_financials
from services.health_score import calculate as calculate_health
from services.inventory_intelligence import analyze as analyze_inventory


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(exist_ok=True)
    Path(app.instance_path).mkdir(exist_ok=True)
    db.init_app(app)
    login_manager = LoginManager(app)
    login_manager.login_view = "login"
    login_manager.login_message_category = "warning"
    CSRFProtect(app)

    @app.template_filter("money")
    def money(value):
        return "₹" + format(float(value or 0), ",.0f")

    @app.template_filter("pct")
    def pct(value):
        return "—" if value is None else f"{value:+.1f}%"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_globals():
        return {
            "csrf_token": __import__(
                "flask_wtf.csrf", fromlist=["generate_csrf"]
            ).generate_csrf
        }

    @app.errorhandler(413)
    def too_large(_error):
        flash("File exceeds the 16 MB upload limit.", "error")
        return redirect(url_for("upload"))

    @app.route("/")
    def index():
        return redirect(
            url_for("dashboard" if current_user.is_authenticated else "login")
        )

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            name, email, password = (
                request.form.get(k, "").strip() for k in ("name", "email", "password")
            )
            company_name = request.form.get("company_name", "").strip()
            if not name or not company_name or "@" not in email or len(password) < 8:
                flash(
                    "Enter your name, a valid email, company name, and a password with at least 8 characters.",
                    "error",
                )
            elif User.query.filter_by(email=email.lower()).first():
                flash("An account with that email already exists.", "error")
            else:
                user = User(name=name, email=email.lower())
                user.set_password(password)
                user.company = Company(
                    company_name=company_name,
                    industry=request.form.get("industry", "Other").strip() or "Other",
                )
                db.session.add(user)
                db.session.commit()
                login_user(user)
                return redirect(url_for("dashboard"))
        return render_template("auth.html", mode="register")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            user = User.query.filter_by(
                email=request.form.get("email", "").strip().lower()
            ).first()
            if user and user.check_password(request.form.get("password", "")):
                login_user(user, remember=request.form.get("remember") == "on")
                return redirect(request.args.get("next") or url_for("dashboard"))
            flash("Email or password is incorrect.", "error")
        return render_template("auth.html", mode="login")

    @app.post("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    def get_company():
        if not current_user.company:
            abort(404)
        return current_user.company

    def snapshot():
        company = get_company()
        sales = (
            Sale.query.filter_by(company_id=company.id).order_by(Sale.sale_date).all()
        )
        expenses = (
            Expense.query.filter_by(company_id=company.id)
            .order_by(Expense.expense_date)
            .all()
        )
        stock = Inventory.query.filter_by(company_id=company.id).all()
        financial = analyze_financials(sales, expenses)
        exp = analyze_expenses(expenses)
        inv = analyze_inventory(stock, sales)
        revenue_pred = predict_next_month(sales)
        profit_pred = predict_next_month_profit(sales, expenses)
        risk = predict_risk(sales, expenses)
        pred = {"revenue": revenue_pred, "profit": profit_pred}
        health = calculate_health(
            financial, inv, risk.get("probability") if risk.get("available") else None
        )
        advice = recommendations(financial, exp, inv, pred, risk, health)
        return {
            "company": company,
            "sales": sales,
            "expenses_raw": expenses,
            "inventory_raw": stock,
            "financial": financial,
            "expense_analysis": exp,
            "inventory": inv,
            "revenue_prediction": revenue_pred,
            "profit_prediction": profit_pred,
            "risk": risk,
            "health": health,
            "recommendations": advice,
        }

    @app.get("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html", data=snapshot())

    @app.route("/upload", methods=["GET", "POST"])
    @login_required
    def upload():
        if request.method == "POST":
            try:
                kind = request.form.get("kind", "")
                if kind not in {"sales", "expenses", "inventory", "employees"}:
                    raise ValueError("Choose a supported data type.")
                frame = parse_upload(request.files.get("file"))
                records, summary = clean_frame(frame, kind)
                company = get_company()
                models = {
                    "sales": (
                        Sale,
                        {
                            "sale_date": "sale_date",
                            "product": "product",
                            "quantity": "quantity",
                            "revenue": "revenue",
                        },
                    ),
                    "expenses": (
                        Expense,
                        {
                            "expense_date": "expense_date",
                            "category": "category",
                            "amount": "amount",
                        },
                    ),
                    "inventory": (
                        Inventory,
                        {
                            "product": "product",
                            "current_stock": "current_stock",
                            "reorder_level": "reorder_level",
                            "unit_cost": "unit_cost",
                        },
                    ),
                    "employees": (
                        Employee,
                        {
                            "name": "name",
                            "salary": "salary",
                            "joining_date": "joining_date",
                        },
                    ),
                }
                model, fields = models[kind]
                for record in records:
                    db.session.add(
                        model(
                            company_id=company.id,
                            **{field: record[field] for field in fields},
                        )
                    )
                db.session.commit()
                flash(
                    f"Imported {summary['valid']} {kind} records. {summary['invalid']} invalid rows and {summary['duplicates']} exact duplicates were skipped.",
                    "success",
                )
                return render_template("upload.html", summary=summary, kind=kind)
            except (ValueError, SQLAlchemyError) as exc:
                db.session.rollback()
                flash(
                    (
                        str(exc)
                        if isinstance(exc, ValueError)
                        else "The import could not be saved. Check records for duplicates or database errors."
                    ),
                    "error",
                )
        return render_template("upload.html")

    @app.route("/sales", methods=["GET", "POST"])
    @login_required
    def sales_page():
        company = get_company()
        if request.method == "POST":
            try:
                records, _ = clean_frame(
                    pd.DataFrame([request.form.to_dict()]), "sales"
                )
                db.session.add(Sale(company_id=company.id, **records[0]))
                db.session.commit()
                flash("Sale saved.", "success")
            except (ValueError, IndexError):
                flash(
                    "Enter a valid date, product, positive quantity, and non-negative revenue.",
                    "error",
                )
        rows = (
            Sale.query.filter_by(company_id=company.id)
            .order_by(Sale.sale_date.desc())
            .limit(200)
            .all()
        )
        return render_template("records.html", kind="sales", rows=rows)

    @app.route("/expenses", methods=["GET", "POST"])
    @login_required
    def expenses_page():
        company = get_company()
        if request.method == "POST":
            try:
                records, _ = clean_frame(
                    pd.DataFrame([request.form.to_dict()]), "expenses"
                )
                db.session.add(Expense(company_id=company.id, **records[0]))
                db.session.commit()
                flash("Expense saved.", "success")
            except (ValueError, IndexError):
                flash("Enter a valid date, category, and non-negative amount.", "error")
        rows = (
            Expense.query.filter_by(company_id=company.id)
            .order_by(Expense.expense_date.desc())
            .limit(200)
            .all()
        )
        return render_template("records.html", kind="expenses", rows=rows)

    @app.route("/inventory", methods=["GET", "POST"])
    @login_required
    def inventory_page():
        company = get_company()
        if request.method == "POST":
            try:
                records, _ = clean_frame(
                    pd.DataFrame([request.form.to_dict()]), "inventory"
                )
                row = Inventory.query.filter_by(
                    company_id=company.id, product=records[0]["product"]
                ).first()
                if row:
                    for key, value in records[0].items():
                        setattr(row, key, value)
                    row.last_updated = date.today()
                else:
                    db.session.add(Inventory(company_id=company.id, **records[0]))
                db.session.commit()
                flash("Inventory saved.", "success")
            except (ValueError, IndexError):
                flash(
                    "Enter a product and non-negative stock, reorder level, and unit cost.",
                    "error",
                )
        rows = (
            Inventory.query.filter_by(company_id=company.id)
            .order_by(Inventory.product)
            .all()
        )
        return render_template("records.html", kind="inventory", rows=rows)

    @app.route("/employees", methods=["GET", "POST"])
    @login_required
    def employees_page():
        company = get_company()
        if request.method == "POST":
            try:
                records, _ = clean_frame(
                    pd.DataFrame([request.form.to_dict()]), "employees"
                )
                db.session.add(Employee(company_id=company.id, **records[0]))
                db.session.commit()
                flash("Employee saved.", "success")
            except (ValueError, IndexError):
                flash("Enter a name, joining date, and non-negative salary.", "error")
        rows = (
            Employee.query.filter_by(company_id=company.id)
            .order_by(Employee.name)
            .all()
        )
        return render_template("records.html", kind="employees", rows=rows)

    @app.post("/<kind>/<int:record_id>/delete")
    @login_required
    def delete_record(kind, record_id):
        record_models = {
            "sales": (Sale, "sales_page", "sale"),
            "expenses": (Expense, "expenses_page", "expense"),
            "inventory": (Inventory, "inventory_page", "inventory item"),
            "employees": (Employee, "employees_page", "employee"),
        }
        if kind not in record_models:
            abort(404)

        model, endpoint, label = record_models[kind]
        company = get_company()
        record = model.query.filter_by(
            id=record_id, company_id=company.id
        ).first()
        if record is None:
            abort(404)

        db.session.delete(record)
        db.session.commit()
        flash(f"The {label} was deleted.", "success")
        return redirect(url_for(endpoint))

    @app.route("/<kind>/<int:record_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_record(kind, record_id):
        record_models = {
            "sales": (Sale, "sales_page"),
            "expenses": (Expense, "expenses_page"),
            "inventory": (Inventory, "inventory_page"),
            "employees": (Employee, "employees_page"),
        }
        if kind not in record_models:
            abort(404)

        model, endpoint = record_models[kind]
        company = get_company()
        record = model.query.filter_by(
            id=record_id, company_id=company.id
        ).first()
        if record is None:
            abort(404)

        if request.method == "POST":
            try:
                records, _ = clean_frame(
                    pd.DataFrame([request.form.to_dict()]), kind
                )
                for field, value in records[0].items():
                    setattr(record, field, value)
                if kind == "inventory":
                    record.last_updated = date.today()
                db.session.commit()
                flash("Record updated successfully.", "success")
                return redirect(url_for(endpoint))
            except (ValueError, IndexError):
                db.session.rollback()
                flash("Check the values and try saving again.", "error")
            except IntegrityError:
                db.session.rollback()
                flash("That product already exists in inventory. Choose another product name.", "error")
            except SQLAlchemyError:
                db.session.rollback()
                flash("The record could not be updated. Please try again.", "error")

        query = model.query.filter_by(company_id=company.id)
        if kind == "sales":
            rows = query.order_by(Sale.sale_date.desc()).limit(200).all()
        elif kind == "expenses":
            rows = query.order_by(Expense.expense_date.desc()).limit(200).all()
        elif kind == "inventory":
            rows = query.order_by(Inventory.product).all()
        else:
            rows = query.order_by(Employee.name).all()
        return render_template(
            "records.html", kind=kind, rows=rows, edit_record=record
        )

    @app.get("/analytics")
    @login_required
    def analytics():
        return render_template("analytics.html", data=snapshot())

    @app.get("/predictions")
    @login_required
    def predictions():
        return render_template("predictions.html", data=snapshot())

    @app.get("/risk")
    @login_required
    def risk_page():
        return render_template("risk.html", data=snapshot())

    @app.get("/advisor")
    @login_required
    def advisor_page():
        return render_template("advisor.html", data=snapshot())

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        company = get_company()
        if request.method == "POST":
            company_name = request.form.get("company_name", "").strip()
            industry = request.form.get("industry", "").strip()
            if not company_name or not industry:
                flash("Company name and industry are required.", "error")
            else:
                company.company_name = company_name
                company.industry = industry
                db.session.commit()
                flash("Business profile updated.", "success")
        return render_template("settings.html", company=company)

    @app.get("/api/analytics")
    @login_required
    def analytics_api():
        data = snapshot()["financial"]
        return jsonify(data)

    @app.get("/reports")
    @login_required
    def reports():
        return render_template("reports.html", data=snapshot())

    @app.get("/reports/pdf")
    @login_required
    def report_pdf():
        data = snapshot()
        buf = BytesIO()
        pdf = canvas.Canvas(buf, pagesize=letter)
        width, height = letter
        y = height - 56
        pdf.setTitle(f"{data['company'].company_name} Business Health Report")
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(48, y, "Business Health Report")
        y -= 26
        pdf.setFont("Helvetica", 11)
        lines = [
            f"Company: {data['company'].company_name}",
            f"Generated: {date.today().isoformat()}",
            f"Revenue: {data['financial']['total_revenue']:,.2f}",
            f"Expenses: {data['financial']['total_expenses']:,.2f}",
            f"Profit: {data['financial']['total_profit']:,.2f}",
            f"Profit margin: {data['financial']['profit_margin']:.1f}%",
            f"Health score: {data['health']['score']}/100 ({data['health']['category']})",
            f"Cash flow: {data['financial']['cash_flow']}",
            "Revenue prediction: "
            + (
                f"{data['revenue_prediction']['predicted']:,.2f}"
                if data["revenue_prediction"]["available"]
                else data["revenue_prediction"]["reason"]
            ),
            "Profit prediction: "
            + (
                f"{data['profit_prediction']['predicted']:,.2f}"
                if data["profit_prediction"]["available"]
                else data["profit_prediction"]["reason"]
            ),
            "Financial risk: "
            + (
                f"{data['risk']['level']} ({data['risk']['probability']:.0%})"
                if data["risk"]["available"]
                else data["risk"]["reason"]
            ),
            "",
            "Expense changes:",
        ]
        lines += [
            f"{c['category']}: {c['change_pct']:+.1f}% month over month"
            for c in data["expense_analysis"]["changes"]
        ] or ["No significant category changes detected."]
        lines += ["", "Inventory status:"] + [
            f"{r['product']}: {r['status']} (stock {r['stock']:g})"
            for r in data["inventory"]
        ]
        lines += ["", "Recommendations:"] + [
            "- " + item for item in data["recommendations"]
        ]
        for line in lines:
            if y < 55:
                pdf.showPage()
                y = height - 55
                pdf.setFont("Helvetica", 11)
            pdf.drawString(48, y, line[:110])
            y -= 17
        pdf.save()
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="business-health-report.pdf",
        )

    with app.app_context():
        db.create_all()
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
