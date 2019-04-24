from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class WebDavRcloneRemote(BaseRcloneRemote):
    name = "WEBDAV"
    title = "WebDAV"

    rclone_type = "webdav"

    credentials_schema = [
        Str("url", title="URL", required=True),
        Str("vendor", title="Name of the WebDAV site/service/software",
            enum=["NEXTCLOUD", "OWNCLOUD", "SHAREPOINT", "OTHER"], required=True),
        Str("user", title="Username", required=True),
        Str("pass", title="Password", required=True),
    ]

    async def get_task_extra(self, task):
        return dict(vendor=task["credentials"]["attributes"]["vendor"].lower())
