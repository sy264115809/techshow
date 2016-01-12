# coding=utf-8
import random
from datetime import datetime

from flask import Blueprint, current_app, request, url_for, redirect, render_template, abort
from flask_login import login_required, current_user, login_user

from app import db, login_manager
from app.models.user import User, UserGender
from app.http.request import paginate, Rule, parse_params
from app.http.response import success, InvalidAuthCode, UserNotFound, OAuthFail
from app.http.oauth import OAuthSignIn

users_endpoint = Blueprint('users', __name__, url_prefix = '/users')

AUTH_CODE_VALIDITY_SECONDS = 60 * 10


@users_endpoint.route('/login/mobile/code', methods = ['GET'])
def get_mobile_auth_code():
    """获取手机验证码
    支持的query params:
    mobile - 必须, 手机号
    """
    q = parse_params(request.args, Rule('mobile', must = True))
    user = User.query.filter_by(**q).first()
    if user is None:
        user = User(**q)

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
    """根据手机号及验证码登录
    支持的json参数:
    mobile - 必须, 手机号
    auth_code - 必须, 验证码
    """
    q = parse_params(
            request.json,
            Rule('mobile', must = True),
            Rule('auth_code', must = True)
    )
    user = User.query.filter_by(**q).first()
    if user is None:
        raise InvalidAuthCode()

    delta = (datetime.now() - user.last_get_auth_code_at).seconds
    if delta > AUTH_CODE_VALIDITY_SECONDS:
        raise InvalidAuthCode()

    user.login()
    db.session.commit()

    return success({
        'user': user.to_json(),
        'api_token': user.api_token,
        'rong_cloud_token': user.rong_cloud_token
    })


@users_endpoint.route('/login/<provider_name>', methods = ['GET'])
def login_by_oauth(provider_name):
    """GitHub OAuth
    :param provider_name: 支持: github qiniu
    """
    provider = OAuthSignIn.get_provider(provider_name)
    if provider:
        return provider.authorize()
    else:
        return abort(404)


@users_endpoint.route('/login/github/callback', methods = ['GET'])
def login_by_github_callback():
    """Github OAuth 回调
    """
    code, info = OAuthSignIn.get_provider('github').callback()
    if code is None:
        raise OAuthFail()

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

    # if user is admin, login it and redirect to admin index
    if user.github_email in current_app.config['ADMIN_GITHUB']:
        login_user(user)
        return redirect(url_for('admin.admin_index'))

    return render_template('login.html')


@users_endpoint.route('/login/qiniu/callback', methods = ['GET'])
def login_by_qiniu_callback():
    """Qiniu OAuth 回调
    """
    code, info = OAuthSignIn.get_provider('qiniu').callback()
    if code is None:
        raise OAuthFail()

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

    # if user is admin, login it and redirect to admin index
    if user.qiniu_email in current_app.config['ADMIN_QINIU']:
        login_user(user)
        return redirect(url_for('admin.admin_index'))

    return render_template('login.html')


@users_endpoint.route('/login', methods = ['POST'])
def get_user_access_token():
    """登录
    支持的json参数:
    auth_code - 必须, OAuth回调时url中附带的code
    """
    auth_code = parse_params(request.json, Rule('auth_code', must = True))['auth_code']
    user = User.query.filter_by(oauth_code = auth_code).first()
    if user is None:
        raise InvalidAuthCode()

    user.login()
    db.session.commit()

    return success({
        'user': user.to_json(),
        'api_token': user.api_token,
        'rong_cloud_token': user.rong_cloud_token
    })


@users_endpoint.route('/logout', methods = ['POST'])
@login_required
def logout():
    """登出
    """
    current_user.api_token = ''
    db.session.commit()
    return success()


@users_endpoint.route('', methods = ['GET'])
@login_required
def get_users_info():
    """按条件查询用户.
    支持的query params:
    id - 可选, 用户id
    nickname - 可选, 用户昵称
    l - 可选, 返回条目数量限制, 默认10
    p - 可选, 返回条目的起始页, 默认1
    :return:
    """
    q = parse_params(
            request.args,
            Rule('id'),
            Rule('nickname')
    )
    users = User.query.filter_by(**q).paginate(*paginate()).items
    if len(users) == 0:
        raise UserNotFound()

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
    """查询当前用户信息
    """
    return success({
        'user': current_user.to_json()
    })


@users_endpoint.route('/my', methods = ['POST'])
@login_required
def update_user_info():
    """更新当前用户信息
    """
    q = parse_params(
            request.json,
            Rule('avatar'),
            Rule('nickname'),
            Rule('gender', allow = [UserGender.female, UserGender.male]),
            Rule('bio')
    )
    User.query.filter_by(id = current_user.id).update(q)
    db.session.commit()
    return success({
        'user': current_user.to_json()
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
        user = User.query.filter_by(api_token = api_token).first()
        if user:
            return user

    # finally, return None if both methods did not login the user
    return None


@login_manager.user_loader
def load_user_from_session(user_id):
    return User.query.get(user_id)


def _get_auth_code():
    return random.randint(1000, 9999)


def _github_oauth():
    return OAuth2Service(**current_app.config['OAUTH_GITHUB'])


def _qiniu_oauth():
    return OAuth2Service(**current_app.config['OAUTH_QINIU'])
