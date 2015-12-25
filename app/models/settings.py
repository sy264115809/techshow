# encoding=utf8
from app import db

SETTING_MAX_CHANNEL_NUMS = 'SETTING_MAX_ROOM_NUMS'


class Setting(db.Model):
    key = db.Column(db.String(128), primary_key = True)
    value = db.Column(db.String(128))
    humanized = db.Column(db.String(128))

    def __init__(self, key, value, humanized):
        self.key = key
        self.value = value
        self.humanized = humanized

    @classmethod
    def get_setting(cls, key, default = None):
        setting = cls.query.get(key)
        return setting if setting else default
