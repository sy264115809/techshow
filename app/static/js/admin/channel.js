$(function () {
    var initChannelStatus = function () {
        var channelStatus = {
            '0': ['新建', 'label label-info'],
            '1': ['直播中', 'label label-success'],
            '2': ['直播结束', 'label label-warning'],
            '3': ['关闭', 'label'],
            '4': ['管理员封禁', 'label label-danger']
        };

        $('td[data-status]').each(function (i, e) {
            var status = $(e).data('status');
            var statusLabel = $('<span/>', {
                text: channelStatus[status][0],
                'class': channelStatus[status][1]
            });
            $(e).append(statusLabel);
        });
    };
    initChannelStatus();

    var initOpBtn = function () {
        var btnCallback = function (suffix, action) {
            return function () {
                var channelId = $(this).data('channel-id');
                var channelName = $(this).data('channel-name');
                var url = '/admin/channels/' + channelId + suffix;
                var msg = '确认对聊天室[' + channelName + ']的[' + action + ']操作吗?';
                WarningSwal(msg, function () {
                    var success = false;
                    $.post(url, function (data, status, xhr) {
                        if (xhr.code = 200) {
                            success = true
                        }
                    }).complete(function () {
                        if (success) {
                            SuccessSwal(action + '成功');
                            setTimeout('location.reload()', 3000);
                        } else {
                            FailedSwal(action + '失败');
                        }
                    });


                });
            };

        };

        $('.channel-disable').click(btnCallback('/disable', '封禁'));
        $('.channel-enable').click(btnCallback('/enable', '解禁'));
    };
    initOpBtn();

});