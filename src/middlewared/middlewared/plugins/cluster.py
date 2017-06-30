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
django.setup()

from freenasUI.common.freenassysctl import freenas_sysctl as _fs

class ClusterService(Service):

    def __init__(self, *args):
        super(ClusterService, self).__init__(*args)

#def setup(middleware):
#    asyncio.ensure_future(middleware.call('cluster.start'))
