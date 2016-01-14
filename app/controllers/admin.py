# coding=utf-8
import qiniu
from flask import Blueprint, request, current_app, render_template, url_for, redirect, json, jsonify
from flask_login import current_user, login_required, logout_user

from app import db
from app.models.channel import Channel, Thumbnail
from app.controllers.channel import destroy_rongcloud_chatroom, get_channel
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
    p = Channel.query.filter_by().order_by(Channel.started_at.desc()).paginate(*paginate())
    return render_template('admin/channel/index.html', channels = p)


@admin_endpoint.route('/channels/<int:channel_id>/disable', methods = ['POST'])
@login_required
def channel_disable(channel_id):
    channel = get_channel(channel_id)
    channel.banned(destroy_rongcloud_chatroom.s(channel.id))
    return success()


@admin_endpoint.route('/channels/<int:channel_id>/enable', methods = ['POST'])
@login_required
def channel_enable(channel_id):
    channel = get_channel(channel_id)
    channel.release()
    return success()


@admin_endpoint.route('/users/index', methods = ['GET'])
@login_required
def user_index():
    pass


@admin_endpoint.route('/uptoken', methods = ['GET'])
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
