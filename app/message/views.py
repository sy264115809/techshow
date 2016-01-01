# encoding=utf-8
from datetime import datetime, timedelta

from flask import Blueprint, request, current_app
from flask_login import current_user, login_required

from app import db
from app.channel.models import Channel
from app.http_utils.response import success, bad_request, channel_not_found, send_message_too_frequently
from app.message.models import Message
from app.models.settings import Setting, SETTING_SEND_MESSAGE_FREQUENCY
from app.rong_cloud import ApiClient, ClientError

messages_endpoint = Blueprint('message', __name__, url_prefix = 'messages')


@messages_endpoint.route('', methods = ['POST'])
@login_required
def send_message():
    created_at = datetime.now()
    frequency = Setting.get_setting(SETTING_SEND_MESSAGE_FREQUENCY,
                                    current_app.config.get(SETTING_SEND_MESSAGE_FREQUENCY))
    # 检查用户发言间隔是否超过阈值
    if (created_at - current_user.last_send_message_at).seconds < frequency:
        return send_message_too_frequently()

    channel_id = request.json.get('channel_id')
    if channel_id is None:
        return bad_request('missing arguments "channel_id"')

    content = request.json.get('content')
    if content is None:
        return bad_request('missing arguments "content"')

    channel = Channel.query.get(channel_id)
    if channel is None:
        return channel_not_found()

    # 对弹幕的创建时间进行一些处理,使用户因发送造成的损耗被中和
    if (created_at - channel.started_at).seconds >= 5:
        created_at -= timedelta(seconds = 5)
    else:
        created_at = channel.started_at + timedelta(seconds = 2)
    relative_time = (channel.started_at - created_at).seconds

    if channel.is_publishing:
        # 如果正在推流,调用融云发送聊天室消息
        try:
            ApiClient().message_chatroom_publish(
                    from_user_id = current_user.id,
                    to_chatroom_id = channel.id,
                    object_name = 'RC:TxtMsg',
                    content = content
            )
        except ClientError, e:
            current_app.logger.info('user %d send message "%s" with error: %s', current_user.id, content, str(e))

    elif not channel.is_published:
        return bad_request('channel is not live or published')

    # 如果推流已结束,存入数据库及缓存
    # TODO redis
    message = Message(author = current_user, channel = channel, content = content, created_at = created_at,
                      relative_time = relative_time)
    db.session.add(message)
    db.session.commit()

    return success()
