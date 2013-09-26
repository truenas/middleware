#!/usr/bin/env python

import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

from freenasUI import settings

from django.core.management import setup_environ
setup_environ(settings)

from freenasUI.services.models import AFP

afp = AFP.objects.order_by('id')[0]
afpd_config = "/etc/afpd.conf"

guest_user = afp.afp_srv_guest_user
allow_guest = afp.afp_srv_guest
max_connections = afp.afp_srv_connections_limit
server_name = afp.afp_srv_name
print guest_user
