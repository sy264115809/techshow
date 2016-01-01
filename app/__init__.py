# coding=utf8
import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

from rong_cloud import ApiClient

db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config):
    app = Flask(__name__)

    app.config.from_object(config)
    app.debug = app.config['DEBUG']
    app.secret_key = app.config['SECRET_KEY']

    db.init_app(app)

    login_manager.init_app(app)

    os.environ.setdefault('rongcloud_app_key', app.config['RONG_CLOUD_APP_KEY'])
    os.environ.setdefault('rongcloud_app_secret', app.config['RONG_CLOUD_APP_SECRET'])

    from user.views import users_endpoint
    app.register_blueprint(users_endpoint)
    from channel.views import channels_endpoint
    app.register_blueprint(channels_endpoint)

    return app
