# coding=utf8
import logging
import os

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

from app.http.response import APIException, Unauthorized
from app.http.response import exception
from app.http.rong_cloud import ApiClient

db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config):
    app = Flask(__name__)

    app.config.from_object(config)
    app.debug = app.config['DEBUG']
    app.secret_key = app.config['SECRET_KEY']

    # add handler to redirect to gunicorn error
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.handlers.extend(logging.getLogger("gunicorn.error").handlers)
    app.logger.info('Use %s', config.__name__)

    db.init_app(app)

    # flask-login init
    login_manager.init_app(app)
    login_manager.unauthorized_handler(lambda: exception(Unauthorized()))

    # rongcloud init
    os.environ.setdefault('rongcloud_app_key', app.config['RONG_CLOUD_APP_KEY'])
    os.environ.setdefault('rongcloud_app_secret', app.config['RONG_CLOUD_APP_SECRET'])

    # blueprint
    from app.controllers.user import users_endpoint
    app.register_blueprint(users_endpoint)
    from app.controllers.channel import channels_endpoint
    app.register_blueprint(channels_endpoint)

    # error handler
    app.register_error_handler(APIException, lambda e: exception(e))

    return app
