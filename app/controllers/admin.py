# coding=utf-8
from flask import Blueprint, request, current_app, render_template, url_for, redirect
from flask_login import current_user, login_required, logout_user

from app import db
from app.models.channel import Channel
from app.controllers.channel import destroy_rongcloud_chatroom, get_channel
from app.http.request import paginate
from app.http.response import success

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
    # db.session.commit()
    p = Channel.query.filter_by().order_by(Channel.started_at.desc()).paginate(*paginate())
    return render_template('admin/channel_index.html', channels = p)


@admin_endpoint.route('/channels', methods = ['GET'])
def channels():
    p = Channel.query.filter_by().order_by(Channel.started_at.desc()).paginate(*paginate())
    return success({
        'channels': map(lambda c: [c.id, c.status], p.items)
    })


@admin_endpoint.route('/channels/<int:channel_id>/block', methods = ['POST'])
@login_required
def block_channel(channel_id):
    channel = get_channel(channel_id)
    channel.banned(destroy_rongcloud_chatroom.s(channel.id))
    return success()


@admin_endpoint.route('/channels/<int:channel_id>/release', methods = ['POST'])
@login_required
def release_channel(channel_id):
    channel = get_channel(channel_id)
    channel.release()
    return success()


@admin_endpoint.route('/users/index', methods = ['GET'])
@login_required
def user_index():
    pass
