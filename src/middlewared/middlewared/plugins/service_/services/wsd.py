from .base import SimpleService


class WSDService(SimpleService):
    name = "wsd"

    freebsd_rc = "wsdd"
