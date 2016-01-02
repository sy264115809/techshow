# 市场部直播APP应用接口说明

版本号：`v1.0.1`

## 接口规范

### 协议
`HTTP/1.1`

### 请求方法

#### `GET`
一般在请求服务器资源时使用。

包含参数时,参数一律以 **Query String** 的形式传递，示例可参考**[请求手机验证码](#get_auth_code)** API。

#### `POST`
一般在操作服务器资源时使用。

包含参数时，请求头需添加`Content-Type: application/json`，参数一律以 **JSON** 格式在请求体中传递，示例可参考**[根据手机验证码登录](#login_by_mobile)**API。

<a name="authentication"></a>
### 鉴权
> `TODO` 添加加密`Token`机制

用户登录后的所有操作都需要经过鉴权，鉴权方式使用 **[HTTP Basic Auth](https://zh.wikipedia.org/wiki/HTTP%E5%9F%BA%E6%9C%AC%E8%AE%A4%E8%AF%81)**。

用户在登录成功后，服务器会返回唯一的`api_token`。之后客户端的每一次请求都需要在请求头中携带经过 [Base64](https://zh.wikipedia.org/wiki/Base64) 编码的`api_token`，形式为：`Authorization: base64encode(api_token)`。

<a name='token-life-circle'></a>
### 令牌生命周期
令牌生命周期是指一个用户自登录之后所获得的令牌的有效时长。

> `V1.0.0`版本中设计为：一个令牌自颁发以后，除非用户**主动注销**或者**重新登录**，否则**一直有效**。

### 响应
服务器一旦接受了客户端的请求，一定会返回状态为`200 OK`的 HTTP 响应，**但请求执行结果需要根据响应内容来进行判断**。

响应内容的格式一律为 **JSON**，并一定包含两个基本的**状态码**`code`和`desc`。`code`是服务器制定的状态编码，用于指示本次返回请求所对应的结果；`desc`是对`code`的描述，用于帮助客户端的开发人员直观的理解`code`的含义而无需查表。

例如，当因为没有携带授权信息而导致请求失败时，会返回：

```
{
	"code": 4010,
	"desc": "unauthorized"
}
```

当成功时，则返回的数据中一定包含以下两项内容，以及根据不同的API规范而返回的不同数据结构：

```
{
	"code": 2000,
	"desc": "ok"
}
```
全部的状态码请参考[状态码列表](#code-list)。
全部的API接口请参考[API列表](#api-list)

<a name='code-list'></a>
## 状态码
|状态码|返回值`code`|默认描述`desc`|说明|
|:----|:----:|:-----|:--|
|`API_OK`|2000|ok|成功|
|`API_BAD_REQUEST`|4000|bad request|请求的参数缺失或格式不符|
|`API_UNAUTHORIZED`|4010|unauthorized|未授权，一般是因为`api_token`不正确|
|`API_INVALID_AUTH_CODE`|4011|invalid auth code|错误的登录验证码|
|`API_OAUTH_FAIL`|4012|oauth fail|OAuth登录失败|
|`API_MAX_CHANNEL_TOUCHED`|4031|touch maximum number of channels|达到最大频道数量|
|`API_USER_NOT_FOUND`|4041|user not found|用户未找到|
|`API_CHANNEL_NOT_FOUND`|4042|channel not found|频道未找到|

<a name='api-list'></a>
## API

### 目录

- [登陆](#api-login)
	- [获取手机验证码](#get_auth_code)
	- [根据手机号码登录](#login_by_mobile)
	- [Github OAuth方式登陆](#github-oauth)
	- [Qiniu OAuth方式登陆](#qiniu-oauth)
	- [登录](#login)
	- [登出](#logout)
- [用户相关](#api-user)
	- [类型声明: user](#user-definition)
	- [获取用户信息](#get-user-info)
	- [获取我的用户信息](#get-my-info)
- [频道相关](#api-channel)
	- [类型声明: channel](#channel-definition)
	- [类型声明: stream](#stream-definition)
	- [创建频道](#create-channel)
	- [获取直播频道信息](#get-live-channels)
	- [获取回放频道信息](#get-playback-channels)
	- [获取我的频道列表](#get-my-channels)
	- [开始推流](#channel-publish)
	- [结束推流](#channel-finish)

---

<a name="api-login"></a>
### 登录
> - `v1.0.1`仅支持使用[Github OAuth](#github-oauth)或[Qiniu OAuth](#qiniu-oauth)的方式登陆。

<a name='get_auth_code'></a>
#### 获取手机验证码
> `v1.0.1`该接口不使用

一个用户一次请求所获得的一个验证码，在**十分钟内有效**。

**请求**

```
GET /users/login/mobile/code?mobile=<mobile>
```
- `mobile` 用户的手机号

**成功**

```
{
	"code": 2000,
	"desc": "ok"
}
```
此时服务器端以成功向用户手机发送验证码。

**失败**

```
API_BAD_REQUEST
```
根据不同场景可能表达以下含义，详见`desc`字段的描述：

- 缺少参数`mobile`
- `mobile`格式不正确，无法获取手机验证码

<a name='login_by_mobile'></a>
#### 根据手机号码登录
> `v1.0.1`该接口不使用

**请求**

```
POST /users/login/mobile
Content-Type: application/json

{
	"mobile": <string mobile>,
	"auth_code": <string auth_code>
}
```

- `mobile`： `string`类型，用户的手机号
- `auth_code`： `string`类型，用户的验证码

**成功**

```
{
  "code": 2000, 
  "desc": "ok", 
  "api_token": <string api_token>, 
  "mobile": <string mobile>,
  "id": <int id>,
  "rong_cloud_token": <string rong_cloud_token>
}
```
表示用户通过验证，此时请求中的`auth_code`过期作废。

- `api_token`： `string`类型，用户本次[生命周期](#token-life-circle)中用于[鉴权](#authentication)的秘钥
- `mobile`：`string`类型，用户登录使用的手机号码
- `id`： `int`类型，用户的id
- `rong_cloud_token`： `int`类型，融云的token

**失败**

```
API_INVALID_AUTH_CODE
```
错误的验证码。

<a name="github-oauth"></a>
#### Github OAuth方式登录

客户端应使用`WebView`请求本 API，请求后会跳转到 **Github** 的 **OAuth** 登录页面供用户登录，用户操作后会产生响应结果。

**请求**

```
GET /users/login/github
```

**成功**

```
{
  "code": 2000, 
  "desc": "ok", 
  "auth_code": <string auth_code>
}
```

- `auth_code`： `string`类型，凭此[登录](#login)

**失败**

```
API_BAD_REQUEST
API_OAUTH_FAIL
```

<a name="qiniu-oauth"></a>
#### Qiniu OAuth方式登录

客户端应使用`WebView`请求本 API，请求后会跳转到 **Qiniu Portal** 的 **OAuth** 登录页面供用户登录，用户操作后会产生响应结果。

**请求**

```
GET /users/login/qiniu
```

**成功**

```
{
  "code": 2000, 
  "desc": "ok", 
  "auth_code": <string auth_code>
}
```

- `auth_code`： `string`类型，凭此[登录](#login)

**失败**

```
API_BAD_REQUEST
API_OAUTH_FAIL
```

<a name="login"></a>
#### 登录
**请求**

```
POST /users/login
Content-Type: application/json

{
	"auth_code": <string auth_code>
}
```

- `auth_code`： `string`类型，OAuth成功后返回的`auth_code`，一经登录即作废。

**成功**

```
{
  "code": 2000, 
  "desc": "ok", 
  "api_token": <string api_token>, 
  "id": <int id>,
  "rong_cloud_token": <string rong_cloud_token>
}
```

- `api_token`： `string`类型，用户本次[生命周期](#token-life-circle)中用于[鉴权](#authentication)的秘钥
- `id`： `int`类型，用户的id
- `rong_cloud_token`： `int`类型，融云的token

**失败**

```
API_BAD_REQUEST
API_INVALID_AUTH_CODE
```

<a name="logout"></a>
#### 登出
**请求**

```
POST /users/logout
Authorization: Basic Auth
```

**成功**

```
{
	"code": 2000,
	"desc": "ok"
}
```
登出成功。

**失败**

```
API_UNAUTHORIZED
```
未带授权，登出失败。

----

<a name="api-user"></a>
### 用户相关

<a name="user-definition"></a>
#### 类型声明：`user`
在返回结果中，`user`的格式如下：

```
{
	 "id": <int id>,
	 "name": <string name>,
	 "nickname": <strng nickname>,
	 "bio": <string bio>,
	 "gender": <int gender>,
	 "email": <string email>,
	 "mobile": <string mobile>,
	 "avatar": <string avatar>,
    "qiniu_name": <string qiniu_name>,
    "qiniu_email": <string qiniu_email>,
    "github_login": <string github_login>,
    "github_name": <string github_name>,
    "github_email": <string github_email>,
    "is_banned": <int is_banned>,
    "stream_status" <int stream_status>:
}
```
- `id`： `int`类型，用户id
- `name`： `string`类型，用户名称
- `nickname`： `string`类型，用户昵称
- `bio`： `string`类型，用户个人签名
- `gender`： `int`类型，用户的性别
	- `null`：unknown
	- `0`：male
	- `1`：female
- `email`： `string`类型，用户的电子邮箱（优先级：七牛帐号对应邮箱 > Github帐号对应邮箱）
- `mobile`： `string`类型，用户的手机号
- `avatar`： `string`类型，用户的头像对应的url
- `qiniu_name`： `string`类型，用户通过Qiniu OAuth登陆后获得的名称
- `qiniu_email`： `string`类型，用户通过Qiniu OAuth登陆后获得的邮箱
- `github_login`： `string`类型，用户通过Github OAuth登陆后获得的登陆名
- `github_name`： `string`类型，用户通过Github OAuth登陆后获得的名称
- `github_email`： `string`类型，用户通过Github OAuth登陆后获得的邮箱
- `is_banned`： `bool`类型，用户是否被禁用
	- `true`：禁用状态
	- `false`：可用状态
- `stream_status`： `int`类型，用户所持有的流状态
	- `0`：用户没有创建过流（创建频道后生成）
	- `1`：用户的流处于不可用状态（被占据、被禁用等，不应创建频道）
	- `2`：用户的流可用（可以新建频道）

<a name="get-user-info"></a>
#### 获取用户信息
**请求**

```
GET /users
Authorization: Basic Auth
```
 
**参数**

- `id`： `int`类型，用户id。可选
- `nickname`： `int`类型，用户昵称。可选
- `p`： `int`类型，分页中的页数page，默认为`1`
- `l`： `int`类型，分页中的限制limit，默认为`10`

**成功**

```
{
	"code": 2000,
	"desc": "ok",
	"users": [
		<user user1>,
		<user user2>,
		...
	]
}
```

- `users`：`user`类型（[定义](#user-definition)）的列表，符合查询条件的用户列表

**失败**

```
API_UNAUTHORIZED
API_USER_NOT_FOUND
```

<a name="get-my-info"></a>
#### 获取我的用户信息

```
GET /users/my
Authorization: Basic Auth
```

**成功**

```
{
	"code": 2000,
	"desc": "ok",
	"user": <user>
}
```

- `user`：`user`类型（[定义](#user-definition)），我的用户信息

**失败**

```
API_UNAUTHORIZED
```

----

<a name="api-channel"></a>
### 频道相关

<a name="channel-definition"></a>
#### 类型声明：`channel`
在返回结果中，`channel`的格式如下：

```
{
	"id": <int id>,
	"title": <string title>,
	"thumbnail": <string thumbnail>,
	"desc": <string desc>,
  	"duration": <int duration>,
  	"orientation": <int orientation>,
  	"quality": <int quality>,
  	"status": <int status>,
  	"owner": <user>,  
	"started_at": <timestamp statred_at>,
  	"stopped_at": <timestamp stopped_at>,
  	"created_at": <timestamp created_at>
}
```

- `id`： `int`类型，频道id
- `title`： `string`类型，频道标题
- `thumbnail`： `string`类型，频道缩略图对应url
- `desc`： `string`类型，频道描述
- `duration`： `int`类型，频道的持续时间，单位秒。未结束时为None
- `orientation`： `int`类型，屏幕方向，由前端给出
- `quality`： `ini`类型，画质，由前端给出
- `status`： `int`类型，[频道状态](#channel-status)<a name="channel-status-definition"></a>
	- `0`：新建，尚未推流
	- `1`：推流中
	- `2`：已结束推流
	- `3`：关闭（由频道拥有者操作）
	- `4`：禁止（由管理员操作）
- `owner`：`user`类型（[定义](#user-definition)），频道的拥有者
- `started_at`： `timestamp`类型，开始推流的时间
- `stopped_at`： `timestamp`类型，结束推流的时间
- `created_at`： `timestamp`类型，频道创建的时间

<a name="channel-status"></a>
**频道状态**
在目前的设计（v1.0.1）中，频道有五种可能的状态：

- `initiate`： 新建状态，这时用户还没有提起推流请求。一个用户只可能拥有至多一个处于`initiate`状态的频道，一旦一个频道被新建了但是没有进行推流，它将会在下一个新建频道的请求到来后被删除。

- `publishing`： 正在推流状态。只有一个处于`initiate`状态的频道可以被提出推流申请，对任何非`initiate`状态的频道提出推流申请都将被服务器拒绝。一个用户只可能拥有至多一个处于`publishing`状态的频道，此后任何新的对该用户的`initiate`状态频道的推流申请都将强制打断当前处于`publishing`状态的这个频道。

- `published`： 结束推流状态。只有一个处于`publishing`状态的频道可以被提出结束推流申请。一个用户可以拥有多个处于`published`状态的频道。

- `closed`：关闭状态。用户可以关闭自己（一般是处于`published`状态）的频道，被关闭的频道将不会被任何其他用户查看。

- `banned`：禁止状态。管理员可以禁止用户的频道，被禁止的频道将会被强制中断直播（如果处于`publishing`状态），并且不能被回放。

<a name="stream-definition"></a>
#### 类型声明：`stream`
`stream`是由 *pili* 服务器返回的模型。在返回结果中，`stream`的格式形如：

```
{
	"createdAt": "2015-12-23T16:23:33.086+08:00",
    "disabled": false,
    "disabledTill": 0,
    "hosts": {
    	"live": {
       	"hdl": "pili-live-hdl.live.golanghome.com",
       	"hls": "pili-live-hls.live.golanghome.com",
       	"http": "pili-live-hls.live.golanghome.com",
       	"rtmp": "pili-live-rtmp.live.golanghome.com"
    	},
    	"play": {
    		"http": "pili-live-hls.live.golanghome.com",
     		"rtmp": "pili-live-rtmp.live.golanghome.com"
    	},
    	"playback": {
    		"hls": "pili-playback.live.golanghome.com",
    		"http": "pili-playback.live.golanghome.com"
    	},
    	"publish": {
    		"rtmp": "pili-publish.live.golanghome.com"
    	}
    },
    "hub": "jinxinxin",
    "id": "z1.jinxinxin.567a5a05d409d266f3000003",
    "publishKey": "7a2f7f10cab7a706",
    "publishSecurity": "static",
    "title": "567a5a05d409d266f3000003",
    "updatedAt": "2015-12-23T16:23:33.086+08:00"
}
```

<a name="create-channel"></a>
#### 创建频道
**请求**

```
POST /channels
Authorization: Basic Auth
Content-Type: application/json

{
	"title": <string title>,
	"quality": <int quality>,
	"orientation": <int orientation>
}
```

- `title`： `string`类型，频道的标题
- `quality`： `int`类型，直播的清晰度
- `orientation`： `int`类型，直播的屏幕方向

**成功**

```
{
	"code": 2000,
	"desc": "ok",
	"channel": <channel>,
	"stream": <stream>
}
```

- `channel`： `channel`类型，本次创建的频道信息，定义见[这里](#channel-definition)
- `stream`： `stream`类型，本次创建的频道对应的流信息，定义见[这里](#stream-definition)

**失败**

```
API_UNAUTHORIZED
API_BAD_REQUEST
API_MAX_CHANNEL_TOUCHED
```

- `API_BAD_REQUEST`： 请检查`title`, `quality`, `orientation`是否在请求体中并格式正确。
- `API_MAX_CHANNEL_TOUCHED`： 频道数达到管理员设置的最大频道数

<a name="get-live-channels"></a>
#### 获取直播频道信息
**请求**

```
GET /channels/live
Authorization: Basic Auth
```

**参数**

- `id`： `int`类型，频道id。可选
- `owner`： `int`类型，频道属主id。可选
- `p`： `int`类型，分页中的页数page，默认为`1`
- `l`： `int`类型，分页中的限制limit，默认为`10`

**成功**

```
{
	"code": 2000,
	"desc": "ok",
	"channels":[
		{
	 		"channel": <channel>,
			"stream": <stream>,
			"playback": {
				"hls": "xxxxx/hub/stream-id.m3u8?start=t&end=t"
			},
			"playback": {
				"flv": "http://xxxxx/hub/stream-id.flv",
  				"hls": "http:/xxxxx/hub/stream-id.m3u8",
			  	"rtmp": "rtmp://xxxxx/hub/stream-id"
			}
		}
	]
}
```

- `channel`： `channel`类型，本次创建的频道信息，定义见[这里](#channel-definition)
- `stream`： `stream`类型，本次创建的频道对应的流信息，定义见[这里](#stream-definition)
- `playback`： 回放地址
- `live`： 直播地址，推流结束时为`null`

**失败**

```
API_UNAUTHORIZED
API_CHANNEL_NOT_FOUND
```

<a name="get-playback-channels"></a>
#### 获取直播频道信息
**请求**

```
GET /channels/playback
Authorization: Basic Auth
```

**参数**

- `id`： `int`类型，频道id。可选
- `owner`： `int`类型，频道属主id。可选
- `p`： `int`类型，分页中的页数page，默认为`1`
- `l`： `int`类型，分页中的限制limit，默认为`10`

**成功**

```
{
	"code": 2000,
	"desc": "ok",
	"channels":[
		{
	 		"channel": <channel>,
			"stream": <stream>,
			"playback": {
				"hls": "xxxxx/hub/stream-id.m3u8?start=t&end=t"
			},
			"playback": {
				"flv": "http://xxxxx/hub/stream-id.flv",
  				"hls": "http:/xxxxx/hub/stream-id.m3u8",
			  	"rtmp": "rtmp://xxxxx/hub/stream-id"
			}
		}
	]
}
```

- `channel`： `channel`类型，本次创建的频道信息，定义见[这里](#channel-definition)
- `stream`： `stream`类型，本次创建的频道对应的流信息，定义见[这里](#stream-definition)
- `playback`： 回放地址
- `live`： 直播地址，推流结束时为`null`

**失败**

```
API_UNAUTHORIZED
API_CHANNEL_NOT_FOUND
```

<a name="get-my-channels"></a>
#### 获取我的频道列表
**请求**

```
GET /channels
Authorization: Basic Auth
```

**参数**

- `status`： `int`类型，频道状态。可选，可为任意[频道状态](#channel-status)
- `p`： `int`类型，分页中的页数page，默认为`1`
- `l`： `int`类型，分页中的限制limit，默认为`10`

**成功**

```
{
	"code": 2000,
	"desc": "ok",
	"channels":[
		{
	 		"channel": <channel>,
			"stream": <stream>,
			"playback": {
				"hls": "xxxxx/hub/stream-id.m3u8?start=t&end=t"
			},
			"playback": {
				"flv": "http://xxxxx/hub/stream-id.flv",
  				"hls": "http:/xxxxx/hub/stream-id.m3u8",
			  	"rtmp": "rtmp://xxxxx/hub/stream-id"
			}
		}
	]
}
```

- `channel`： `channel`类型，本次创建的频道信息，定义见[这里](#channel-definition)
- `stream`： `stream`类型，本次创建的频道对应的流信息，定义见[这里](#stream-definition)
- `playback`： 回放地址
- `live`： 直播地址，推流结束时为`null`

**失败**

```
API_UNAUTHORIZED
API_CHANNEL_NOT_FOUND
```


<a name="channel-publish"></a>
#### 开始推流

**请求**

```
POST /channels/publish
Authorization: Basic Auth
Content-Type: application/json

{
	"id": <int id>
}
```

- `id`： `int`类型，频道id。必须

**成功**

```
{
	"code": 2000,
	"desc": "ok",
}
```

**失败**

```
API_UNAUTHORIZED
API_CHANNEL_NOT_FOUND
API_BAD_REQUEST
```

- `API_UNAUTHORIZED`： 如果请求的用户和申请推流频道的所有者不是同一人，也会返回未授权。
- `API_BAD_REQUEST`： 频道未处于`initiate`[状态](#channel-status)

<a name="channel-finish"></a>
#### 结束推流

**请求**

```
POST /channels/<int channel_id>/finish
Authorization: Basic Auth
Content-Type: application/json

{
	"id": <int id>
}
```

- `id`： `int`类型，频道id。必须

**成功**

```
{
	"code": 2000,
	"desc": "ok",
}
```

**失败**

```
API_UNAUTHORIZED
API_CHANNEL_NOT_FOUND
API_BAD_REQUEST
```

- `API_UNAUTHORIZED`： 如果请求的用户和申请结束推流频道的所有者不是同一人，也会返回未授权。
- `API_BAD_REQUEST`： 频道未处于`publishing`[状态](#channel-status)