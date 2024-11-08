from middlewared.rclone.base import BaseRcloneRemote


class YandexRcloneRemote(BaseRcloneRemote):
    name = "YANDEX"
    title = "Yandex"

    fast_list = True

    rclone_type = "yandex"

    credentials_oauth = True
    refresh_credentials = ["token"]
