# encoding=utf8

from datetime import datetime, timedelta
from time import mktime

from flask import Blueprint, current_app, request, json
from flask_login import login_required, current_user
from pili import *

from app import db
from app.channel import constants as CHANNEL
from app.channel.models import Channel, Complaint
from app.http_utils.response import success, bad_request, unauthorized, max_number_of_channel, channel_not_found, \
    rong_cloud_failed, channel_access_denied
from app.http_utils.request import paginate, rule, query_params, json_params, must_json_params, must_query_params
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


@channels_endpoint.route('/live', methods = ['GET'])
@login_required
def get_live_channels():
    """
    按条件查询直播频道. 支持的query params:
    owner - 频道主人的id

    p - 返回条目的起始页, 默认1
    l - 返回条目数量限制, 默认10
    :return:
    """

    rules = [
        rule('owner_id', 'owner'),
    ]
    q, bad = query_params(*rules)
    if bad:
        return bad_request(bad)

    q['status'] = CHANNEL.PUBLISHING

    channels = Channel.query.filter_by(**q).order_by(Channel.started_at.desc()).paginate(*paginate()).items
    return _return_channels(channels)


@channels_endpoint.route('/playback', methods = ['GET'])
@login_required
def get_playback_channels():
    """
    按条件查询已结束直播频道. 支持的query params:
    owner - 频道主人的id

    p - 返回条目的起始页, 默认1
    l - 返回条目数量限制, 默认10
    :return:
    """

    rules = [
        rule('owner_id', 'owner'),
    ]
    q, bad = query_params(*rules)
    if bad:
        return bad_request(bad)

    q['status'] = CHANNEL.PUBLISHED

    channels = Channel.query.filter_by(**q).order_by(Channel.stopped_at.desc()).paginate(*paginate()).items
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
        rule('status')
    ]
    q, bad = query_params(*rules)
    if bad:
        return bad_request(bad)

    q['owner'] = current_user

    channels = Channel.query.filter_by(**q).order_by(Channel.started_at.desc()).paginate(*paginate()).items
    return _return_channels(channels)


@channels_endpoint.route('/info', methods = ['GET'])
@login_required
def get_channel_info():
    """
    查询频道的流信息. 必须的query params:
    id - 查询的频道id
    :return:
    """
    rules = [
        rule('id')
    ]
    q, bad = must_query_params(*rules)
    if bad:
        return bad_request(bad)

    channel = Channel.query.get(q['id'])
    if channel is None:
        return channel_not_found()

    if not channel.is_publishing and not channel.is_published:
        return channel_access_denied()

    channel.visit_count += 1
    db.session.commit()

    return success({
        'channel': _assemble_channel(channel)
    })


@channels_endpoint.route('/publish', methods = ['POST'])
@login_required
def publish():
    """
    开始推流. 必须的query params:
    id - 开始推流的频道id
    :return:
    """
    rules = [
        rule('id')
    ]
    q, bad = must_json_params(*rules)
    if bad:
        return bad_request(bad)

    channel = Channel.query.get(q['id'])
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
    结束推流. 必须的query params:
    id - 结束推流的频道id
    :return:
    """
    rules = [
        rule('id')
    ]
    q, bad = must_json_params(*rules)
    if bad:
        return bad_request(bad)

    channel = Channel.query.get(q['id'])
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


@channels_endpoint.route('/like', methods = ['POST'])
@login_required
def like():
    """
    频道点赞. 必须的query params:
    id - 点赞的频道id
    :return:
    """
    rules = [
        rule('id')
    ]
    q, bad = must_json_params(*rules)
    if bad:
        return bad_request(bad)

    channel = Channel.query.get(q['id'])
    if channel is None:
        return channel_not_found()

    # TODO:redis缓存
    ok = channel.like(current_user)
    if ok:
        channel.like_count += 1
        db.session.commit()
        return success()

    return bad_request('user has already liked this channel.')


@channels_endpoint.route('/dislike', methods = ['POST'])
@login_required
def dislike():
    """
    取消频道点赞. 必须的query params:
    id - 取消点赞的频道id
    :return:
    """
    rules = [
        rule('id')
    ]
    q, bad = must_json_params(*rules)
    if bad:
        return bad_request(bad)

    channel = Channel.query.get(q['id'])
    if channel is None:
        return channel_not_found()

    # TODO:redis缓存
    ok = channel.dislike(current_user)
    if ok:
        channel.like_count -= 1
        db.session.commit()
        return success()

    return bad_request('user has already disliked this channel.')


@channels_endpoint.route('/complain', methods = ['POST'])
@login_required
def send_complain():
    """
    举报频道. 必须的query params:
    id - 被举报的频道id
    reason - 举报原因
    :return:
    """
    rules = [
        rule('id'),
        rule('reason')
    ]
    q, bad = must_json_params(*rules)
    if bad:
        return bad_request(bad)

    channel = Channel.query.get(q['id'])
    if channel is None:
        return channel_not_found()

    complain = Complaint(reporter = current_user, channel = channel, reason = q['reason'])
    db.session.add(complain)
    db.session.commit()
    # TODO:通知管理员
    return success()


@channels_endpoint.route('/messages', methods = ['GET'])
@login_required
def get_channel_messages():
    """
    指定channel的消息列表,默认返回自起始时间算起10s内的消息列表
    :param channel_id:查询的channel的id
    :type channel_id:int
    :return:
    """
    rules = [
        rule('id')
    ]
    q, bad = must_json_params(*rules)
    if bad:
        return bad_request(bad)

    channel = Channel.query.get(q['id'])
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

    ret = list()
    for channel in channels:
        ret.append(_assemble_channel(channel, need_url = False))

    return success({
        'count': len(ret),
        'channels': ret
    })


def _assemble_channel(channel, need_url = True):
    stream = _get_stream(channel.stream_id)

    ret = {
        'channel': channel.to_json(),
        'is_liked': channel.is_like(current_user),
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
