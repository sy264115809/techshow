import os


class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'aJuGcEdzcG9WsF7ZXojoFvaDZDJzkseCwXMeQgsmTnkbqvRDYr'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
