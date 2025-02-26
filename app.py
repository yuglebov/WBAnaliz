import hashlib
import hmac
import requests
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from jinja2 import Template
from dotenv import load_dotenv
from config import Config
from models import db, User, Product, ReportData
from html_functs import generate_report, save_report_data, is_float

load_dotenv()  # Загружаем переменные окружения из .env файла

TELEGRAM_BOT_NAME = os.environ.get('TELEGRAM_BOT_NAME')
TELEGRAM_BOT_URL = os.environ.get('TELEGRAM_URL')

# Создаем экземпляр приложения Flask
app = Flask(__name__)
app.config.from_object(Config)

# Инициализируем базу данных
db.init_app(app)

# Инициализация менеджера логинов
login_manager = LoginManager()
login_manager.login_view = 'index'  # Страница для входа
login_manager.init_app(app)

# URL для запроса данных
url = "https://statistics-api.wildberries.ru/api/v5/supplier/reportDetailByPeriod"


def get_api_data(user):
    apiKey = user.api_key
    params = {"dateFrom": user.start_date.strftime("%Y-%m-%d"), "dateTo": user.end_date.strftime("%Y-%m-%d")}
    response = requests.get(url, params=params, headers={"Authorization": apiKey})
    if response.status_code == 200:
        return response.json()
    else:
        return False

# Проверка хеша подлинности
def check_response(data):
    d = data.copy()
    del d['hash']
    d_list = []
    for key in sorted(d.keys()):
        if d[key] != None:
            d_list.append(key + '=' + d[key])
    data_string = bytes('\n'.join(d_list), 'utf-8')
    secret_key = hashlib.sha256(app.config['TELEGRAM_BOT_TOKEN'].encode('utf-8')).digest()
    hmac_string = hmac.new(secret_key, data_string, hashlib.sha256).hexdigest()
    if hmac_string == data['hash']:
        return True
    return False

def round_float(value):
    """Округляет значение до двух знаков после запятой"""
    if isinstance(value, float):
        return round(value, 2)
    return value

# Функция загрузки пользователя
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('index.html', telegram_bot_name=TELEGRAM_BOT_NAME,
                               telegram_url=TELEGRAM_BOT_URL)
    else:
        user = User.query.filter_by(id=current_user.id).first()
        total = {'Payout': 0, 'CustomCalculation': 0, 'StorageFee': 0,
                 'Penalty': 0, 'Ad': 0, 'Deduction': 0, 'Other': 0}
        if user:
            start_date = user.start_date.strftime("%Y-%m-%d")
            end_date = user.end_date.strftime("%Y-%m-%d")
            api_key = user.api_key
            products = Product.query.filter_by(user_id=user.id).all()
            product_data = "\n".join([f"{product.article},{product.price}" for product in products])
            report_data = ReportData.query.filter_by(user_id=user.id).all()
            for data in report_data:
                total['Payout'] += data.custom_payout
                total['CustomCalculation'] += data.custom_calculation
                total['StorageFee'] += data.storage_fee
                total['Penalty'] += data.penalty
                total['Ad'] += data.ad
                total['Deduction'] += data.deduction
                total['Other'] += data.other
        else:
            start_date = ""
            end_date = ""
            api_key = ""
            product_data = ""
            report_data = []
        app.jinja_env.filters['round2'] = round_float
        return render_template('index.html', user=user, start_date=start_date,
                               end_date=end_date, api_key=api_key, product_data=product_data,
                               report_data=report_data, total=total, telegram_bot_name=TELEGRAM_BOT_NAME,
                               telegram_url=TELEGRAM_BOT_URL)


@app.route('/login', methods=['GET'])
def login():
    # Проверка подлинности хэша
    # См. документацию Telegram: https://core.telegram.org/widgets/login#checking-authorization
    if request.args:
        data = {
            'id': request.args.get('id', None),
            'first_name': request.args.get('first_name', None),
            'last_name': request.args.get('last_name', None),
            'username': request.args.get('username', None),
            'photo_url': request.args.get('photo_url', None),
            'auth_date': request.args.get('auth_date', None),
            'hash': request.args.get('hash', None)
        }
        telegram_id = data['id']

        if not check_response(data):
            abort(403)

        user = User.query.filter_by(telegram_id=str(telegram_id)).first()
        if user is None:
            user = User(telegram_id=str(telegram_id), username=data['username'], first_name=data['first_name'])
            db.session.add(user)
            db.session.commit()
        else:
            get = db.session.query(User).filter_by(telegram_id=str(telegram_id))
            get.update({'username': data['username'], 'first_name': data['first_name']})
            db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    else:
        return render_template('index.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/save_dates', methods=['POST'])
@login_required
def save_dates():
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    api_key = request.form['api_key']

    user = User.query.filter_by(id=current_user.id).first()
    user.start_date = start_date
    user.end_date = end_date
    user.api_key = api_key
    db.session.commit()

    flash('Данные сохранены!')
    return redirect(url_for('index'))


@app.route('/save_products', methods=['POST'])
@login_required
def save_products():
    products = request.form['products']
    # Разделяем строку на отдельные продукты
    product_lines = products.split('\n')
    # Разделяем артикул и цену для каждого продукта
    products_data = [line.strip().split(',') for line in product_lines if line.strip()]
    # Удаляем старые продукты
    Product.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    # Сохраняем данные в базу данных
    for product in products_data:
        if len(product) == 2:
            article = product[0].strip()
            price = product[1].strip()
            if not is_float(price):
                flash(f'Продукт "{article}" имеет некорректную цену')
                continue
            product = Product(article=article, price=price, user_id=current_user.id)
            db.session.add(product)
            db.session.commit()
            flash(f'Продукт "{article}" с ценой "{price}" добавлен.')
        else:
            flash(f'Ошибка в формате продукта: {product}')
    return redirect(url_for('index'))

@app.route('/update_report', methods=['POST'])
@login_required
def update_report():
    user = User.query.filter_by(id=current_user.id).first()
    products = Product.query.filter_by(user_id=user.id).all()
    api_data = get_api_data(user)  # Получаем данные api
    if not api_data:
        flash('Ошибка при получении данных от API')
        return redirect(url_for('index'))
    cost_prices = {}
    for product in products:
        cost_prices[product.article] = product.price
    report_data = generate_report(api_data, cost_prices)
    save_report_data(report_data, cost_prices, current_user.id) # Сохраняем данные в БД
    flash('Данные обновлены')
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(port=8080, host='0.0.0.0')