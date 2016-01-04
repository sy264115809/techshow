# encoding=utf-8
from datetime import datetime

from flask import Blueprint, request, current_app, json
from flask_login import current_user, login_required

from app import db
from app.channel.models import Channel
from app.http_utils.response import success, bad_request, channel_not_found, send_message_too_frequently, \
    channel_access_denied
from app.http_utils.request import rule, must_json_params
from app.message.models import Message
from app.models.settings import Setting, SETTING_SEND_MESSAGE_FREQUENCY
from app.rong_cloud import ApiClient, ClientError

messages_endpoint = Blueprint('message', __name__, url_prefix = '/messages')


@messages_endpoint.route('', methods = ['POST'])
@login_required
def send_message():
    created_at = datetime.now()
    frequency = Setting.get_setting(SETTING_SEND_MESSAGE_FREQUENCY,
                                    current_app.config.get(SETTING_SEND_MESSAGE_FREQUENCY))
    # 检查用户发言间隔是否超过阈值
    if (created_at - current_user.last_send_message_at).seconds < frequency:
        return send_message_too_frequently()

    current_user.last_send_message_at = created_at

    rules = [
        rule('channel_id'),
        rule('content')
    ]
    q, bad = must_json_params(*rules)
    if bad:
        return bad_request(bad)

    channel = Channel.query.get(q['channel_id'])
    if channel is None:
        return channel_not_found()

    if not channel.is_publishing and not channel.is_published:
        return channel_access_denied()

    if channel.is_published:
        relative_time = request.json.get('relative_time')
        if relative_time is None:
            return bad_request('missing argument "relative_time"')
        if not isinstance(relative_time, int):
            return bad_request('"relative_time" should be int type')
    else:
        relative_time = (created_at - channel.started_at).seconds

    # 如果推流已结束,存入数据库及缓存
    # TODO redis
    message = Message(author = current_user, channel = channel, content = q['content'], created_at = created_at,
                      relative_time = relative_time)
    db.session.add(message)
    db.session.commit()

    if channel.is_publishing:
        # 如果正在推流,调用融云发送聊天室消息
        try:
            ApiClient().message_chatroom_publish(
                    from_user_id = current_user.id,
                    to_chatroom_id = channel.id,
                    object_name = 'RC:TxtMsg',
                    content = json.dumps({'content': q['content']})
            )
        except ClientError, e:
            current_app.logger.info('user %d send message "%s" with error: %s', current_user.id, q['content'], str(e))

    return success()
