# coding=utf8
import os

if os.path.exists('.env'):
    print('Importing environment from .env...')
    for line in open('.env'):
        var = line.strip().split('=')
        if len(var) == 2:
            os.environ[var[0]] = var[1]

from app import create_app, db, celery
from app.models.user import User
from app.models.channel import Channel
from flask_script import Manager, Shell
from flask_migrate import Migrate, MigrateCommand

app = create_app(os.getenv('TECHSHOW_CONFIG') or 'default')

migrate = Migrate(app, db)
manager = Manager(app)


def make_shell_context():
    return dict(app = app, db = db, User = User, Channel = Channel)


manager.add_command("shell", Shell(make_context = make_shell_context))
manager.add_command('db', MigrateCommand)

if __name__ == '__main__':
    manager.run()
