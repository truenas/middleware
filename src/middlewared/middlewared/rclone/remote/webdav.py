from middlewared.rclone.base import BaseRcloneRemote


class WebDavRcloneRemote(BaseRcloneRemote):
    name = "WEBDAV"
    title = "WebDAV"

    rclone_type = "webdav"

    def get_task_extra(self, task):
        return dict(vendor=task["credentials"]["provider"]["vendor"].lower())
