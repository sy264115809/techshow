# coding=utf-8
import qiniu
from flask import Blueprint, request, current_app, render_template, url_for, redirect, json, jsonify
from flask_login import current_user, login_required, logout_user
from sqlalchemy import or_

from app import db
from app.models.user import User
from app.models.channel import Channel, ChannelStatus, Thumbnail, Complaint
from app.controllers.channel import destroy_rongcloud_chatroom
from app.http.request import paginate, parse_params, Rule
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
    q = {}
    _filter = request.args.get('filter')
    if _filter == 'publishing':
        q['status'] = ChannelStatus.publishing

    p = Channel.query.filter_by(**q).order_by(Channel.started_at.desc()).paginate(
            *paginate())
    return render_template('admin/channel/index.html', channels = p, filter = _filter)


@admin_endpoint.route('/channels/<int:channel_id>', methods = ['GET'])
@login_required
def channel_detail(channel_id):
    channel = Channel.query.get_or_404(channel_id)
    complaints = Complaint.query.filter_by(channel = channel).order_by(Complaint.created_at.desc()).paginate(
            *paginate())
    return render_template('admin/channel/detail.html', channel = channel, complaints = complaints)


@admin_endpoint.route('/channels/<int:channel_id>/disable', methods = ['POST'])
@login_required
def channel_disable(channel_id):
    channel = Channel.query.get_or_404(channel_id)
    resp = {
        'disable_calculate_task': channel.disable(),
        'disable_destroy_chatroom_task': destroy_rongcloud_chatroom.apply_async(args = [channel.id]).id
    }
    return success(resp)


@admin_endpoint.route('/channels/<int:channel_id>/enable', methods = ['POST'])
@login_required
def channel_enable(channel_id):
    channel = Channel.query.get_or_404(channel_id)
    channel.enable()
    return success()


@admin_endpoint.route('/users/index', methods = ['GET'])
@login_required
def user_index():
    q = request.args.get('q')
    qs = User.query
    if q:
        qs = qs.filter(or_(User.github_email == q, User.qiniu_email == q, User.nickname == q))

    p = qs.paginate(*paginate())
    return render_template('admin/user/index.html', users = p)


@admin_endpoint.route('/users/<user_id>', methods = ['GET'])
@login_required
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    channels = Channel.query.filter_by(owner_id = user_id).order_by(Channel.started_at.desc()).paginate(*paginate())
    return render_template('admin/user/detail.html', user = user, channels = channels)


@admin_endpoint.route('/users/<user_id>/stream/enable', methods = ['POST'])
@login_required
def user_stream_enable(user_id):
    user = User.query.get_or_404(user_id)
    user.enable_stream()
    return success()


@admin_endpoint.route('/users/<user_id>/stream/disable', methods = ['POST'])
@login_required
def user_stream_disable(user_id):
    user = User.query.get_or_404(user_id)
    user.disable_stream()
    return success()


@admin_endpoint.route('/users/<user_id>/ban', methods = ['POST'])
@login_required
def user_ban(user_id):
    user = User.query.get_or_404(user_id)
    user.ban()
    return success()


@admin_endpoint.route('/users/<user_id>/unban', methods = ['POST'])
@login_required
def user_unban(user_id):
    user = User.query.get_or_404(user_id)
    user.unban()
    return success()


@admin_endpoint.route('/uptoken', methods = ['GET'])
@login_required
def uptoken():
    policy = {
        'returnBody': json.dumps({
            'key': '$(key)',
            'hash': '$(etag)',
            'name': '$(fname)',
            'bucket': '$(bucket)',
            'path': 'http://%s/$(key)' % current_app.config['QINIU_DOMAIN'],
            'success': True
        })
    }
    q = qiniu.Auth(current_app.config['QINIU_ACCESS_KEY'], current_app.config['QINIU_SECRET_KEY'])
    token = q.upload_token(current_app.config['QINIU_BUCKET'], policy = policy)
    return jsonify({
        "uptoken": token,
        "domain": current_app.config['QINIU_DOMAIN']
    })


@admin_endpoint.route('/thumbnails/index', methods = ['GET'])
@login_required
def thumbnail_index():
    p = Thumbnail.query.paginate(*paginate(24))
    return render_template('admin/channel/thumbnail/index.html', thumbnails = p)


@admin_endpoint.route('/thumbnails', methods = ['POST'])
@login_required
def thumbnail_create():
    args = parse_params(
            request.form,
            Rule('key', must = True),
            Rule('name', must = True)
    )
    t = Thumbnail.query.filter_by(key = args['key']).first()
    if t is None:
        t = Thumbnail(**args)
        db.session.add(t)
        db.session.commit()
        return render_template('admin/channel/thumbnail/partial.html', item = t)

    return jsonify({'error': '您已上传过该图片'})


@admin_endpoint.route('/thumbnails/<thumbnail_id>/delete', methods = ['POST'])
@login_required
def thumbnail_delete(thumbnail_id):
    t = Thumbnail.query.get(thumbnail_id)
    if t:
        db.session.delete(t)
        db.session.commit()
    return success()


@admin_endpoint.route('/complaints/<complaint_id>/handle', methods = ['POST'])
@login_required
def complaint_handle(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    complaint.handler = current_user
    db.session.commit()
    return success()
