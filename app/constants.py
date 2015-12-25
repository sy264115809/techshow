# coding=utf8

# api return code
API_OK = 2000

API_BAD_REQUEST = 4000

API_UNAUTHORIZED = 4010
API_INVALID_AUTH_CODE = 4011
API_OAUTH_FAIL = 4012

API_MAX_CHANNEL_TOUCHED = 4031

API_USER_NOT_FOUND = 4041
API_CHANNEL_NOT_FOUND = 4042

API_CODES = {
    API_OK: 'ok',

    API_BAD_REQUEST: 'bad request',

    API_UNAUTHORIZED: 'unauthorized',
    API_INVALID_AUTH_CODE: 'invalid auth code',
    API_OAUTH_FAIL: 'oauth fail',

    API_MAX_CHANNEL_TOUCHED: 'touch maximum number of channels',

    API_USER_NOT_FOUND: 'user not found',
    API_CHANNEL_NOT_FOUND: 'channel not found'

}
