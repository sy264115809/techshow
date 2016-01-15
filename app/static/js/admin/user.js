$(function () {
    var initOpBtn = function () {
        var btnCallback = function (suffix, action) {
            return function () {
                var userId = $(this).data('user-id');
                var userName = $(this).data('user-name');
                var url = '/admin/users/' + userId + suffix;
                var msg = '确认对用户[' + userName + ']的[' + action + ']操作吗?';
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

        $('.user-ban').click(btnCallback('/ban', '封禁'));
        $('.user-unban').click(btnCallback('/unban', '解禁'));
        $('.stream-disable').click(btnCallback('/stream/disable', '关闭流'));
        $('.stream-enable').click(btnCallback('/stream/enable', '启用流'));
    };
    initOpBtn();

});