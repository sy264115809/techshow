# encoding=utf-8
from datetime import datetime

from app import db


class Message(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    content = db.Column(db.String(128))
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    author = db.relationship('User', backref = db.backref('messages'))
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'))
    channel = db.relationship('Channel', backref = db.backref('messages'))
    relative_time = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default = datetime.now())

    def __init__(self, **kwargs):
        super(Message, self).__init__(**kwargs)

    def to_json(self):
        return {
            'id': self.id,
            'content': self.content,
            'author': {
                'id': self.author.id,
                'nickname': self.author.nickname,
                'avatar': self.author.avatar
            },
            'channel_id': self.channel_id,
            'relative_time': self.relative_time
        }
