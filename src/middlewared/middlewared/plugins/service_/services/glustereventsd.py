from .base import SimpleService


class GlusterEventsdService(SimpleService):

    name = 'glustereventsd'
    systemd_unit = 'glustereventsd'

    restartable = True
    reloadable = True
