from .base import SimpleService


class WebDAVService(SimpleService):
    name = "webdav"

    etc = ["webdav"]

    systemd_unit = "apache2"
