#!/usr/bin/env python

import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

from freenasUI import settings
from django.core.management import setup_environ
setup_environ(settings)

def main():
    """Use the django ORM to generate a config file.  We'll build the
    config file as a series of lines, and once that is done write it
    out in one go"""

    afpd_config = "/etc/afpd.conf"
    cf_contents = []

    from freenasUI.services.models import AFP
    afp = AFP.objects.order_by('id')[0]

    cf_contents.append("[Global]")
    
    if afp.afp_srv_guest:
        cf_contents.append("\tuam list = uams_dhx.so uams_dhx2.so"
                           " uams_guest.so")
        cf_contents.append('\tguest account = "%s"' % afp.afp_srv_guest_user)
    else:
        cf_contents.append("\tuam list = uams_dhx.so uams_dhx2.so")

    cf_contents.append("\tmax connections = %s" % afp.afp_srv_connections_limit)
    cf_contents.append("\tmimic model = RackMac")
    #server_name = afp.afp_srv_name
    cf_contents.append("")

    from freenasUI.sharing.models import AFP_Share
    afp_share = AFP_Share.objects.all()
    for share in afp_share:
        cf_contents.append("[%s]" % share.afp_name)

    for line in cf_contents:
        print line

if __name__ == "__main__":
    main()
