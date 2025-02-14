import logging

from middlewared.service import Service


logger = logging.getLogger('truenas_connect')


class TNCPostInstallService(Service):

    class Config:
        private = True
        namespace = 'tn_connect.post_install'

    async def process(self, post_install_config):
        if 'tnc_config' not in (post_install_config or {}):
            return
