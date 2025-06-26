from .base import SimpleService


class SSSDService(SimpleService):
    name = "sssd"

    systemd_unit = "sssd"
