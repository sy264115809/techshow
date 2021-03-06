# coding=utf-8
import logging
from datetime import datetime
from time import mktime, strftime, localtime
from flask_login import current_user, current_app
from celery.utils.log import get_task_logger

from app import db, cache, celery
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
    calculating = 5


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
        self.thumbnail = Thumbnail.random_url()
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
    def is_calculating(self):
        return self.status == ChannelStatus.calculating

    @property
    def stream(self):
        return self.owner.stream

    @cache.memoize(timeout = 10)
    def online_nums(self):
        if self.is_publishing:
            try:
                nums = len(ApiClient().chatroom_user_query(self.id)['users'])
                current_app.logger.info('Check Channel[%d] online nums: %d', self.id, nums)
                return nums
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

    def publish(self):
        """设置频道为开始推流状态
        """
        if self.is_new:
            self.status = ChannelStatus.publishing
            self.started_at = datetime.now()
            self.owner.stream_status = StreamStatus.unavailable
            db.session.commit()
            current_app.logger.info('publish channel[%d]', self.id)
            return monitor_channel.apply_async(args = [self.id], countdown = 30)
        current_app.logger.debug('can not publish channel[%d] with status[%d]', self.id, self.status)
        return False

    def resume(self):
        """恢复频道为开始推流状态
        """
        if self.is_calculating or self.is_published:
            self.status = ChannelStatus.publishing
            self.owner.stream_status = StreamStatus.unavailable
            db.session.commit()
            current_app.logger.info('resume channel[%d] with status[%d]', self.id, self.status)
            return monitor_channel.apply_async(args = [self.id], countdown = 10)
        current_app.logger.debug('can not resume channel[%d] with status[%d]', self.id, self.status)
        return False

    def finish(self):
        """设置频道为结束推流状态
        """
        if self.is_publishing:
            self.status = ChannelStatus.calculating
            self.stopped_at = datetime.now()
            self.owner.stream_status = StreamStatus.available
            db.session.commit()
            current_app.logger.info('finish channel[%d]', self.id)
            return calculate_duration.apply_async(args = [self.id], countdown = 60)
        current_app.logger.debug('can not finish channel[%d] with status[%d]', self.id, self.status)
        return False

    def disable(self):
        """封禁房间.
        """
        # 掐断直播
        self.owner.disable_stream()
        self.status = ChannelStatus.banned
        self.stopped_at = datetime.now()
        self.owner.stream_status = StreamStatus.unavailable
        db.session.commit()
        current_app.logger.info('disable channel[%d]', self.id)
        return calculate_duration.apply_async(args = [self.id], countdown = 60)

    def enable(self):
        """解封房间
        """
        if self.is_banned:
            self.status = ChannelStatus.published
            db.session.commit()
            current_app.logger.info('enable channel[%d]', self.id)
            return True
        current_app.logger.debug('can not enable channel[%d] with status[%d]', self.id, self.status)
        return False

    def close(self):
        """关闭房间
        """
        if self.is_published:
            self.status = ChannelStatus.closed
            db.session.commit()
            current_app.logger.info('close channel[%d]', self.id)
            return True
        current_app.logger.debug('can not close channel[%d] with status[%d]', self.id, self.status)
        return False

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


logger = get_task_logger(__name__)


@celery.task(bind = True, max_retries = None)
def monitor_channel(self, channel_id):
    """监视频道所对应的流是否还处于连接或可用状态,
    防止客户端没有调用finish接口导致已经停止推流的频道还处于直播状态.
    应通过monitor_channel.delay嗲用
    :param self: celery task
    :param channel_id: 监控的频道id
    """
    channel = Channel.query.get(channel_id)
    resp = 'channel dose not need monitor'
    if channel and channel.is_publishing:
        logger.debug('monitor channel[%d]', channel.id)
        if channel.check_stream_alive():
            logger.debug('channel %d is alive, retry later', channel.id)
            raise self.retry(countdown = 10)
        else:
            resp = 'finish channel, monitor done'
            channel.finish()
    return {
        'action': resp,
        'channel_id': channel_id,
    }


@celery.task
def calculate_duration(channel_id):
    """根据pili stream的segment信息计算真实的持续时间,开始时间和结束时间.
    默认在duration不为空时不进行计算, 除非参数force被置为True.
    :param channel_id:要计算duration的频道
    """
    channel = Channel.query.with_for_update().get(channel_id)
    resp = 'channel does not need calculate'
    if channel and not channel.is_publishing:
        start = int(mktime(channel.started_at.timetuple()))
        end = int(mktime(channel.stopped_at.timetuple()))
        segment_info = channel.stream.segments(start_second = start, end_second = end)
        duration = segment_info['duration']

        if duration == 0:
            db.session.delete(channel)
            db.session.commit()
            resp = 'calculate then delete empty channel'
        else:
            channel.duration = duration
            segments = segment_info['segments']
            channel.started_at = strftime('%Y-%m-%d %H:%M:%S', localtime(segments[-1]['start']))
            channel.stopped_at = strftime('%Y-%m-%d %H:%M:%S', localtime(segments[0]['end']))
            if not channel.is_banned:
                channel.status = ChannelStatus.published
            db.session.commit()
            resp = 'calculate done'
    return {
        'action': resp,
        'channel_id': channel_id
    }


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    reporter = db.relationship('User', foreign_keys = [reporter_id],
                               backref = db.backref('report_complaints', lazy = 'dynamic'))
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'))
    channel = db.relationship('Channel', backref = db.backref('complaints', lazy = 'dynamic'))
    reason_type = db.Column(db.Integer)
    reason = db.Column(db.Text)
    handler_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    handler = db.relationship('User', foreign_keys = [handler_id],
                              backref = db.backref('handle_complaints', lazy = 'dynamic'))
    created_at = db.Column(db.DateTime, default = datetime.now)

    def __init__(self, **kwargs):
        super(Complaint, self).__init__(**kwargs)


class Thumbnail(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    key = db.Column(db.String(128), index = True)
    domain = db.Column(db.String(128))
    name = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default = datetime.now)

    def __init__(self, **kwargs):
        self.domain = current_app.config['QINIU_DOMAIN']
        super(Thumbnail, self).__init__(**kwargs)

    @property
    def url(self):
        return 'http://%s/%s' % (self.domain, self.key)

    @staticmethod
    def random_url():
        amount = Thumbnail.query.count()
        if amount == 0:
            return None

        thumbnail = Thumbnail.query.order_by(db.func.rand()).first()
        return thumbnail.url
