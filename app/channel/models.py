# encoding=utf8
from datetime import datetime
from time import mktime

from app import db
from app.channel import constants as CHANNEL

channel_user_like = db.Table('channel_user_like',
                             db.Column('channel_id', db.Integer, db.ForeignKey('channel.id')),
                             db.Column('user_id', db.Integer, db.ForeignKey('user.id')))


class Channel(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(32))
    thumbnail = db.Column(db.String(128))
    desc = db.Column(db.String(255))
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    owner = db.relationship('User', backref = db.backref('channels'))
    status = db.Column(db.Integer, default = CHANNEL.INITIATE)

    stream_id = db.Column(db.String(64))

    quality = db.Column(db.Integer)
    orientation = db.Column(db.Integer)
    duration = db.Column(db.String(16))

    started_at = db.Column(db.DateTime)
    stopped_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default = datetime.now())

    liked_users = db.relationship('User',
                                  secondary = channel_user_like,
                                  backref = db.backref('like_channels', lazy = 'dynamic'),
                                  lazy = 'dynamic')

    def __init__(self, title, owner, **kwargs):
        self.title = title
        self.owner = owner
        self.stream_id = owner.stream_id
        super(Channel, self).__init__(**kwargs)

    @property
    def is_published(self):
        return self.status == CHANNEL.PUBLISHED

    @property
    def is_publishing(self):
        return self.status == CHANNEL.PUBLISHING

    def like(self, user):
        if not self.is_like(user):
            self.liked_users.append(user)
            return self

    def dislike(self, user):
        if self.is_like(user):
            self.liked_users.remove(user)
            return self

    def is_like(self, user):
        return self.liked_users.filter(channel_user_like.c.user_id == user.id).count() > 0

    def to_json(self):
        return {
            'id': self.id,
            'title': self.title,
            'thumbnail': self.thumbnail,
            'desc': self.desc,
            'quality': self.quality,
            'orientation': self.orientation,
            'duration': self.duration,
            'status': self.status,
            'owner': self.owner.to_json(),
            'started_at': mktime(self.started_at.timetuple()) if self.started_at else None,
            'stopped_at': mktime(self.stopped_at.timetuple()) if self.stopped_at else None,
            'created_at': mktime(self.created_at.timetuple())
        }
