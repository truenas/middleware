#!/usr/local/bin/python

import os
import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.sharing.models import AFP_Share
from freenasUI.services.models import AFP

def main():
    """Use the django ORM to generate a config file.  We'll build the
    config file as a series of lines, and once that is done write it
    out in one go"""

    afp_config = "/usr/local/etc/afp.conf"
    cf_contents = []

    afp = AFP.objects.order_by('-id')[0]

    cf_contents.append("[Global]\n")

    if afp.afp_srv_guest:
        cf_contents.append("\tuam list = uams_dhx.so uams_dhx2.so"
                           " uams_guest.so\n")
        cf_contents.append('\tguest account = %s\n' % afp.afp_srv_guest_user)
    else:
        cf_contents.append("\tuam list = uams_dhx.so uams_dhx2.so\n")

    if afp.afp_srv_bindip:
        cf_contents.append("\tafp listen = %s\n" % ' '.join(afp.afp_srv_bindip))
    cf_contents.append("\tmax connections = %s\n" % afp.afp_srv_connections_limit)
    cf_contents.append("\tmimic model = RackMac\n")
    if afp.afp_srv_dbpath:
        cf_contents.append("\tvol dbnest = no\n")
        cf_contents.append("\tvol dbpath = %s\n" % afp.afp_srv_dbpath)
    else:
        cf_contents.append("\tvol dbnest = yes\n")
    if afp.afp_srv_global_aux:
        cf_contents.append("\t%s" % afp.afp_srv_global_aux.encode('utf8'))
    cf_contents.append("\n")

    if afp.afp_srv_homedir_enable:
        cf_contents.append("[Homes]\n")
        cf_contents.append("\tbasedir regex = %s\n" % afp.afp_srv_homedir)
        if afp.afp_srv_homename:
            cf_contents.append('\thome name = "%s"\n' % afp.afp_srv_homename)
        cf_contents.append("\n")

    for share in AFP_Share.objects.all():
        cf_contents.append("[%s]\n" % share.afp_name)
        cf_contents.append("\tpath = %s\n" % share.afp_path)
        if share.afp_allow:
            cf_contents.append("\tvalid users = %s\n" % share.afp_allow)
        if share.afp_deny:
            cf_contents.append("\tinvalid users = %s\n" % share.afp_deny)
        if share.afp_hostsallow:
            cf_contents.append("\thosts allow = %s\n" % share.afp_hostsallow)
        if share.afp_hostsdeny:
            cf_contents.append("\thosts deny = %s\n" % share.afp_hostsdeny)
        if share.afp_ro:
            cf_contents.append("\trolist = %s\n" % share.afp_ro)
        if share.afp_rw:
            cf_contents.append("\trwlist = %s\n" % share.afp_rw)
        if share.afp_timemachine:
            cf_contents.append("\ttime machine = yes\n")
        if not share.afp_nodev:
            cf_contents.append("\tcnid dev = no\n")
        if share.afp_nostat:
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
        cf_contents.append("\tveto files = .windows/.mac/\n")

    with open(afp_config, "w") as fh:
        for line in cf_contents:
            fh.write(line)

if __name__ == "__main__":
    main()
