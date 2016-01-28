# encoding=utf-8
from datetime import datetime

from app import db, cache


class Message(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    content = db.Column(db.String(128))
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    author = db.relationship('User', backref = db.backref('messages'))
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'))
    channel = db.relationship('Channel', backref = db.backref('messages'))
    offset = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default = datetime.now)

    def __init__(self, **kwargs):
        super(Message, self).__init__(**kwargs)

    @classmethod
    @cache.memoize(60)
    def get_messages_by_offset(cls, channel_id, offset):
        return cls.query.options(db.joinedload('author')).filter_by(channel_id = channel_id, offset = offset).all()

    def to_json(self):
        return {
            'id': self.id,
            'content': self.content,
            'offset': self.offset,
            'author': {
                'id': self.author.id,
                'nickname': self.author.nickname,
                'avatar': self.author.avatar
            },
            'channel_id': self.channel_id
        }
