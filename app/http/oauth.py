# coding=utf-8
from rauth import OAuth2Service
from flask import current_app, url_for, request, redirect, json


class OAuthSignIn(object):
    providers = None

    def __init__(self, provider_name):
        self.provider_name = provider_name
        credentials = current_app.config['OAUTH_CREDENTIALS'][provider_name]
        self.consumer_id = credentials['id']
        self.consumer_secret = credentials['secret']

    def authorize(self):
        pass

    def callback(self):
        pass

    def get_callback_url(self):
        return url_for('users.login_by_%s_callback' % self.provider_name,
                       next = request.args.get('next') or request.referrer or None,
                       _external = True)

    @classmethod
    def get_provider(cls, provider_name):
        if cls.providers is None:
            cls.providers = {}
            for provider_class in cls.__subclasses__():
                provider = provider_class()
                cls.providers[provider.provider_name] = provider
        return cls.providers[provider_name]


class GithubSignIn(OAuthSignIn):
    def __init__(self):
        super(GithubSignIn, self).__init__('github')
        self.service = OAuth2Service(
                name = 'github',
                client_id = self.consumer_id,
                client_secret = self.consumer_secret,
                authorize_url = 'https://github.com/login/oauth/authorize',
                access_token_url = 'https://github.com/login/oauth/access_token',
                base_url = 'https://api.github.com/'
        )

    def authorize(self):
        return redirect(self.service.get_authorize_url(redirect_uri = self.get_callback_url()))

    def callback(self):
        if 'code' not in request.args:
            return None, None

        code = request.args['code']
        oauth_session = self.service.get_auth_session(
                data = {
                    'code': code,
                    'redirect_uri': self.get_callback_url()
                }
        )
        me = oauth_session.get('user').json()
        return code, me


class QiniuSignIn(OAuthSignIn):
    def __init__(self):
        super(QiniuSignIn, self).__init__('qiniu')
        self.service = OAuth2Service(
                name = 'qiniu',
                client_id = self.consumer_id,
                client_secret = self.consumer_secret,
                authorize_url = 'https://portal.qiniu.com/oauth/authorize',
                access_token_url = 'https://portal.qiniu.com/oauth/token',
                base_url = 'https://portal.qiniu.com/api/account/'
        )

    def authorize(self):
        return redirect(self.service.get_authorize_url(redirect_uri = self.get_callback_url()))

    def callback(self):
        if 'code' not in request.args:
            return None, None

        code = request.args['code']
        oauth_session = self.service.get_auth_session(
                data = {
                    'code': code,
                    'grant_type': 'authorization_code',
                    'redirect_uri': self.get_callback_url()
                },
                decoder = lambda c: json.loads(c)
        )
        me = oauth_session.get('info?access_token=' + oauth_session.access_token).json().get['data']
        return code, me
