import asyncio
import os
import socket
import random
import sys
import threading
import time

from middlewared.service import Service, private

if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

import django
from django.apps import apps
if not apps.ready:
    django.setup()

from freenasUI.common.freenassysctl import freenas_sysctl as _fs

class ClusterNode(object):
    def __init__(self, *args, **kwargs):
        self.logger = kwargs.get('logger')
        self.interface = kwargs.get('interface')
        self.name = kwargs.get('name')
        self.target = kwargs.get('target')
        self.port = kwargs.get('port')
        self.ssl = kwargs.get('ssl')

    def __str__(self):
        return "%s:%d" % (self.name, self.port)


class ClusterService(Service):

    def __init__(self, *args):
        super(ClusterService, self).__init__(*args)
        self.__nodes = []
        self.__available_nodes = []

    def _is_middleware(self, name, ssl):
        res = False

        parts = name.split('.')
        if len(parts) < 2:
            return False

        regtype = parts[1]
        if not regtype:
            return False

        regtype = regtype.lower()
        if regtype == '_middlwre-http':
            res = True
        elif regtype == '_middlwre-https':
            res = True
            ssl[0] = True
        elif regtype == '_middleware':
            res = True
        elif regtype == '_middleware-ssl':
            res = True
            ssl[0] = True

        return res

    async def get_available_nodes(self):
        services = await self.middleware.call('mdnsbrowser.get_services')
        if not services:
            return

        for s in services:
            if not ('name' in s and s['name']):
                continue

            ssl = [False]
            name = s['name']
            if not self._is_middleware(name, ssl):
                continue

            self.__available_nodes.append(
                ClusterNode(
                    **dict({
                         'logger': self.logger,
                        'ssl': ssl[0]
                    }, **s)
                )
            )
        for node in self.__available_nodes:
            self.logger.debug("Cluster: node=%s", node)

    def node_add(self):
        pass

    def node_remove(self):
        pass

    def node_list(self):
        pass

    def node_check(self):
        pass


#def setup(middleware):
#    asyncio.ensure_future(middleware.call('cluster.start'))
