import os


class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'aJuGcEdzcG9WsF7ZXojoFvaDZDJzkseCwXMeQgsmTnkbqvRDYr'

    SQLALCHEMY_TRACK_MODIFICATIONS = True
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_RECORD_QUERIES = True

    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    CELERY_BROKER_URL = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
    CELERY_ACCEPT_CONTENT = ['pickle', 'json']

    PILI_ACCESS_KEY = os.environ.get('PILI_ACCESS_KEY')
    PILI_SECRET_KEY = os.environ.get('PILI_SECRET_KEY')
    PILI_HUB_NAME = os.environ.get('PILI_HUB_NAME')

    CACHE_TYPE = 'redis'
    CACHE_KEY_PREFIX = 'techshow'
    CACHE_REDIS_HOST = 'localhost'
    CACHE_REDIS_PORT = 6379

    OAUTH_CREDENTIALS = {
        'github': {
            'id': os.environ.get('OAUTH_GITHUB_ID'),
            'secret': os.environ.get('OAUTH_GITHUB_SECRET')
        },
        'qiniu': {
            'id': os.environ.get('OAUTH_QINIU_ID'),
            'secret': os.environ.get('OAUTH_QINIU_SECRET')
        }
    }

    QINIU_DOMAIN = os.environ.get('QINIU_DOMAIN')
    QINIU_BUCKET = os.environ.get('BUCKET')
    QINIU_ACCESS_KEY = os.environ.get('ACCESS_KEY')
    QINIU_SECRET_KEY = os.environ.get('SECRET_KEY')

    TECHSHOW_MAIL_SUBJECT_PREFIX = '[TechShow]'
    TECHSHOW_MAIL_SENDER = 'TechShow Admin <admin@techshow.com>'
    TECHSHOW_ADMIN = os.environ.get('TECHSHOW_ADMIN')
    TECHSHOW_MAX_CHANNELS = 50
    TECHSHOW_SEND_MESSAGE_FREQUENCY = 3

    ADMIN_QINIU = [
        'shaoyu@qiniu.com'
    ]
    ADMIN_GITHUB = [
        '264115809@qq.com'
    ]

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
                              'mysql://root:root@127.0.0.1:3306/techshow?charset=utf8'


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
                              'mysql://root:root@127.0.0.1:3306/techshow_test?charset=utf8'
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'mysql://root:root@127.0.0.1:3306/techshow?charset=utf8'

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)

        # email errors to the administrators
        import logging
        from logging.handlers import SMTPHandler
        credentials = None
        secure = None
        if getattr(cls, 'MAIL_USERNAME', None) is not None:
            credentials = (cls.MAIL_USERNAME, cls.MAIL_PASSWORD)
            if getattr(cls, 'MAIL_USE_TLS', None):
                secure = ()
        mail_handler = SMTPHandler(
                mailhost = (cls.MAIL_SERVER, cls.MAIL_PORT),
                fromaddr = cls.TECHSHOW_MAIL_SENDER,
                toaddrs = [cls.TECHSHOW_ADMIN],
                subject = cls.TECHSHOW_MAIL_SUBJECT_PREFIX + ' Application Error',
                credentials = credentials,
                secure = secure)
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)


class GunicornConfig(ProductionConfig):
    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)

        # add handler to redirect to gunicorn error
        import logging
        from logging import StreamHandler
        handler = StreamHandler()
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)
        app.logger.handlers.extend(logging.getLogger("gunicorn.error").handlers)


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'gunicorn': GunicornConfig,

    'default': DevelopmentConfig
}
