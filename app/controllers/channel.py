# coding=utf-8

from datetime import datetime
from time import mktime

from pili import *

from flask import Blueprint, current_app, request, json
from flask_login import login_required, current_user

from app import db
from app.models.channel import Channel, ChannelStatus, Complaint
from app.models.user import StreamStatus
from app.models.message import Message
from app.models.setting import Setting, SETTING_MAX_CHANNEL_NUMS, SETTING_SEND_MESSAGE_FREQUENCY
from app.http.request import paginate, Rule, parse_params, parse_int
from app.http.response import success, MaxChannelTouched, ChannelNotFound, ChannelInaccessible, Unauthorized, \
    BadRequest, RongCloudError, MessageTooFrequently
from app.http.rong_cloud import ApiClient, ClientError

channels_endpoint = Blueprint('channels', __name__, url_prefix = '/channels')


@channels_endpoint.route('', methods = ['POST'])
@login_required
def create_channel():
    """创建一个新的频道.
    支持的json参数:
    title - 必选, 频道的标题
    quality - 可选, 频道的质量
    orientation - 可选, 频道的屏幕方向
    """
    q = parse_params(
            request.json,
            Rule('title', must = True),
            Rule('quality'),
            Rule('orientation')
    )

    # 检查是否达到最大同时房间数
    max_nums = Setting.get_setting(
            SETTING_MAX_CHANNEL_NUMS,
            current_app.config.get(SETTING_MAX_CHANNEL_NUMS)
    )
    if Channel.query.filter_by(stopped_at = None).count() >= max_nums:
        raise MaxChannelTouched()

    # get or create stream
    user = current_user
    if user.stream_id:
        stream = _get_stream(user.stream_id)
    else:
        stream = _create_dynamic_stream()
        user.stream_id = stream.id

    # 删除所有该用户的其他处于'新建'状态的频道
    Channel.query.filter_by(owner = user, status = ChannelStatus.initiate).delete()

    # 新建频道
    channel = Channel(owner = user, **q)
    db.session.add(channel)
    db.session.commit()

    return success({
        'channel': channel.to_json(),
        'stream': json.loads(stream.to_json())
    })


@channels_endpoint.route('/live', methods = ['GET'])
@login_required
def get_live_channels():
    """按条件查询直播频道.
    支持的query params:
    owner_id - 可选, 频道主人的id
    p - 返回条目的起始页, 默认1
    l - 返回条目数量限制, 默认10
    """
    q = parse_params(request.args, Rule('owner_id'))
    q['status'] = ChannelStatus.publishing
    channels = Channel.query.filter_by(**q).order_by(Channel.started_at.desc()).paginate(*paginate()).items
    ret = _assemble_channels(channels)
    return success({
        'count': len(ret),
        'channels': ret
    })


@channels_endpoint.route('/playback', methods = ['GET'])
@login_required
def get_playback_channels():
    """按条件查询已结束直播频道.
    支持的query params:
    owner_id - 可选, 频道主人的id
    p - 返回条目的起始页, 默认1
    l - 返回条目数量限制, 默认10
    """
    q = parse_params(request.args, Rule('owner_id'))
    q['status'] = ChannelStatus.published
    channels = Channel.query.filter_by(**q).order_by(Channel.stopped_at.desc()).paginate(*paginate()).items
    ret = _assemble_channels(channels)
    return success({
        'count': len(ret),
        'channels': ret
    })


@channels_endpoint.route('/my', methods = ['GET'])
@login_required
def get_my_channels():
    """查询我的频道.
    支持的query params:
    status - 可选, 频道状态
        0 - init:       该channel刚刚建立,但未推送;
        1 - publishing: 该channel处于直播状态;
        2 - published:  该channel处于非直播状态;
        3 - closed:     该channel已被用户关闭;
        4 - banned:     该channel已被管理员禁止;
    l - 可选, 返回条目数量限制, 默认10
    p - 可选, 返回条目的起始页, 默认1
    """
    q = parse_params(
            request.args,
            Rule(
                    param = 'status',
                    allow = [
                        str(ChannelStatus.initiate),
                        str(ChannelStatus.publishing),
                        str(ChannelStatus.published),
                        str(ChannelStatus.closed),
                        str(ChannelStatus.banned)
                    ]
            )
    )
    q['owner'] = current_user
    channels = Channel.query.filter_by(**q).order_by(Channel.started_at.desc()).paginate(*paginate()).items
    ret = _assemble_channels(channels)
    return success({
        'count': len(ret),
        'channels': ret
    })


