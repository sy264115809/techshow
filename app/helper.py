from flask import jsonify

from app import login_manager
from constants import *


def success(data = None, code = API_OK, desc = None):
    data = {} if data is None else data
    data['code'] = code
    data['desc'] = API_CODES[code] if desc is None else desc
    return jsonify(data)


def fail(code, desc = None):
    data = {
        'code': code,
        'desc': API_CODES[code] if desc is None else desc
    }
    return jsonify(data)


def bad_request(desc):
    return fail(API_BAD_REQUEST, desc)


@login_manager.unauthorized_handler
def unauthorized():
    return fail(API_UNAUTHORIZED)


def oauth_fail():
    return fail(API_OAUTH_FAIL)


def invalid_auth_code():
    return fail(API_INVALID_AUTH_CODE)


def user_not_found():
    return fail(API_USER_NOT_FOUND)


def channel_not_found():
    return fail(API_CHANNEL_NOT_FOUND)


def max_number_of_channel():
    return fail(API_MAX_CHANNEL_TOUCHED)
