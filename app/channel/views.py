# encoding=utf8

from datetime import datetime, timedelta
from time import mktime

from flask import Blueprint, current_app, request, json
from flask_login import login_required, current_user
from pili import *

from app import db
from app.channel import constants as CHANNEL
from app.channel.models import Channel
from app.http_utils.response import success, bad_request, unauthorized, max_number_of_channel, channel_not_found, \
    rong_cloud_failed
from app.http_utils.request import paginate, query_params, rule
from app.message.models import Message
from app.models.settings import Setting, SETTING_MAX_CHANNEL_NUMS
from app.rong_cloud import ApiClient, ClientError
from app.user import constants as USER

channels_endpoint = Blueprint('channel', __name__, url_prefix = '/channels')


@channels_endpoint.route('', methods = ['POST'])
@login_required
def create_channel():
    """
    创建一个新的频道
    :return:
    """
    title = request.json.get('title')
    if title is None:
        return bad_request("missing argument 'title'")

    quality = request.json.get('quality')
    if quality is None:
        return bad_request("missing argument 'quality'")

    orientation = request.json.get('orientation')
    if orientation is None:
        return bad_request("missing arguments 'orientation'")

    max_nums = Setting.get_setting(SETTING_MAX_CHANNEL_NUMS, current_app.config.get(SETTING_MAX_CHANNEL_NUMS))
    if not Channel.query.filter_by(stopped_at = None).count() < max_nums:
        return max_number_of_channel()

    user = current_user
    if user.stream_id:
        stream = _get_stream(user.stream_id)
    else:
        stream = _create_dynamic_stream()
        user.stream_id = stream.id
        db.session.add(user)

    # 删除所有该用户的其他处于'新建'状态的频道
    Channel.query.filter_by(owner = user, status = CHANNEL.INITIATE).delete()

    # 新建频道
    channel = Channel(title = title, owner = user, quality = quality, orientation = orientation)
    db.session.add(channel)
    db.session.commit()

    return success({
        'channel': channel.to_json(),
        'stream': json.loads(stream.to_json())
    })


@channels_endpoint.route('', methods = ['GET'])
@login_required
def get_channels():
    """
    按条件查询频道. 支持的query params:
    id - 频道id
    owner - 频道主人的id
    status - 频道状态(只允许状态为1,2)
        0 - init:       该channel刚刚建立,但未推送;
        1 - publishing: 该channel处于直播状态;
        2 - published:  该channel处于非直播状态;
        3 - closed:     该channel已被用户关闭;
        4 - banned:     该channel已被管理员禁止;

    p - 返回条目的起始页, 默认1
    l - 返回条目数量限制, 默认10
    :return:
    """

    rules = [
        rule('id', 'id'),
        rule('owner_id', 'owner'),
        rule('status', 'status', allow = [str(CHANNEL.PUBLISHING), str(CHANNEL.PUBLISHED)])
    ]
    q, bad = query_params(*rules)
    if bad:
        return bad_request(bad)

    channels = Channel.query.filter_by(**q).order_by(Channel.started_at.desc()).paginate(*paginate()).items
    return _return_channels(channels)


@channels_endpoint.route('/my', methods = ['GET'])
@login_required
def get_my_channels():
    """
    查询我的频道. 支持的query params:
    status - 频道状态
        0 - init:       该channel刚刚建立,但未推送;
        1 - publishing: 该channel处于直播状态;
        2 - published:  该channel处于非直播状态;
        3 - closed:     该channel已被用户关闭;
        4 - banned:     该channel已被管理员禁止;

    l - 返回条目数量限制, 默认10
    p - 返回条目的起始页, 默认1
    :return:
    """

    rules = [
        rule('status', 'status')
    ]
    q, bad = query_params(*rules)
    if bad:
        return bad_request(bad)

    q['owner'] = current_user

    channels = Channel.query.filter_by(**q).order_by(Channel.started_at.desc()).paginate(*paginate()).items
    return _return_channels(channels)


