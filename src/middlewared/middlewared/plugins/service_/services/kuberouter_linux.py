from middlewared.plugins.service_.services.base import SimpleService


class KubeRouterService(SimpleService):
    name = 'kuberouter'
    systemd_unit = 'kube-router'
