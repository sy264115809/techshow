# coding=utf8
import base64
import random
from datetime import datetime

from flask import Blueprint, request, current_app, url_for, redirect, json
from flask_login import login_required, current_user
from rauth import OAuth2Service

from app import db, login_manager
from app.user.models import User
from app.channel import constants as CHANNEL
from app.channel.models import Channel
from app.helper import success, bad_request, invalid_auth_code, user_not_found, oauth_fail

users_endpoint = Blueprint('users', __name__, url_prefix = '/users')

AUTH_CODE_VALIDITY_SECONDS = 60 * 10


@users_endpoint.route('/login/mobile/code', methods = ['GET'])
def get_mobile_auth_code():
    """
    获取手机验证码
    :return:
    """
    mobile = request.args.get('mobile')
    if mobile is None:
        return bad_request("missing arguments 'mobile'")

    user = User.query.filter_by(mobile = mobile).first()
    if user is None:
        user = User(mobile)
        user.get_auth_code_count = 0

    user.auth_code = __get_auth_code()
    user.get_auth_code_count += 1
    user.last_get_auth_code_at = datetime.now()
    db.session.add(user)
    db.session.commit()

    return success({
        'auth_code': user.auth_code
    })


@users_endpoint.route('/login/mobile', methods = ['POST'])
def login_by_mobile():
    """
    根据手机号及验证码登录
    :return:
    """
    mobile = request.json.get('mobile')
    if mobile is None:
        return bad_request("missing arguments 'mobil'")

    auth_code = request.json.get('auth_code')
    if auth_code is None:
        return bad_request("missing arguments 'auth_code'")

    user = User.query.filter_by(mobile = mobile, auth_code = auth_code).first()
    if user:
        delta = datetime.now() - user.last_get_auth_code_at
        if delta.seconds > AUTH_CODE_VALIDITY_SECONDS:
            return invalid_auth_code()

        user.auth_code = ''
        user.get_auth_code_count = 0
        user.login()

        return success({
            'id': user.id,
            'mobile': user.mobile,
            'api_key': user.api_key
        })
    else:
        return invalid_auth_code()


@users_endpoint.route('/login/github', methods = ['GET'])
def login_by_github():
    """
    GitHub OAuth
    :return:
    """
    redirect_uri = url_for('users.login_by_github_callback',
                           next = request.args.get('next') or request.referrer or None,
                           _external = True)
    return redirect(__github_oauth().get_authorize_url(redirect_uri = redirect_uri))


@users_endpoint.route('/login/github/callback', methods = ['GET'])
def login_by_github_callback():
    """
    Github OAuth 回调
    :return:
    """
    code = request.args.get('code')
    if code is None:
        return bad_request('bad request')

    try:
        data = dict(code = code)
        auth = __github_oauth().get_auth_session(data = data)
        info = auth.get('user').json()
    except Exception:
        return oauth_fail()

    user = User.query.filter_by(github_id = info.get('id')).first()
    if user is None:
        user = User(
                github_id = info.get('id'),
                github_login = info.get('login'),
                nickname = info.get('login'),
                github_name = info.get('name'),
                name = info.get('name'),
                github_email = info.get('email'),
                avatar = info.get('avatar_url'),
                bio = info.get('bio'),
        )

    user.login()
    return success({
        'id': user.id,
        'api_key': user.api_key
    })


@users_endpoint.route('/login/qiniu', methods = ['GET'])
def login_by_qiniu():
    """
    Qiniu OAuth
    :return:
    """
    redirect_uri = url_for('users.login_by_qiniu_callback', next = request.args.get('next') or request.referrer or None,
                           _external = True)
    return redirect(__qiniu_oauth().get_authorize_url(redirect_uri = redirect_uri, response_type = 'code'))


@users_endpoint.route('/login/qiniu/callback', methods = ['GET'])
def login_by_qiniu_callback():
    """
    Qiniu OAuth 回调
    :return:
    """
    code = request.args.get('code')
    if code is None:
        return bad_request('bad request')

    try:
        data = dict(code = code, grant_type = 'authorization_code')
        auth = __qiniu_oauth().get_auth_session(data = data, decoder = lambda c: json.loads(c))
        info = auth.get('info?access_token=' + auth.access_token).json().get('data')
    except Exception:
        return oauth_fail()

    user = User.query.filter_by(qiniu_id = info.get('uid')).first()
    if user is None:
        user = User(
                qiniu_id = info.get('uid'),
                qiniu_name = info.get('full_name'),
                name = info.get('full_name'),
                qiniu_email = info.get('email'),
                gender = info.get('gender')
        )

    user.login()
    return success({
        'id': user.id,
        'api_key': user.api_key
    })


@users_endpoint.route('/logout', methods = ['POST'])
@login_required
def logout():
    """
    登出
    :return:
    """
    current_user.api_key = ''
    db.session.add(current_user)
    db.session.commit()
    return success()


@users_endpoint.route('/<int:user_id>', methods = ['GET'])
@login_required
def user_info(user_id):
    """
    指定用户的信息
    :param user_id:要查询的user的id
    :type user_id:int
    :return:
    """
    user = User.query.get(user_id)
    if user is None:
        return user_not_found()

    return success({
        'user': user.to_json()
    })


@users_endpoint.route('/<int:user_id>/channels/published', methods = ['GET'])
@login_required
def get_user_published_channels(user_id):
    """
    指定用户的所有已结束推送的channel(回放列表)
    :param user_id:要查询的user的id
    :type user_id:int
    :return:
    """
    channels = Channel.query.filter_by(owner_id = user_id, status = CHANNEL.PUBLISHED).all()
    published_channel_list = []
    for channel in channels:
        published_channel_list.append(channel.to_json())
    return success({
        'count': len(channels),
        'published_channels': published_channel_list if len(published_channel_list) else None
    })


@users_endpoint.route('/<int:user_id>/channels/publishing', methods = ['GET'])
@login_required
def get_user_publishing_channel(user_id):
    """
    指定用户的当前正在推送(直播)的channel
    :param user_id:要查询的user的id
    :type user_id:int
    :return:
    """
    channel = Channel.query.filter_by(owner_id = user_id, status = CHANNEL.PUBLISHING).first()
    return success({
        'publishing_channel': channel.to_json() if channel else None
    })


@login_manager.request_loader
def load_user_from_request(request):
    # first, try to login using the api_key url arg
    api_key = request.args.get('api_key')
    if api_key:
        user = User.query.filter_by(api_key = api_key).first()
        if user:
            return user

    # next, try to login using Basic Auth
    api_key = request.authorization
    if api_key:
        api_key = api_key.username
        try:
            api_key = base64.b64decode(api_key)
        except TypeError:
            pass

        user = User.query.filter_by(api_key = api_key).first()
        if user:
            return user

    # finally, return None if both methods did not login the user
    return None


def __get_auth_code():
    return random.randint(1000, 9999)


def __github_oauth():
    return __oauth('github')


def __qiniu_oauth():
    return __oauth('qiniu')


def __oauth(which):
    settings = current_app.config['OAUTH'][which]
    return OAuth2Service(**settings) if settings else None
