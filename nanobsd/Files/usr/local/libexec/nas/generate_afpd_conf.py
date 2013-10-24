#!/usr/local/bin/python

import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

from freenasUI import settings
from django.core.management import setup_environ
setup_environ(settings)

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

def main():
    """Use the django ORM to generate a config file.  We'll build the
    config file as a series of lines, and once that is done write it
    out in one go"""

    afp_config = "/usr/local/etc/afp.conf"
    cf_contents = []

    from freenasUI.services.models import AFP
    afp = AFP.objects.order_by('id')[0]

    cf_contents.append("[Global]\n")
    
    if afp.afp_srv_guest:
        cf_contents.append("\tuam list = uams_dhx.so uams_dhx2.so"
                           " uams_guest.so\n")
        cf_contents.append('\tguest account = %s\n' % afp.afp_srv_guest_user)
    else:
        cf_contents.append("\tuam list = uams_dhx.so uams_dhx2.so\n")

    cf_contents.append("\tmax connections = %s\n" % afp.afp_srv_connections_limit)
    cf_contents.append("\tmimic model = RackMac\n")
    #server_name = afp.afp_srv_name
    cf_contents.append("\n")

    from freenasUI.sharing.models import AFP_Share
    afp_share = AFP_Share.objects.all()
    for share in afp_share:
        cf_contents.append("[%s]\n" % share.afp_name)
        cf_contents.append("\tpath = %s\n" % share.afp_path)
        if share.afp_sharepw:
            cf_contents.append("\tpassword = %s\n" % share.afp_sharepw)
        if share.afp_allow:
            cf_contents.append("\tallow = %s\n" % share.afp_allow)
        if share.afp_deny:
            cf_contents.append("\tdeny = %s\n" % share.afp_deny)
        if share.afp_ro:
            cf_contents.append("\trolist = %s\n" % share.afp_ro)
        if share.afp_rw:
            cf_contents.append("\trwlist = %s\n" % share.afp_rw)
        if share.afp_timemachine:
            cf_contents.append("\ttime machine = yes\n")
        if share.afp_dbpath:
            cf_contents.append("\tvol dbpath = %s\n" % share.afp_dbpath)
        if not share.afp_nodev:
            cf_contents.append("\tcnid dev = no\n")
        if not share.afp_nostat:
            cf_contents.append("\tstat vol = no\n")
        if not share.afp_upriv:
            cf_contents.append("\tunix priv = no\n")
        else:
            if share.afp_fperm:
                cf_contents.append("\tfile perm = %s\n" % share.afp_fperm)
            if share.afp_dperm:
                cf_contents.append("\tdirectory perm = %s\n" % share.afp_dperm)
            if share.afp_umask:
                cf_contents.append("\tumask = %s\n" % share.afp_umask)

    fh = open(afp_config, "w")
    for line in cf_contents:
        fh.write(line)
    fh.close()

if __name__ == "__main__":
    main()