@channels_endpoint.route('/access/<int:channel_id>', methods = ['POST'])
@login_required
def get_channel_info(channel_id):
    """访问频道.
    :param channel_id: 访问的频道id
    :type channel_id: int
    """
    channel = _get_channel(channel_id, access_control = True)
    channel.visit_count += 1
    db.session.commit()
    return success({
        'channel': _assemble_channel(channel)
    })


@channels_endpoint.route('/publish/<int:channel_id>', methods = ['POST'])
@login_required
def publish(channel_id):
    """开始推流.
    :param channel_id: 开始推流的频道id
    :type channel_id: int
    """

    channel = _get_channel(channel_id, must_owner = True)
    if channel.status != ChannelStatus.initiate:
        raise BadRequest('channel is not at initiate status')

    # 将其他正在使用该stream进行直播的房间设置为推流完毕
    Channel.query.filter_by(
            stream_id = channel.stream_id,
            status = ChannelStatus.publishing
    ).update({
        'stopped_at': datetime.now(),
        'status': ChannelStatus.published
    })

    # 在融云中创建一个聊天室
    try:
        # {'room_id':'room_name'}
        ApiClient().chatroom_create({
            channel.id: channel.title
        })
    except ClientError, e:
        current_app.logger.error('create rong cloud chatroom with error: [%s]' % e)
        raise RongCloudError

    channel.started_at = datetime.now()
    channel.owner.stream_status = StreamStatus.unavailable
    channel.status = ChannelStatus.publishing
    db.session.commit()

    return success()


@channels_endpoint.route('/finish/<int:channel_id>', methods = ['POST'])
@login_required
def finish(channel_id):
    """结束推流.
    :param channel_id: 结束推流的频道id
    :type channel_id: int
    """
    stopped_at = datetime.now()

    channel = _get_channel(channel_id, must_owner = True)
    if not channel.is_publishing:
        raise BadRequest('channel is not publishing')

    duration = 0
    start = mktime(channel.started_at.timetuple())
    end = mktime(stopped_at.timetuple())

    segments = _get_stream(channel.stream_id).segments(start_second = int(start), end_second = int(end))
    if isinstance(segments, list):
        for segment in segments:
            duration += segment['duration']
    else:
        duration = segments['duration']

    channel.stopped_at = stopped_at
    channel.duration = duration
    channel.owner.stream_status = StreamStatus.available
    channel.status = ChannelStatus.published
    db.session.commit()
    return success()


@channels_endpoint.route('/like/<int:channel_id>', methods = ['POST'])
@login_required
def like(channel_id):
    """频道点赞.
    :param channel_id: 点赞的频道id
    :type channel_id: int
    """
    channel = _get_channel(channel_id, access_control = True)
    # TODO:redis缓存
    ok = channel.like(current_user)
    if not ok:
        raise BadRequest('user has already liked this channel.')

    channel.like_count += 1
    db.session.commit()
    return success()


@channels_endpoint.route('/dislike/<int:channel_id>', methods = ['POST'])
@login_required
def dislike(channel_id):
    """取消频道点赞.
    :param channel_id: 取消点赞的频道id
    :type channel_id: int
    """
    channel = _get_channel(channel_id, access_control = True)
    # TODO:redis缓存
    ok = channel.dislike(current_user)
    if not ok:
        raise BadRequest('user has already disliked this channel.')

    channel.like_count -= 1
    db.session.commit()
    return success()


@channels_endpoint.route('/complain/<int:channel_id>', methods = ['POST'])
@login_required
def send_complain(channel_id):
    """举报频道.
    支持的query params:
    reason - 必选, 举报原因

    :param channel_id: 被举报的频道id
    :type channel_id: int
    """
    q = parse_params(request.json, Rule('reason', must = True))

    channel = _get_channel(channel_id, True)

    complain = Complaint(reporter = current_user, channel = channel, **q)
    db.session.add(complain)
    db.session.commit()
    # TODO:通知管理员
    return success()


