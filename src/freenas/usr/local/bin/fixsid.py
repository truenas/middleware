#!/usr/local/bin/python

import os
import sys

sids = os.popen("net groupmap list | awk '{print $2}'"
                " | sed -e 's/^(//' -e 's/)$//'").readlines()

sidlist = []

for sid in sids:
    sid = sid.strip()
    while not sid.endswith("-"):
        sid = sid[:-1]
    else:
        sid = sid[:-1]
        sidlist.append(sid)
        continue

# sanity check all the sids we have are the same
sanity = True
if sidlist:
    sidval = sidlist[0]
    for sid in sidlist:
        if sid != sidval:
            sanity = False

if sanity:
    sys.path.extend([
        '/usr/local/www',
        '/usr/local/www/freenasUI'
    ])

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

    import django
    django.setup()

    from freenasUI.common.system import (
        activedirectory_enabled,
        domaincontroller_enabled,
        ldap_enabled
    )

    if (activedirectory_enabled() or
            domaincontroller_enabled() or
            ldap_enabled()):
        print("A directory service is enabled, aborting without making changes.")
        exit(1)

    print("detected SID: %s\n" % sidval)
    from freenasUI.services.models import CIFS
    cifs = CIFS.objects.all()[0]
    print("database SID: %s\n" % cifs.cifs_SID)
    if cifs.cifs_SID != sidval:
        cifs.cifs_SID = sidval
        print("Saving detected SID to the database")
        cifs.save()
        print("Please either reboot the system or run the following commands as root:")
        print("service samba_server stop")
        print("service ix-pre-samba start")
        print("service samba_server start")
    else:
        print("Database SID is the same as the detected SID. Nothing to do.")
        exit(0)
else:
    print("Multiple SIDs detected, aborting without making changes.")
    exit(2)
