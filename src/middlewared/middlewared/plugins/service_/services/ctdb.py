from .base import SimpleService


class CtdbService(SimpleService):

    name = 'ctdb'
    systemd_unit = 'ctdb'
    restartable = True
    etc = ['ctdb', 'ctdb_public', 'ctdb_private']
