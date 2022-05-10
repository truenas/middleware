from .base import SimpleService


class WSDService(SimpleService):
    name = "wsdd"
    etc = ["wsd"]
    freebsd_rc = "wsdd"
    freebsd_proc_arguments_match = True
