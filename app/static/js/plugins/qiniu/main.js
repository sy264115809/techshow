/*global Qiniu */
/*global plupload */
/*global FileProgress */
/*global hljs */


// uploader factory
function initUploader(options) {
    var toasts = {};
    var addedCallback = function (callback) {
        return function (up, files) {
            $.each(files, function (i, file) {
                toasts[file.name] = toastr.warning('上传中: ' + file.name + ' ...', '', {
                    "timeOut": "0",
                    "extendedTimeOut": "0"
                });
            });
            callback(up, files);
        }
    };
    var uploadedCallback = function (callback) {
        return function (up, file, result) {
            if (toasts[file.name]) {
                toasts[file.name].hide();
                toasts[file.name].remove();
            }
            callback(up, file, result);
        }
    };
    var errorCallback = function (callback) {
        return function (up, err, errtip) {
            var file = err.file;
            if (toasts[file.name]) {
                toasts[file.name].hide();
                toasts[file.name].clear();
            }
            if (file) {
                switch (err.code) {
                    case plupload.FILE_SIZE_ERROR:
                        var max_file_size = up.getOption && up.getOption('max_file_size');
                        max_file_size = max_file_size || (up.settings && up.settings.max_file_size);
                        toastr.error('"' + file.name
                            + '" 超过了图片上传大小限制:'
                            + max_file_size);

                }
            }
            toastr.error('Upload "' + err.file.name + '" error.');
            callback(up, err, errtip);
        }
    };
    var defaults = {
        runtimes: 'html5,flash,html4', //上传模式,依次退化
        dragdrop: false, //是否允许拖拽上传
        max_file_size: '20mb', //最大允许上传文件的大小
        flash_swf_url: '/static/js/plugins/qiniu/Moxie.swf',
        chunk_size: '4mb', //分片上传的大小
        auto_start: false, //选择文件后自动开始
        max_retries: 3,  //最大失败重试次数
        multi_selection: false,
        filters: {
            mime_types: [
                {title: 'Image files', extensions: "jpg,png"}
            ]
        },
        init: {
            'FileUploaded': function (up, file, result) {
                toastr.success('Upload "' + file.name + '" success.')
            }
        }
    };
    var settings = $.extend(true, {}, defaults, options);
    var _FileAdded_Handler = settings.init.FilesAdded || function (up, files) {
        };
    var _FileUploaded_Handler = settings.init.FileUploaded || function (up, file, result) {
        };
    var _Error_Handler = settings.init.Error || function (up, err, errTip) {
        };

    settings.init.FilesAdded = addedCallback(_FileAdded_Handler);
    settings.init.FileUploaded = uploadedCallback(_FileUploaded_Handler);
    settings.init.Error = errorCallback(_Error_Handler);
    settings.init.Key = function (up, file) {
    };//保证文件的hash为文件名

    return Qiniu.uploader(settings);
}
