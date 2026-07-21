from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api.current import WebDavCredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote

if TYPE_CHECKING:
    from middlewared.api.current import CloudTaskAttributes


class WebDavRcloneRemote(BaseRcloneRemote[WebDavCredentialsModel]):
    credentials_schema = WebDavCredentialsModel

    name = "WEBDAV"
    title = "WebDAV"

    rclone_type = "webdav"

    def get_task_extra(self, attributes: CloudTaskAttributes, credentials: WebDavCredentialsModel) -> dict[str, Any]:
        return dict(vendor=credentials.vendor.get_secret_value().lower())
