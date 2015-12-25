# encoding=utf8

from datetime import datetime
from time import mktime

from flask import Blueprint, current_app, request, json
from flask_login import login_required, current_user
from pili import *

from app import db
from app.channel import constants as CHANNEL
from app.channel.models import Channel
from app.user import constants as USER
from app.helper import success, bad_request, unauthorized, max_number_of_channel, channel_not_found
from app.models.settings import Setting, SETTING_MAX_CHANNEL_NUMS

channels_endpoint = Blueprint('channel', __name__, url_prefix = '/channels')


@channels_endpoint.route('', methods = ['POST'])
@login_required
def create_channel():
    title = request.json.get('title')
    if title is None:
        return bad_request("missing argument 'title'")

    quality = request.json.get('quality')
    if quality is None:
        return bad_request("missing argument 'quality'")

    orientation = request.json.get('orientation')
    if orientation is None:
        return bad_request("missing arguments 'orientation'")

    max_nums = Setting.get_setting(SETTING_MAX_CHANNEL_NUMS, current_app.config['SETTING_MAX_CHANNEL_NUMS'])
    if not Channel.query.filter_by(stopped_at = None).count() < max_nums:
        return max_number_of_channel()

    user = current_user
    if user.stream_id:
        stream = __get_stream(user.stream_id)
    else:
        stream = __create_dynamic_stream()
        user.stream_id = stream.id

    Channel.query.filter_by(status = CHANNEL.INITIATE).delete()
    channel = Channel(title = title, owner = user)
    channel.quality = quality
    channel.orientation = orientation
    db.session.add(channel)
    db.session.commit()

    return success({
        'channel': channel.to_json(),
        'stream': json.loads(stream.to_json())
    })


@channels_endpoint.route('/<int:channel_id>', methods = ['GET'])
@login_required
def get_channel(channel_id):
    channel = Channel.query.get(channel_id)
    if channel is None:
        return channel_not_found()

    stream = __get_stream(channel.stream_id)
    return success({
        'channel': channel.to_json(),
        'stream': json.loads(stream.to_json())
    })


@channels_endpoint.route('/<int:channel_id>/status', methods = ['GET'])
@login_required
def get_channel_status(channel_id):
    """
    返回一个channel的状态:
    0 - init:       该channel刚刚建立,但未推送;
    1 - publishing: 该channel处于直播状态;
    2 - published:  该channel处于非直播状态;
    3 - closed:     该channel已被用户关闭;
    4 - banned:     该channel已被管理员禁止, 并返回原因;

    :param channel_id: 查询的channel id
    :type channel_id: int
    """
    channel = Channel.query.get(channel_id)
    if channel is None:
        return channel_not_found()

    return success({
        'status': channel.status
    })


@channels_endpoint.route('/<int:channel_id>/publish', methods = ['POST'])
@login_required
def publish(channel_id):
    channel = Channel.query.get(channel_id)
    if channel is None:
        return channel_not_found()

    if not channel.owner == current_user:
        return unauthorized()

    if channel.status != CHANNEL.INITIATE:
        return bad_request('channel is not initiate')

    Channel.query.filter_by(stream_id = channel.stream_id, status = CHANNEL.PUBLISHING).update({
        'stopped_at': datetime.now(),
        'status': CHANNEL.PUBLISHED
    })

    channel.started_at = datetime.now()
    channel.owner.stream_status = USER.STREAM_UNAVAILABLE
    channel.status = CHANNEL.PUBLISHING
    db.session.commit()
    return success()


@channels_endpoint.route('/<int:channel_id>/finish', methods = ['POST'])
@login_required
def finish(channel_id):
    channel = Channel.query.get(channel_id)
    if channel is None:
        return channel_not_found()

    if not channel.owner == current_user:
        return unauthorized()

    if channel.status != CHANNEL.PUBLISHING:
        return bad_request('channel is not publishing')

    channel.stopped_at = datetime.now()
    channel.owner.stream_status = USER.STREAM_AVAILABLE
    channel.status = CHANNEL.PUBLISHED
    db.session.commit()
    return success()


@channels_endpoint.route('/publishing', methods = ['GET'])
@login_required
def get_publishing_channels():
    """
    获取所有正在直播的列表
    :return:
    """
    publishing_channels = Channel.query.filter_by(status = CHANNEL.PUBLISHING).all()
    publishing_channel_list = []
    for channel in publishing_channels:
        publishing_channel_list.append(channel.to_json())

    return success({
        'count': len(publishing_channel_list),
        'publishing_channels': publishing_channel_list
    })


@channels_endpoint.route('/published', methods = ['GET'])
@login_required
def get_published_channels():
    """
    获取所有直播结束的列表
    :return:
    """
    published_channels = Channel.query.filter_by(status = CHANNEL.PUBLISHED).all()
    published_channel_list = []
    for channel in published_channels:
        published_channel_list.append(channel.to_json())

    return success({
        'count': len(published_channel_list),
        'published_channels': published_channel_list
    })


@channels_endpoint.route('/<int:channel_id>/live', methods = ['GET'])
@login_required
def get_channel_live_urls(channel_id):
    """
    指定channel的直播地址(rtmp,hls,flv)
    :param channel_id:查询的channel的id
    :type channel_id:int
    :return:
    """
    channel = Channel.query.get(channel_id)
    if channel is None:
        return channel_not_found()

    if channel.status != CHANNEL.PUBLISHING:
        return bad_request('channel is not live')

    stream = __get_stream(channel.stream_id)
    return success({
        'rtmp': stream.rtmp_live_urls()['ORIGIN'],
        'hls': stream.hls_live_urls()['ORIGIN'],
        'flv': stream.http_flv_live_urls()['ORIGIN']
    })


@channels_endpoint.route('/<int:channel_id>/playback', methods = ['GET'])
def get_channel_playback_url(channel_id):
    """
    指定channel的回放地址(hls)
    :param channel_id:查询的channel的id
    :type channel_id:int
    :return:
    """
    channel = Channel.query.get(channel_id)
    if channel is None:
        return channel_not_found()

    if channel.status != CHANNEL.PUBLISHING and channel.status != CHANNEL.PUBLISHED:
        return bad_request('channel is not live or published')

    start = mktime(channel.started_at.timetuple()) if channel.started_at else None
    end = mktime(channel.stopped_at.timetuple()) if channel.stopped_at else mktime(datetime.now().timetuple())
    stream = __get_stream(channel.stream_id)
    return success({
        'hls': stream.hls_playback_urls(start_second = start, end_second = end)['ORIGIN']
    })


def __get_stream(stream_id):
    return __hub().get_stream(stream_id)


def __create_dynamic_stream():
    return __hub().create_stream()


def __hub():
    credentials = Credentials(current_app.config['PILI_ACCESS_KEY'], current_app.config['PILI_SECRET_KEY'])
    return Hub(credentials, current_app.config['PILI_HUB_NAME'])
