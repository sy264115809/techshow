# coding=utf-8
from datetime import datetime
from time import mktime

from app import db


class ChannelStatus(object):
    """Channel Status Enum
    """
    initiate = 0
    publishing = 1
    published = 2
    closed = 3
    banned = 4


# 点赞关联表
channel_user_like = db.Table(
        'channel_user_like',
        db.Column('channel_id', db.Integer, db.ForeignKey('channel.id')),
        db.Column('user_id', db.Integer, db.ForeignKey('user.id'))
)


class Channel(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(32))
    thumbnail = db.Column(db.String(128))
    desc = db.Column(db.String(255))
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    owner = db.relationship('User', backref = db.backref('channels'))
    status = db.Column(db.Integer, default = ChannelStatus.initiate)

    stream_id = db.Column(db.String(64))

    quality = db.Column(db.Integer)
    orientation = db.Column(db.Integer)
    duration = db.Column(db.String(16))

    visit_count = db.Column(db.Integer, default = 0)
    like_count = db.Column(db.Integer, default = 0)

    started_at = db.Column(db.DateTime)
    stopped_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default = datetime.now)

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
        return self.status == ChannelStatus.published

    @property
    def is_publishing(self):
        return self.status == ChannelStatus.publishing

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
            'visit_count': self.visit_count,
            'like_count': self.like_count,
            'started_at': mktime(self.started_at.timetuple()) if self.started_at else None,
            'stopped_at': mktime(self.stopped_at.timetuple()) if self.stopped_at else None,
            'created_at': mktime(self.created_at.timetuple())
        }


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    reporter = db.relationship('User', backref = db.backref('complaints', lazy = 'dynamic'))
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'))
    channel = db.relationship('Channel', backref = db.backref('complaints', lazy = 'dynamic'))
    reason_type = db.Column(db.Integer)
    reason = db.Column(db.Text)

    def __init__(self, **kwargs):
        super(Complaint, self).__init__(**kwargs)
