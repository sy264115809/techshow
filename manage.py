# coding=utf8
from app import create_app, db
from config import load_config
from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand

app = create_app(load_config())

migrate = Migrate(app, db)

manager = Manager(app)
manager.add_command('db', MigrateCommand)

if __name__ == '__main__':
    manager.run()