@channels_endpoint.route('/messages/<int:channel_id>', methods = ['POST'])
@login_required
def send_message(channel_id):
    """发送消息
    支持的json参数:
    content - 必选, 消息内容
    offset - 当频道处于已结束推送状态时, 必选. 相对于视频开始时间的偏移.

    :param channel_id:发送消息的频道id
    :type channel_id:int
    """
    created_at = datetime.now()
    content = parse_params(request.json, Rule('content', must = True))['content']

    # 检查用户发言间隔是否超过阈值
    frequency = Setting.get_setting(
            SETTING_SEND_MESSAGE_FREQUENCY,
            current_app.config.get(SETTING_SEND_MESSAGE_FREQUENCY)
    )
    if (created_at - current_user.last_send_message_at).seconds < frequency:
        raise MessageTooFrequently()

    channel = _get_channel(channel_id, access_control = True)
    # if get channel, the status of channel is neither publishing nor published
    if channel.is_published:
        offset = parse_params(request.json, Rule('offset', must = True))['offset']
        if not isinstance(offset, int):
            raise BadRequest('argument offset should be int type')
    else:
        offset = (created_at - channel.started_at).seconds

    # 如果推流已结束,存入数据库及缓存
    # TODO redis
    message = Message(
            author = current_user,
            channel = channel,
            content = content,
            created_at = created_at,
            offset = offset
    )
    current_user.last_send_message_at = created_at
    db.session.add(message)
    db.session.commit()

    if channel.is_publishing:
        # 如果正在推流,调用融云发送聊天室消息
        try:
            msg = json.dumps({
                'content': content,
                'extra': {
                    'name': current_user.nickname,
                    'avatar': current_user.avatar
                }
            })
            ApiClient().message_chatroom_publish(
                    from_user_id = current_user.id,
                    to_chatroom_id = channel.id,
                    object_name = 'RC:TxtMsg',
                    content = msg
            )
        except ClientError, e:
            current_app.logger.info('user %d send message "%s" with error: %s', current_user.id, content, e)

    return success()


@channels_endpoint.route('/messages/<int:channel_id>', methods = ['GET'])
@login_required
def get_channel_messages(channel_id):
    """指定频道的消息列表.
    支持的query params:
    s - 可选, 相对起始时间, 默认为0, 单位秒
    o - 可选, 相对起始时间的偏移, 默认为10, 单位秒
    l - 可选, 返回的条目限制, 默认为不限制

    :param channel_id:查询的频道id
    :type channel_id:int
    """
    channel = _get_channel(channel_id, access_control = True)

    start = parse_int('s', default = 0, condition = lambda s: s >= 0)  # 相对起始时间
    offset = parse_int('o', default = 10, condition = lambda o: o > 0)  # 相对起始时间的便宜
    limit = parse_int('l', default = None, condition = lambda l: l > 0)  # 返回条目限制

    messages = Message.query.filter(
            Message.channel == channel,
            Message.offset >= start,
            Message.offset <= start + offset
    ).order_by(
            Message.created_at.desc()
    ).limit(limit).all()

    ret = map(lambda msg: msg.to_json(), messages)

    return success({
        'count': len(ret),
        'messages': ret,
        'start': start,
        'offset': offset,
        'limit': limit
    })


def _hub():
    credentials = Credentials(current_app.config['PILI_ACCESS_KEY'], current_app.config['PILI_SECRET_KEY'])
    return Hub(credentials, current_app.config['PILI_HUB_NAME'])


def _get_stream(stream_id):
    return _hub().get_stream(stream_id)


def _create_dynamic_stream():
    return _hub().create_stream()


def _assemble_channel(channel, need_url = True):
    stream = _get_stream(channel.stream_id)
    ret = {
        'channel': channel.to_json(),
        'is_liked': channel.is_like(current_user),
        'live': None,
        'playback': None
    }

    if need_url:
        # 直播地址
        if channel.is_publishing:
            live = {
                'rtmp': stream.rtmp_live_urls()['ORIGIN'],
                'hls': stream.hls_live_urls()['ORIGIN'],
                'flv': stream.http_flv_live_urls()['ORIGIN']
            }
            ret['live'] = live

        # 回放地址
        if channel.is_published:
            start = mktime(channel.started_at.timetuple())
            end = mktime(channel.stopped_at.timetuple())
            playback = {
                'hls': stream.hls_playback_urls(start_second = start, end_second = end)['ORIGIN']
            }
            ret['playback'] = playback

    return ret


def _assemble_channels(channels):
    if len(channels) == 0:
        raise ChannelNotFound()

    ret = list()
    for channel in channels:
        ret.append(_assemble_channel(channel, need_url = False))

    return ret


def _get_channel(channel_id, access_control = False, must_owner = False):
    channel = Channel.query.get(channel_id)

    if channel is None:
        raise ChannelNotFound()
    if access_control and not (channel.is_publishing or channel.is_published):
        raise ChannelInaccessible()
    if must_owner and channel.owner != current_user:
        raise Unauthorized()

    return channel
