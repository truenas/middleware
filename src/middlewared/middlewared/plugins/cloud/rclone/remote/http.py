from middlewared.api.current import HTTPCredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote


class HTTPRcloneRemote(BaseRcloneRemote[HTTPCredentialsModel]):
    credentials_schema = HTTPCredentialsModel

    name = "HTTP"
    title = "HTTP"

    readonly = True

    rclone_type = "http"
