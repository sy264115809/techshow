# coding=utf-8
from datetime import datetime
from time import mktime, strftime
from flask_login import current_user, current_app

from app import db, cache
from app.models.user import StreamStatus
from app.http.rong_cloud import ApiClient, ClientError


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

    def __init__(self, **kwargs):
        self.owner = current_user
        self.stream_id = current_user.stream_id
        super(Channel, self).__init__(**kwargs)

    def __repr__(self):
        return '<Channel %r>' % self.id

    @property
    def is_new(self):
        return self.status == ChannelStatus.initiate

    @property
    def is_publishing(self):
        return self.status == ChannelStatus.publishing

    @property
    def is_published(self):
        return self.status == ChannelStatus.published

    @property
    def is_closed(self):
        return self.status == ChannelStatus.closed

    @property
    def is_banned(self):
        return self.status == ChannelStatus.banned

    @property
    def stream(self):
        return self.owner.stream

    @cache.memoize(timeout = 10)
    def online_nums(self):
        if self.is_publishing:
            try:
                current_app.logger.info('Check Channel[%d] online nums', self.id)
                return len(ApiClient().chatroom_user_query(self.id)['users'])
            except ClientError as exc:
                current_app.logger.warning('Refresh channel[%d] online nums error: %s', self.id, exc)

    def live_urls(self):
        if self.is_publishing:
            return {
                'rtmp': self.stream.rtmp_live_urls()['ORIGIN'],
                'hls': self.stream.hls_live_urls()['ORIGIN'],
                'flv': self.stream.http_flv_live_urls()['ORIGIN']
            }

        return None

    def playback_url(self):
        if self.is_published:
            start = mktime(self.started_at.timetuple())
            end = mktime(self.stopped_at.timetuple())
            return {
                'hls': self.stream.hls_playback_urls(start_second = start, end_second = end)['ORIGIN']
            }

        return None

    def publish(self, callback_task = None):
        """设置频道为开始推流状态
        :param callback_task: 回调的celery subtask
        """
        if self.is_new:
            self.status = ChannelStatus.publishing
            self.started_at = datetime.now()
            self.owner.stream_status = StreamStatus.unavailable
            db.session.commit()
            if hasattr(callback_task, 'apply_async'):
                return callback_task.apply_async()
            return True
        return False

    def finish(self, callback_task = None):
        """设置频道为结束推流状态
        :param callback_task: 回调的celery subtask
        """
        if self.is_publishing:
            self.status = ChannelStatus.published
            self.stopped_at = datetime.now()
            self.owner.stream_status = StreamStatus.available
            self.calc_duration()
            db.session.commit()
            if hasattr(callback_task, 'apply_async'):
                return callback_task.apply_async()
            return True
        return False

    def banned(self, callback_task = None):
        """封禁房间.
        :param callback_task: 回调的celery subtask
        """
        # 掐断直播
        self.stream.disable().enable()
        self.finish(callback_task)
        self.status = ChannelStatus.banned
        db.session.commit()
        return True

    def release(self):
        """解封房间
        """
        if self.is_banned:
            self.status = ChannelStatus.published
            db.session.commit()
            return True
        return False

    def close(self):
        """关闭房间
        """
        if self.is_published:
            self.status = ChannelStatus.closed
            db.session.commit()
            return True
        return False

    def calc_duration(self, force = False):
        """根据pili stream的segment信息计算真实的持续时间,开始时间和结束时间.
        默认在duration不为空时不进行计算, 除非参数force被置为True.
        :param force: 强制计算duration
        """
        if self.duration is None or force:
            start = int(mktime(self.started_at.timetuple()))
            end = int(mktime(self.stopped_at.timetuple()))
            segment_info = self.stream.segments(start_second = start, end_second = end)

            self.duration = segment_info['duration']

            segments = segment_info['segments']
            if segments:
                self.started_at = strftime('%Y-%m-%d %H:%M:%S', segments[-1]['start'])
                self.stopped_at = strftime('%Y-%m-%d %H:%M:%S', segments[0]['end'])
            else:
                self.delete()

    def check_stream_alive(self):
        """检查流是否存活
        """
        if not self.is_publishing:
            return False
        elif self.stream.disabled or self.stream.status()['status'] == 'disconnected':
            return False
        else:
            return True

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
        base_info = {
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
            'created_at': mktime(self.created_at.timetuple()),
        }
        return {
            'channel': base_info,
            'is_liked': self.is_like(current_user),
            'live': self.live_urls(),
            'playback': self.playback_url(),
            'live_time': (datetime.now() - self.started_at).seconds if self.is_publishing else None,
            'online_nums': self.online_nums()
        }

    @staticmethod
    def assemble_channels(channels):
        return map(lambda c: c.to_json(), channels)


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
