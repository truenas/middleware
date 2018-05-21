from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class WebDavRcloneRemote(BaseRcloneRemote):
    name = "WEBDAV"
    title = "WebDAV"

    rclone_type = "webdav"

    credentials_schema = [
        Str("url", verbose="URL", required=True),
        Str("vendor", verbose="Name of the WebDAV site/service/software",
            enum=["NEXTCLOUD", "OWNCLOUD", "SHAREPOINT", "OTHER"], required=True),
        Str("user", verbose="Username", required=True),
        Str("pass", verbose="Password", required=True),
    ]

    def get_task_extra(self, task):
        return dict(vendor=task["attributes"]["vendor"].lower())
