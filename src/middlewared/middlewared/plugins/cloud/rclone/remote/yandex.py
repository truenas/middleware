from middlewared.api.current import YandexCredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote


class YandexRcloneRemote(BaseRcloneRemote[YandexCredentialsModel]):
    credentials_schema = YandexCredentialsModel

    name = "YANDEX"
    title = "Yandex"

    fast_list = True

    rclone_type = "yandex"

    credentials_oauth = True
    refresh_credentials = ["token"]
