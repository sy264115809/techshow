# encoding=utf-8
from flask import request


class Rule(object):
    def __init__(self, column, param, allow = None):
        self.column = column
        self.param = param
        self.allow = allow


def rule(column, param, allow = None):
    return Rule(column, param, allow)


def paginate():
    limit = request.args.get('l')
    if limit is None or not limit > 0:
        limit = 10

    page = request.args.get('p')
    if page is None or not page >= 1:
        page = 1

    return page, limit, False


def query_params(*rules):
    allow_params = dict()
    allow_values = dict()
    for r in rules:
        allow_params[r.param] = r.column
        allow_values[r.param] = r.allow

    q = dict()
    for k, v in request.args.items():
        if k in allow_params:
            if allow_values[k] is not None and v not in allow_values[k]:
                return None, 'invalid argument "%s"' % k
            else:
                q[allow_params[k]] = v
        else:
            return None, 'invalid argument "%s"' % k

    return q, None
