from .base import SimpleService


class WebDAVService(SimpleService):
    name = "webdav"

    etc = ["webdav"]
    deprecated = True

    systemd_unit = "apache2"
