# coding=utf8
import logging

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_cache import Cache
from celery import Celery
from pili import Credentials, Hub

from app.http.response import APIException, Unauthorized
from app.http.response import exception
from config import config, Config

db = SQLAlchemy()
celery = Celery(__name__, broker = Config.CELERY_BROKER_URL)
cache = Cache()
pili = Hub(Credentials(Config.PILI_ACCESS_KEY, Config.PILI_SECRET_KEY), Config.PILI_HUB_NAME)

login_manager = LoginManager()
login_manager.session_protection = 'strong'


def create_app(config_name):
    app = Flask(__name__)

    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    db.init_app(app)
    cache.init_app(app)
    celery.conf.update(app.config)

    # flask-login init
    login_manager.init_app(app)
    login_manager.unauthorized_handler(lambda: exception(Unauthorized()))

    # blueprint
    from app.controllers.user import users_endpoint
    app.register_blueprint(users_endpoint)
    from app.controllers.channel import channels_endpoint
    app.register_blueprint(channels_endpoint)
    from app.controllers.admin import admin_endpoint
    app.register_blueprint(admin_endpoint)

    # error handler
    app.register_error_handler(APIException, lambda e: exception(e))

    return app