@channels_endpoint.route('/publish', methods = ['POST'])
@login_required
def publish():
    """
    开始推流
    :return:
    """
    channel_id = request.json.get('id')
    if channel_id is None:
        return bad_request('missing argument "id"')

    channel = Channel.query.get(channel_id)
    if channel is None:
        return channel_not_found()

    if not channel.owner == current_user:
        return unauthorized()

    if channel.status != CHANNEL.INITIATE:
        return bad_request('channel is not at initiate status')

    # 将其他正在使用该stream进行直播的房间设置为推流完毕
    Channel.query.filter_by(stream_id = channel.stream_id, status = CHANNEL.PUBLISHING).update({
        'stopped_at': datetime.now(),
        'status': CHANNEL.PUBLISHED
    })

    # 在融云中创建一个聊天室
    try:
        ApiClient().chatroom_create({
            channel.id: channel.title
        })
    except ClientError:
        return rong_cloud_failed()

    channel.started_at = datetime.now()
    channel.owner.stream_status = USER.STREAM_UNAVAILABLE
    channel.status = CHANNEL.PUBLISHING
    db.session.commit()

    return success()


@channels_endpoint.route('/finish', methods = ['POST'])
@login_required
def finish():
    """
    结束推流
    :return:
    """
    channel_id = request.json.get('id')
    if channel_id is None:
        return bad_request('missing argument "id"')

    channel = Channel.query.get(channel_id)
    if channel is None:
        return channel_not_found()

    if not channel.owner == current_user:
        return unauthorized()

    if not channel.is_publishing:
        return bad_request('channel is not publishing')

    channel.stopped_at = datetime.now()
    channel.owner.stream_status = USER.STREAM_AVAILABLE
    channel.status = CHANNEL.PUBLISHED
    db.session.commit()
    return success()


@channels_endpoint.route('/messages', methods = ['GET'])
def get_channel_messages():
    """
    指定channel的消息列表,默认返回自起始时间算起10s内的消息列表
    :param channel_id:查询的channel的id
    :type channel_id:int
    :return:
    """
    channel_id = request.json.get('id')
    if channel_id is None:
        return bad_request('missing argument "id"')

    channel = Channel.query.get(channel_id)
    if channel is None:
        return channel_not_found()

    start = request.args.get('start') or 0

    start_time = channel.started_at + timedelta(seconds = start)
    end_time = start_time + timedelta(seconds = 10)

    messages = Message.query.filter(Message.created_at >= start_time, Message.created_at <= end_time) \
        .order_by(Message.created_at.desc()).all()
    return success({
        'messages': messages,
        'offset': start
    })


def _get_stream(stream_id):
    return _hub().get_stream(stream_id)


def _create_dynamic_stream():
    return _hub().create_stream()


def _hub():
    credentials = Credentials(current_app.config['PILI_ACCESS_KEY'], current_app.config['PILI_SECRET_KEY'])
    return Hub(credentials, current_app.config['PILI_HUB_NAME'])


def _return_channels(channels):
    if not len(channels):
        return channel_not_found()

    res = list()
    for channel in channels:
        stream = _get_stream(channel.stream_id)
        # 直播地址
        live = None
        if channel.is_publishing:
            live = {
                'rtmp': stream.rtmp_live_urls()['ORIGIN'],
                'hls': stream.hls_live_urls()['ORIGIN'],
                'flv': stream.http_flv_live_urls()['ORIGIN']
            }

        # 回放地址
        playback = None
        if channel.is_publishing or channel.is_published:
            start = mktime(channel.started_at.timetuple())
            end = mktime(channel.stopped_at.timetuple()) if channel.is_published else mktime(datetime.now().timetuple())
            playback = {
                'hls': stream.hls_playback_urls(start_second = start, end_second = end)['ORIGIN']
            }

        c = {
            'channel': channel.to_json(),
            'live': live,
            'playback': playback,
        }

        # 如果当前用户就是频道属主, 添加stream信息
        if channel.owner == current_user:
            c['stream'] = json.loads(stream.to_json())

        res.append(c)

    return success({
        'count': len(res),
        'channels': res
    })
