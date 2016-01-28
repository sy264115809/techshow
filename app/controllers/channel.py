# coding=utf-8
import logging
from random import randint, sample, choice
from string import ascii_letters, digits
from datetime import datetime

from flask import Blueprint, current_app, request, json, render_template, abort
from flask_login import login_required, current_user
from flask_mail import Message as EMessage
from celery.utils.log import get_task_logger

from app import db, celery, mail
from app.models.channel import Channel, ChannelStatus, Complaint
from app.models.message import Message
from app.http.request import paginate, Rule, parse_params, parse_int
from app.http.response import success, MaxChannelTouched, ChannelNotFound, ChannelInaccessible, Unauthorized, \
    BadRequest
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
    if Channel.query.filter_by(stopped_at = None).count() >= current_app.config['TECHSHOW_MAX_CHANNELS']:
        raise MaxChannelTouched()

    # 删除所有该用户的其他处于'新建'状态的频道
    Channel.query.filter_by(owner = current_user, status = ChannelStatus.initiate).delete()

    # 新建频道
    channel = Channel(**q)
    db.session.add(channel)
    db.session.commit()

    return success({
        'channel': channel.to_json(),
        'stream': json.loads(channel.stream.to_json())
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
    ret = Channel.assemble_channels(channels)
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
    ret = Channel.assemble_channels(channels)
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
    ret = Channel.assemble_channels(channels)
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
    channel = get_channel(channel_id, access_control = True)
    channel.visit_count += 1
    db.session.commit()
    return success({
        'channel': channel.to_json()
    })


@channels_endpoint.route('/publish/<int:channel_id>', methods = ['POST'])
@login_required
def publish(channel_id):
    """开始推流.
    :param channel_id: 开始推流的频道id
    :type channel_id: int
    """
    channel = get_channel(channel_id, must_owner = True)
    if not channel.is_new:
        raise BadRequest('channel is not at initiate status')

    resp = {}

    # 如果有当前流上有正在直播的房间, 将其结束
    occupancy = Channel.query.filter_by(stream_id = channel.stream_id, status = ChannelStatus.publishing).first()
    if occupancy:
        resp['calculate_occupancy_task'] = occupancy.finish().id
        resp['destroy_occupancy_chatroom_task'] = destroy_rongcloud_chatroom.apply_async(args = [occupancy.id]).id

    # 开始推流, 并在融云中创建一个聊天室
    resp['publish_monitor_task'] = channel.publish().id
    resp['publish_create_chatroom_task'] = create_rongcloud_chatroom.apply_async(args = [channel.id, channel.title]).id
    return success(resp)


@channels_endpoint.route('/finish/<int:channel_id>', methods = ['POST'])
@login_required
def finish(channel_id):
    """结束推流.
    :param channel_id: 结束推流的频道id
    :type channel_id: int
    """
    channel = get_channel(channel_id, must_owner = True)
    if not channel.is_publishing:
        raise BadRequest('channel is not at publishing status')

    resp = {
        'finish_calculate_task': channel.finish().id,
        'finish_destroy_chatroom_task': destroy_rongcloud_chatroom.apply_async(args = [channel.id]).id
    }
    return success(resp)


@channels_endpoint.route('/resume/<int:channel_id>', methods = ['POST'])
@login_required
def resume(channel_id):
    """
    恢复频道状态, 避免因客户端网络原因造成的断流而错误的将频道终结.
    :param channel_id: 要恢复状态的频道id
    :return:
    """
    channel = get_channel(channel_id, must_owner = True)
    if not (channel.is_published or channel.is_calculating):
        raise BadRequest('cannot resume channel while it is not at the published status')

    # 如果当前流上没有比当前频道更新的频道,说明这是一次RESUME操作,重置流的状态为直播中.
    if Channel.query.filter(Channel.stream_id == channel.stream_id, Channel.id > channel.id).count():
        raise BadRequest('cannot resume channel while it is not the newest')

    resp = {
        'resume_monitor_task': channel.resume().id,
        'resume_create_chatroom_task': create_rongcloud_chatroom.apply_async(args = [channel.id, channel.title]).id
    }
    return success(resp)


@channels_endpoint.route('/stream/<int:channel_id>', methods = ['GET'])
@login_required
def stream_status(channel_id):
    """查询留状态
    :param channel_id: 查询流状态的频道id
    :type channel_id: int
    """
    channel = get_channel(channel_id)
    return success({
        'disabled': channel.stream.disabled,
        'status': channel.stream.status()['status']
    })


@channels_endpoint.route('/like/<int:channel_id>', methods = ['POST'])
@login_required
def like(channel_id):
    """频道点赞.
    :param channel_id: 点赞的频道id
    :type channel_id: int
    """
    channel = get_channel(channel_id, access_control = True)
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
    channel = get_channel(channel_id, access_control = True)
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

    channel = get_channel(channel_id, True)

    complain = Complaint(reporter = current_user, channel = channel, **q)
    db.session.add(complain)
    db.session.commit()

    current_app.logger.info(channel.complaints.count())

    # send email to admin
    if channel.complaints.count() == 1:
        send_email('新的频道投诉', 'techshow@qiniu.com', 'mail/new_complaint.html', channel = channel)
        current_app.logger.info('send complaint[id:%d, content:%s] email to admin.', complain.id, complain.reason)

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
    # frequency = Setting.get_setting(
    #         SETTING_SEND_MESSAGE_FREQUENCY,
    #         current_app.config.get(SETTING_SEND_MESSAGE_FREQUENCY)
    # )
    # if (created_at - current_user.last_send_message_at).seconds < frequency:
    #     raise MessageTooFrequently()

    channel = get_channel(channel_id, access_control = True)
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
        # @task 如果正在推流,调用融云发送聊天室消息
        send_task = send_rongcloud_message.delay(current_user.id, current_user.nickname, current_user.avatar,
                                                 channel_id,
                                                 content)
        return success({
            'send_message_task': send_task.id
        })

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
    channel = get_channel(channel_id, access_control = True)

    start = parse_int('s', default = 1, condition = lambda s: s >= 1)  # 相对起始时间
    offset = parse_int('o', default = 10, condition = lambda o: o > 0)  # 相对起始时间的偏移
    limit = parse_int('l', default = None, condition = lambda l: l > 0)  # 返回条目限制

    # messages = Message.query.filter(
    #         Message.channel == channel,
    #         Message.offset >= start,
    #         Message.offset <= start + offset
    # ).order_by(
    #         Message.offset,
    #         Message.created_at.desc()
    # ).limit(limit).all()

    # ret = map(lambda msg: msg.to_json(), messages)

    ret = {}
    count = 0
    for o in range(start, start + offset):
        if o > channel.duration:
            break

        messages = Message.get_messages_by_offset(channel.id, o)
        if limit:
            messages = messages[-limit:]
        count += len(messages)
        ret[o] = map(lambda msg: msg.to_json(), messages)

    return success({
        'count': count,
        'messages': ret,
        'start': start,
        'offset': offset,
        'limit': limit
    })


@channels_endpoint.route('/task/<task_id>')
def task_status(task_id):
    task = celery.AsyncResult(task_id)
    return success({
        'task_state': task.state,
        'info': str(task.info)
    })


@channels_endpoint.route('/mock/sendmsg', methods = ['GET'])
def send_mock_msg():
    mock_users = [
        {'id': 1, 'name': '邵羽', 'avatar': 'https://avatars.githubusercontent.com/u/6114462?v=3'},
        {'id': 2, 'name': 'MistyL', 'avatar': 'https://avatars.githubusercontent.com/u/16283083?v=3'},
        {'id': 3, 'name': 'Kivenhaoyu', 'avatar': 'https://avatars.githubusercontent.com/u/8874808?v=3'},
        {'id': 4, 'name': '俞杰', 'avatar': 'https://avatars2.githubusercontent.com/u/6002026?v=3&s=400'},
        {'id': 5, 'name': '付业成', 'avatar': 'https://avatars0.githubusercontent.com/u/91730?v=3&s=400'},
        {'id': 6, 'name': '杜晓东', 'avatar': 'https://avatars0.githubusercontent.com/u/6927481?v=3&s=400'},
        {'id': 7, 'name': '杜晓峰', 'avatar': 'https://avatars0.githubusercontent.com/u/1694541?v=3&s=400'},
        {'id': 8, 'name': '郑李新', 'avatar': 'https://avatars2.githubusercontent.com/u/1264747?v=3&s=400'},
        {'id': 9, 'name': '袁晓沛', 'avatar': 'https://avatars2.githubusercontent.com/u/739343?v=3&s=400'}
    ]
    channel_id = parse_params(request.args, Rule('id', must = True))['id']
    cnt = parse_int('cnt', 100, lambda c: c <= 100)
    save = request.args.get('save')
    for i in range(0, cnt):
        user = choice(mock_users)
        message = ''.join(sample(ascii_letters + digits, randint(1, 25)))
        send_rongcloud_message.delay(user['id'], user['name'], user['avatar'], channel_id, message)

        if save:
            c = get_channel(channel_id)
            m = Message(
                    author_id = user['id'],
                    channel = c,
                    content = message,
                    offset = (datetime.now() - c.started_at).seconds
            )
            db.session.add(m)
            db.session.commit()
    return success()


@channels_endpoint.route('/chatroom/<int:channel_id>', methods = ['GET'])
@login_required
def chatroom_info(channel_id):
    return success({
        'info': ApiClient().chatroom_query(channel_id)
    })


@channels_endpoint.route('/share/<int:channel_id>', methods = ['GET'])
def channel_share(channel_id):
    channel = Channel.query.get_or_404(channel_id)
    if not (channel.is_publishing or channel.is_published):
        abort(404)
    return render_template('share.html', channel = channel)


logger = get_task_logger(__name__)


@celery.task(bind = True)
def create_rongcloud_chatroom(self, chatroom_id, chatroom_name):
    """向融云服务器发起创建聊天室的请求
    应通过create_rongcloud_chatroom.delay调用
    :param self: celery task
    :param chatroom_id: 创建的聊天室id
    :param chatroom_name: 创建的聊天室名字
    """
    try:
        ApiClient().chatroom_create({
            chatroom_id: chatroom_name
        })
        return {
            'action': 'create chatroom',
            'chatroom_id': chatroom_id,
            'chatroom_name': chatroom_name
        }
    except ClientError as exc:
        logging.warning('Create chatroom[%d] error: [%s].', chatroom_id, exc)
        # 每隔20s重试一次, 直至成功
        raise self.retry(exc = exc, countdown = 20, max_retries = None)


@celery.task(bind = True)
def destroy_rongcloud_chatroom(self, chatroom_id):
    """向融云服务器发起销毁聊天室的请求
    应通过destroy_rongcloud_chatroom.delay调用
    :param self: celery task
    :param chatroom_id: 销毁的聊天室id
    """
    try:
        ApiClient().chatroom_destroy(chatroom_id)
        return {
            'action': 'destroy chatroom',
            'chatroom_id': chatroom_id
        }
    except ClientError as exc:
        logging.warning('Destroy chatroom[%d] error: [%s]', chatroom_id, exc)
        # 每隔30s重试一次, 至多重试5次
        raise self.retry(exc = exc, countdown = 30, max_retries = 5)


@celery.task(bind = True)
def send_rongcloud_message(self, user_id, name, avatar, chatroom_id, message, retry = None):
    """向融云服务器发送聊天室消息.
    应通过send_rongcloud_message.delay调用
    :param self: celery task
    :param user_id: 发送消息的用户id
    :param name: 发送消息的用户名称
    :param avatar: 发送消息的用户头像
    :param chatroom_id: 发往的聊天室id
    :param message: 发送的消息
    :param retry: 失败后重试的次数,默认不重试
    """
    try:
        ApiClient().message_chatroom_publish(
                from_user_id = user_id,
                to_chatroom_id = chatroom_id,
                object_name = 'RC:TxtMsg',
                content = json.dumps({
                    'content': message,
                    'extra': {'name': name, 'avatar': avatar}
                })
        )
        return {
            'action': 'send message',
            'user_id': user_id,
            'chatroom_id': chatroom_id,
            'message': message
        }
    except ClientError as exc:
        logging.warning('User[%d] send message[%s] to chatroom[%d] error: [%s].', user_id, message, chatroom_id, exc)
        if retry:
            # 每隔5s重试一次, 至多重试3次
            raise self.retry(exc = exc, countdown = 5, max_retries = retry)


@celery.task
def send_async_email(msg):
    mail.send(msg)
    return {
        'action': 'send emails'
    }


def send_email(subject, to, template, **kwargs):
    config = current_app.config
    msg = EMessage(
            subject = config['TECHSHOW_MAIL_SUBJECT_PREFIX'] + ' ' + subject,
            recipients = [to],
            sender = config['TECHSHOW_MAIL_SENDER']
    )
    msg.html = render_template(template, **kwargs)
    send_async_email.delay(msg)


def get_channel(channel_id, access_control = False, must_owner = False):
    channel = Channel.query.get(channel_id)

    if channel is None:
        raise ChannelNotFound()
    if access_control and not (channel.is_publishing or channel.is_published):
        raise ChannelInaccessible()
    if must_owner and channel.owner != current_user:
        raise Unauthorized()

    return channel
