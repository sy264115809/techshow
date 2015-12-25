from default import Config
import os


class DevelopmentConfig(Config):
    DEBUG = True

    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_HOUSEDB_URL') or 'mysql://username:password@server/db'
    SQLALCHEMY_TRACK_MODIFICATIONS = True

    PILI_ACCESS_KEY = ''
    PILI_SECRET_KEY = ''
    PILI_HUB_NAME = ''
