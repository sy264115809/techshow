# coding=utf-8
from datetime import datetime
from itsdangerous import JSONWebSignatureSerializer as Serializer
from flask import current_app
from flask_login import UserMixin

from app import db, pili
from app.http.rong_cloud import ApiClient, ClientError


class StreamStatus(object):
    unborn = 0
    unavailable = 1
    available = 2


class UserGender(object):
    male = 0
    female = 1


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key = True)
    bio = db.Column(db.String(64))
    name = db.Column(db.String(32))
    nickname = db.Column(db.String(32))
    gender = db.Column(db.Integer)
    avatar = db.Column(db.String(128))
    password = db.Column(db.String(64))

    mobile = db.Column(db.String(16), unique = True)
    auth_code = db.Column(db.String(16))

    # github oauth
    github_id = db.Column(db.String(32), unique = True)
    github_login = db.Column(db.String(64))
    github_name = db.Column(db.String(32))
    github_email = db.Column(db.String(64))

    # qiniu_oauth
    qiniu_id = db.Column(db.String(32), unique = True)
    qiniu_name = db.Column(db.String(16))
    qiniu_email = db.Column(db.String(32))

    oauth_code = db.Column(db.String(128))
    api_token = db.Column(db.String(128))
    rong_cloud_token = db.Column(db.String(128))

    stream_id = db.Column(db.String(64))
    stream_status = db.Column(db.Integer, default = StreamStatus.available)
    is_stream_enabled = db.Column(db.Boolean, default = True)

    get_auth_code_count = db.Column(db.Integer, default = 0)
    last_get_auth_code_at = db.Column(db.DateTime)

    sign_in_count = db.Column(db.Integer, default = 0)
    current_sign_in_at = db.Column(db.DateTime)
    last_sign_in_at = db.Column(db.DateTime)

    is_banned = db.Column(db.Boolean, default = False)

    last_send_message_at = db.Column(db.DateTime, default = datetime.now)

    created_at = db.Column(db.DateTime, default = datetime.now)
    updated_at = db.Column(db.DateTime, default = datetime.now, onupdate = datetime.now)

    def __init__(self, **kwargs):
        self.get_auth_code_count = 0
        self.sign_in_count = 0
        self.stream_id = pili.create_stream().id
        super(User, self).__init__(**kwargs)

    def __repr__(self):
        return '<User %r>' % self.id

    def is_active(self):
        """If a user is not banned by admin."""
        return not self.is_banned

    @property
    def email(self):
        return self.qiniu_email or self.github_email

    def login(self):
        login_at = datetime.now()
        self.last_sign_in_at = self.current_sign_in_at
        self.current_sign_in_at = login_at
        self.sign_in_count += 1
        self.auth_code = ''
        self.get_auth_code_count = 0
        self.oauth_code = ''
        self.generate_api_token()
        self.generate_rong_cloud_token()

    def generate_api_token(self):
        s = Serializer(current_app.config['SECRET_KEY'], salt = self.current_sign_in_at.strftime('%Y-%m-%d %H:%M:%S'))
        self.api_token = s.dumps({'id': self.id})

    def generate_rong_cloud_token(self, refresh = False):
        if self.rong_cloud_token is None or refresh:
            token = None
            try:
                token = ApiClient().user_get_token(
                        user_id = self.id,
                        name = self.nickname or self.name,
                        portrait_uri = self.avatar or 'https://avatars.githubusercontent.com/u/16420492'
                ).get('token')
            except ClientError as exc:
                current_app.logger.error('generate rong cloud token error: %s', exc)
            finally:
                self.rong_cloud_token = token

    @property
    def stream(self):
        return pili.get_stream(self.stream_id)

    def disable_stream(self):
        self.stream.disable()
        self.is_stream_enabled = False
        db.session.commit()

    def enable_stream(self):
        self.stream.enable()
        self.is_stream_enabled = True
        db.session.commit()

    def ban(self):
        self.disable_stream()
        self.stream_status = StreamStatus.unavailable
        self.is_banned = True
        db.session.commit()

    def unban(self):
        self.enable_stream()
        self.stream_status = StreamStatus.available
        self.is_banned = False
        db.session.commit()

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'nickname': self.nickname,
            'bio': self.bio,
            'gender': self.gender,
            'email': self.email,
            'mobile': self.mobile,
            'avatar': self.avatar,
            'qiniu_name': self.qiniu_name,
            'qiniu_email': self.qiniu_email,
            'github_login': self.github_login,
            'github_name': self.github_name,
            'github_email': self.github_email,
            'is_banned': self.is_banned,
            'stream_status': self.stream_status
        }
