from datetime import date, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    company = db.relationship("Company", backref="owner", uselist=False, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False)
    company_name = db.Column(db.String(180), nullable=False)
    industry = db.Column(db.String(120), nullable=False, default="Other")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    sales = db.relationship("Sale", backref="company", cascade="all, delete-orphan")
    expenses = db.relationship("Expense", backref="company", cascade="all, delete-orphan")
    inventory = db.relationship("Inventory", backref="company", cascade="all, delete-orphan")
    employees = db.relationship("Employee", backref="company", cascade="all, delete-orphan")


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id", ondelete="CASCADE"), index=True, nullable=False)
    sale_date = db.Column(db.Date, index=True, nullable=False)
    product = db.Column(db.String(180), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    revenue = db.Column(db.Float, nullable=False)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id", ondelete="CASCADE"), index=True, nullable=False)
    expense_date = db.Column(db.Date, index=True, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    amount = db.Column(db.Float, nullable=False)


class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id", ondelete="CASCADE"), index=True, nullable=False)
    product = db.Column(db.String(180), nullable=False)
    current_stock = db.Column(db.Float, nullable=False)
    reorder_level = db.Column(db.Float, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False)
    last_updated = db.Column(db.Date, default=date.today, nullable=False)
    __table_args__ = (db.UniqueConstraint("company_id", "product", name="uq_inventory_company_product"),)


class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id", ondelete="CASCADE"), index=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    salary = db.Column(db.Float, nullable=False)
    joining_date = db.Column(db.Date, nullable=False)
