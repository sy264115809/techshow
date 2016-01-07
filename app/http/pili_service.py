# coding=utf-8
from pili import *
from flask import current_app


def _hub():
    credentials = Credentials(current_app.config['PILI_ACCESS_KEY'], current_app.config['PILI_SECRET_KEY'])
    return Hub(credentials, current_app.config['PILI_HUB_NAME'])


def get_stream(stream_id):
    return _hub().get_stream(stream_id)


def create_dynamic_stream():
    return _hub().create_stream()
