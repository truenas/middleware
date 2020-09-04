from middlewared.plugins.service_.services.base import SimpleService


class DockerService(SimpleService):
    name = 'docker'
    etc = ['docker']
    systemd_unit = 'docker'
