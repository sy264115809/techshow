# coding=utf-8
from flask import jsonify


class APIException(Exception):
    """API Base Exception
    """

    def __init__(self, code, desc, extra = None):
        self.code = code
        self.desc = desc
        self.extra = extra

    def to_json(self):
        ret = {
            'code': self.code,
            'desc': self.desc,
        }
        if self.extra is not None:
            ret['extra'] = self.extra
        return ret


class BadRequest(APIException):
    """4000 Bad Request
    """

    def __init__(self, desc = 'bad request'):
        super(BadRequest, self).__init__(code = 4000, desc = desc)


class Unauthorized(APIException):
    """4010 Unauthorized
    """

    def __init__(self):
        super(Unauthorized, self).__init__(code = 4010, desc = 'unauthorized')


class InvalidAuthCode(APIException):
    """4011 Invalid Auth Code
    """

    def __init__(self):
        super(InvalidAuthCode, self).__init__(code = 4011, desc = 'invalid auth code')


class OAuthFail(APIException):
    """4012 OAuth Fail
    """

    def __init__(self):
        super(OAuthFail, self).__init__(code = 4012, desc = 'oauth fail')


class MaxChannelTouched(APIException):
    """4031 Max Channel's Amount Touched
    """

    def __init__(self):
        super(MaxChannelTouched, self).__init__(code = 4031, desc = 'touch maximum number of channels')


class MessageTooFrequently(APIException):
    """4032 Send Message Too Frequently
    """

    def __init__(self):
        super(MessageTooFrequently, self).__init__(code = 4032, desc = 'send message too frequently')


class ChannelInaccessible(APIException):
    """4033 Channel Is Inaccessible
    """

    def __init__(self):
        super(ChannelInaccessible, self).__init__(code = 4033, desc = 'channel is inaccessible')


class UserNotFound(APIException):
    """4041 User Not Found
    """

    def __init__(self):
        super(UserNotFound, self).__init__(code = 4041, desc = 'user not found')


class ChannelNotFound(APIException):
    """4042 Channel Not Found
    """

    def __init__(self):
        super(ChannelNotFound, self).__init__(code = 4042, desc = 'channel not found')


class ServerError(APIException):
    """5000 Server Error
    """

    def __init__(self):
        super(ServerError, self).__init__(code = 5000, desc = 'server error')


class RongCloudError(APIException):
    """5001 Rong Cloud Error
    """

    def __init__(self):
        super(RongCloudError, self).__init__(code = 5001, desc = 'rong cloud bad response')


def success(data = None):
    if data is None:
        data = {}
    data.update({
        'code': 2000,
        'desc': 'ok'
    })
    return jsonify(data)


def exception(e):
    return jsonify(e.to_json())


def unauthorized():
    return exception(Unauthorized())
