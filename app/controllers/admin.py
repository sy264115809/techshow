# coding=utf-8
from datetime import datetime

from flask import Blueprint, request, current_app, abort, render_template, url_for, redirect
from flask_login import current_user, login_required, logout_user

from app import db
from app.models.channel import Channel, ChannelStatus
from app.http.request import paginate, Rule, parse_params
from app.http.response import success
from app.http.pili_service import get_stream, create_dynamic_stream

admin_endpoint = Blueprint('admin', __name__, url_prefix = '/admin')


@admin_endpoint.before_request
def check_admin_authorization():
    if request.url != url_for('admin.admin_login', _external = True):
        if current_user.is_anonymous:
            return redirect(url_for('admin.admin_login'))

        if current_user.github_email in current_app.config['ADMIN_GITHUB']:
            pass
        elif current_user.qiniu_email in current_app.config['ADMIN_QINIU']:
            pass
        else:
            return redirect(url_for('admin.admin_login'))


@admin_endpoint.route('/login', methods = ['GET'])
def admin_login():
    return render_template('admin/login.html')


@admin_endpoint.route('/index', methods = ['GET'])
@login_required
def admin_index():
    return redirect(url_for('admin.channel_index'))


@admin_endpoint.route('/logout', methods = ['GET'])
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin.admin_login'))


@admin_endpoint.route('/channels/index', methods = ['GET'])
@login_required
def channel_index():
    paginate_ = Channel.query.filter_by().paginate(*paginate())
    channels = paginate_.items
    return render_template('admin/channel_index.html', paginate = paginate_, channels = channels, kwargs = {})


@admin_endpoint.route('/channels/<int:channel_id>/block', methods = ['POST'])
@login_required
def block_channel(channel_id):
    channel = Channel.query.get(channel_id)
    if channel and (channel.is_publishing or channel.is_published):
        # 封禁频道对应的流
        stream = get_stream(channel.stream_id)
        stream.disable()

        # 设置频道状态为banned
        if channel.is_publishing:
            channel.stopped_at = datetime.now()
        channel.status = ChannelStatus.banned

        # 为频道的所有者重新创建一条新的流
        channel.owner.stream_id = create_dynamic_stream().id
        db.session.commit()
    else:
        abort(403)

    return success()


@admin_endpoint.route('/channels/<int:channel_id>/release', methods=['POST'])
@login_required
def release_channel(channel_id):
    channel = Channel.query.get(channel_id)
    if channel and channel.is_banned:
        channel.status = ChannelStatus.published

        db.session.commit()
    else:
        abort(403)

    return success()


@admin_endpoint.route('/users/index', methods = ['GET'])
@login_required
def user_index():
    pass
