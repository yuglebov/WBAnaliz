"""
Конфигурационный файл приложения Flask.
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config(object): # pylint: disable=too-few-public-methods
    """
    Класс конфигурации Flask-приложения.
    Содержит параметры, загружаемые из переменных окружения или используемые по умолчанию.
    """
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = (os.environ.get('DATABASE_URL') or
                               'mysql+mysqlconnector://username:password@localhost/dbname')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
