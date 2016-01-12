import os
from app import create_app, celery

app = create_app(os.getenv('TECHSHOW_CONFIG') or 'default')
app.app_context().push()
