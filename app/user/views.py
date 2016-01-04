# coding=utf8
import base64
import random
from datetime import datetime

from flask import Blueprint, request, current_app, url_for, redirect, json ,render_template
from flask_login import login_required, current_user
from rauth import OAuth2Service

from app import db, login_manager
from app.channel import constants as CHANNEL
from app.channel.models import Channel
from app.http_utils.response import success, bad_request, invalid_auth_code, user_not_found, oauth_fail, \
    rong_cloud_failed
from app.http_utils.request import paginate, query_params, rule
from app.rong_cloud import ApiClient, ClientError
from app.user.models import User

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
        user = User(mobile = mobile)
        user.get_auth_code_count = 0

    user.auth_code = _get_auth_code()
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
        user.rong_cloud_token = _get_rong_cloud_token(user)
        user.login()

        return success({
            'id': user.id,
            'mobile': user.mobile,
            'api_token': user.api_token,
            'rong_cloud_token': user.rong_cloud_token
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
    return redirect(_github_oauth().get_authorize_url(redirect_uri = redirect_uri))


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
        auth = _github_oauth().get_auth_session(data = data)
        info = auth.get('user').json()
    except Exception:
        return oauth_fail()

    user = User.query.filter_by(github_id = info.get('id')).first()
    if user is None:
        user = User(
                github_id = info.get('id'),
                nickname = info.get('login'),
                name = info.get('name'),
                avatar = info.get('avatar_url'),
                bio = info.get('bio'),
        )
        db.session.add(user)

    # update github info
    user.github_login = info.get('login')
    user.github_email = info.get('email')
    user.github_name = info.get('name')

    # update oauth code
    user.oauth_code = code
    db.session.commit()

    return render_template('login.html')


@users_endpoint.route('/login/qiniu', methods = ['GET'])
def login_by_qiniu():
    """
    Qiniu OAuth
    :return:
    """
    redirect_uri = url_for('users.login_by_qiniu_callback', next = request.args.get('next') or request.referrer or None,
                           _external = True)
    return redirect(_qiniu_oauth().get_authorize_url(redirect_uri = redirect_uri, response_type = 'code'))


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
        auth = _qiniu_oauth().get_auth_session(data = data, decoder = lambda c: json.loads(c))
        info = auth.get('info?access_token=' + auth.access_token).json().get('data')
    except Exception:
        return oauth_fail()

    user = User.query.filter_by(qiniu_id = info.get('uid')).first()
    if user is None:
        user = User(
                qiniu_id = info.get('uid'),
                name = info.get('full_name'),
                nickname = info.get('full_name'),
                gender = info.get('gender')
        )
        db.session.add(user)

    # update qiniu info
    user.qiniu_name = info.get('full_name')
    user.qiniu_email = info.get('email')

    # update oauth_code
    user.oauth_code = code
    db.session.commit()

    return render_template('login.html')


@users_endpoint.route('/login', methods = ['POST'])
def get_user_access_token():
    code = request.json.get('auth_code')
    if code is None:
        return bad_request('missing argument "auth_code"')

    user = User.query.filter_by(oauth_code = code).first()
    if user is None:
        return invalid_auth_code()

    user.oauth_code = ''
    user.rong_cloud_token = _get_rong_cloud_token(user)
    user.login()
    return success({
        'user': user.to_json(),
        'api_token': user.api_token,
        'rong_cloud_token': user.rong_cloud_token
    })


@users_endpoint.route('/logout', methods = ['POST'])
@login_required
def logout():
    """
    登出
    :return:
    """
    current_user.api_token = ''
    db.session.add(current_user)
    db.session.commit()
    return success()


@users_endpoint.route('/token/rongcloud')
@login_required
def get_rong_cloud_token():
    token = _get_rong_cloud_token()
    if token is None:
        return rong_cloud_failed()

    current_user.rong_cloud_token = token
    db.session.commit()

    return success({
        'rong_cloud_token': token
    })


@users_endpoint.route('', methods = ['GET'])
@login_required
def get_users_info():
    """
    按条件查询用户. 支持的query params:
    id - 用户id
    nickname - 用户昵称

    l - 返回条目数量限制, 默认10
    p - 返回条目的起始页, 默认1
    :return:
    """
    rules = [
        rule('id', 'id'),
        rule('nickname', 'nickname')
    ]
    q, bad = query_params(*rules)
    if bad:
        return bad_request(bad)

    users = User.query.filter_by(**q).paginate(*paginate()).items
    if len(users) == 0:
        return user_not_found()

    res = list()
    for user in users:
        res.append(user.to_json())

    return success({
        'count': len(res),
        'users': res
    })


@users_endpoint.route('/my', methods = ['GET'])
@login_required
def get_my_info():
    """
    查询当前用户信息
    :return:
    """
    return success({
        'user': current_user.to_json()
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
    api_token = request.args.get('api_token')
    if api_token:
        user = User.query.filter_by(api_token = api_token).first()
        if user:
            return user

    # next, try to login using Basic Auth
    api_token = request.authorization
    if api_token:
        api_token = api_token.username
        try:
            api_token = base64.b64decode(api_token)
        except TypeError:
            pass

        user = User.query.filter_by(api_token = api_token).first()
        if user:
            return user

    # finally, return None if both methods did not login the user
    return None


def _get_auth_code():
    return random.randint(1000, 9999)


def _github_oauth():
    return _oauth('github')


def _qiniu_oauth():
    return _oauth('qiniu')


def _oauth(which):
    settings = current_app.config['OAUTH'].get(which)
    return OAuth2Service(**settings) if settings else None


def _get_rong_cloud_token(user):
    try:
        return ApiClient().user_get_token(
                user_id = user.id,
                name = user.nickname or user.name,
                portrait_uri = user.avatar or 'https://avatars.githubusercontent.com/u/16420492'
        ).get('token')
    except ClientError:
        return None
