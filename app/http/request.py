# coding=utf-8
from flask import request

from app.http.response import BadRequest


def paginate(default_limit = 10):
    """返回适合sqlalchemy.paginate的参数
    :param default_limit:默认的每页项数
    page - 页数, 从1开始, 默认1
    limit - 每页项数, 必须大于0, 默认10
    """
    limit = parse_int('l', default = default_limit, condition = lambda l: l > 0)
    page = parse_int('p', default = 1, condition = lambda p: p >= 1)
    return page, limit


def parse_int(param, default, condition):
    """将参数转换为int
    :param param: 要转换的参数的名称
    :type param: str
    :param default: 默认值
    :param condition: 满足条件时返回转换的参数,否则返回默认值
    :type condition: function
    """
    value = request.args.get(param)
    if value is None:
        return default

    try:
        i = int(value)
        return i if condition(i) else default
    except ValueError:
        raise BadRequest('invalid argument %s' % param)


class Rule(object):
    def __init__(self, param, allow = None, must = False):
        self.param = param
        self.allow = allow
        self.must = must


def parse_params(params, *rules):
    if params is None:
        params = {}

    q = {}
    for r in rules:
        value = params.get(r.param)
        if r.must and value is None:
            raise BadRequest('missing argument %s' % r.param)

        if value is not None:
            if r.allow and value not in r.allow:
                raise BadRequest('invalid argument %s' % r.param)
            else:
                q[r.param] = value

    return q
