# encoding=utf-8
from flask import request


class Rule(object):
    def __init__(self, column, param, allow = None, must = True):
        self.column = column
        self.param = param
        self.allow = allow
        self.must = must


def rule(column, param = None, allow = None, must = True):
    param = column if param is None else param
    return Rule(column, param, allow, must)


def paginate():
    limit = request.args.get('l')
    if limit is None or not limit > 0:
        limit = 10

    page = request.args.get('p')
    if page is None or not page >= 1:
        page = 1

    return page, limit, False


def query_params(*rules):
    return _parse_params(rules, request.args)


def json_params(*rules):
    return _parse_params(rules, request.json)


def must_query_params(*rules):
    return _must_parse_params(rules, request.args)


def must_json_params(*rules):
    return _must_parse_params(rules, request.json)


def _parse_params(rules, params):
    allow_params = dict()
    allow_values = dict()
    for r in rules:
        allow_params[r.param] = r.column
        allow_values[r.param] = r.allow

    q = dict()
    for k, v in params.items():
        if k in allow_params:
            if allow_values[k] is not None and v not in allow_values[k]:
                return None, 'invalid argument "%s"' % k
            else:
                q[allow_params[k]] = v
        else:
            return None, 'invalid argument "%s"' % k

    return q, None


def _must_parse_params(rules, params):
    if params is None:
        return None, 'no arguments received'

    q = dict()
    for r in rules:
        value = params.get(r.param)
        if r.must and value is None:
            return None, 'missing argument "%s"' % r.param
        else:
            if r.allow and value not in r.allow:
                return None, 'invalid argument "%s"' % r.param
            else:
                q[r.param] = value

    return q, None
