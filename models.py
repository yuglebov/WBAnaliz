from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.String(32), unique=True)
    username = db.Column(db.String(32))
    first_name = db.Column(db.String(32))
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    api_key = db.Column(db.String(512))

    def __repr__(self):
        return f'<User {self.telegram_id}>'


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    article = db.Column(db.String(64), unique=True)
    price = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __repr__(self):
        return f'<Product {self.article}>'

class ReportData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sa_name = db.Column(db.String(120))
    logistics_count = db.Column(db.Integer)
    logistics_sum = db.Column(db.Float)
    return_logistics_count = db.Column(db.Integer)
    return_logistics_sum = db.Column(db.Float)
    sales_count = db.Column(db.Integer)
    payout_sum = db.Column(db.Float)
    retail_price_sum = db.Column(db.Float)
    buyout_percentage = db.Column(db.Float)
    cost_price_total = db.Column(db.Float)
    storage_fee = db.Column(db.Float)
    penalty = db.Column(db.Float)
    ad = db.Column(db.Float)
    deduction = db.Column(db.Float)
    other = db.Column(db.Float)
    return_sum = db.Column(db.Float)
    custom_calculation = db.Column(db.Float)
    custom_payout = db.Column(db.Float)
    roi = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))