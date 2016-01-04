# encoding=utf-8

from default import Config
import os


class DevelopmentConfig(Config):
    DEBUG = True

    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_HOUSEDB_URL') or 'mysql://username:password@server/db?charset=utf8'
    SQLALCHEMY_TRACK_MODIFICATIONS = True

    PILI_ACCESS_KEY = ''
    PILI_SECRET_KEY = ''
    PILI_HUB_NAME = ''

    # oauth
    OAUTH = {
        'github': dict(
                name = 'github',
                base_url = 'https://api.github.com/',
                access_token_url = 'https://github.com/login/oauth/access_token',
                authorize_url = 'https://github.com/login/oauth/authorize',
                client_id = '',
                client_secret = '',
        ),
        'qiniu': dict(
                name = 'qiniu',
                base_url = 'https://portal.qiniu.com/api/account/',
                access_token_url = 'https://portal.qiniu.com/oauth/token',
                authorize_url = 'https://portal.qiniu.com/oauth/authorize',
                client_id = '',
                client_secret = '',
        )
    }

    # 融云
    RONG_CLOUD_APP_KEY = ''
    RONG_CLOUD_APP_SECRET = ''

    # 最大同时在线频道数目
    SETTING_MAX_CHANNEL_NUMS = 50
    # 用户发送消息的最小间隔
    SETTING_SEND_MESSAGE_FREQUENCY = 3
