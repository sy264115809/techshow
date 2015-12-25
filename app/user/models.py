# coding=utf8
from datetime import datetime
from itsdangerous import JSONWebSignatureSerializer as Serializer

from app import db
from app.user import constants as USER

from flask import current_app
from flask_login import UserMixin


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

    api_key = db.Column(db.String(128))

    stream_id = db.Column(db.String(64))
    stream_status = db.Column(db.Integer, default = USER.STREAM_UNBORN)

    get_auth_code_count = db.Column(db.Integer, default = 0)
    last_get_auth_code_at = db.Column(db.DateTime)

    sign_in_count = db.Column(db.Integer, default = 0)
    current_sign_in_at = db.Column(db.DateTime)
    last_sign_in_at = db.Column(db.DateTime)

    is_banned = db.Column(db.Boolean, default = False)

    created_at = db.Column(db.DateTime, default = datetime.now())
    updated_at = db.Column(db.DateTime, default = datetime.now(), onupdate = datetime.now())

    def __init__(self, **kwargs):
        self.get_auth_code_count = 0
        self.sign_in_count = 0
        super(User, self).__init__(**kwargs)

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

        s = Serializer(current_app.config['SECRET_KEY'], salt = login_at.strftime('%Y-%m-%d %H:%M:%S'))
        self.api_key = s.dumps({'id': self.id})

        db.session.add(self)
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
