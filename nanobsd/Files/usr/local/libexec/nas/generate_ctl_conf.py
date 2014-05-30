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


def main():
    """Use the django ORM to generate a config file.  We'll build the
    config file as a series of lines, and once that is done write it
    out in one go"""

    ctl_config = "/etc/ctl.conf"
    cf_contents = []

    from freenasUI.services.models import iSCSITargetGlobalConfiguration
    from freenasUI.services.models import iSCSITargetExtent
    from freenasUI.services.models import iSCSITargetPortal
    from freenasUI.services.models import iSCSITargetPortalIP
    from freenasUI.services.models import iSCSITargetAuthorizedInitiator
    from freenasUI.services.models import iSCSITargetAuthCredential
    from freenasUI.services.models import iSCSITarget
    from freenasUI.services.models import iSCSITargetToExtent

    # Generate the auth section
    # Work around SQLite not supporting DISTINCT ON
    val = None
    open = False
    AUTH = None
    for id in iSCSITargetAuthCredential.objects.order_by('iscsi_target_auth_tag'):
        if not val:
            val = id.iscsi_target_auth_tag
            open = True
        else:
            if val == id.iscsi_target_auth_tag:
                pass
            else:
                val = id.iscsi_target_auth_tag
                open = True
                AUTH = None
                cf_contents.append("}\n")
        if open:
            cf_contents.append("auth-group ag%d {\n" % id.iscsi_target_auth_tag)
            open = False
        # It is an error to mix CHAP and Mutual CHAP in the same auth group
        # But not in istgt, so we need to catch this and do something.
        # For now just skip over doing something that would cause ctld to bomb
        if id.iscsi_target_auth_peeruser and AUTH not == "CHAP":
            AUTH = "Mutual"
            cf.contents.append("\tchap-mutual %s %s %s %s\n" % (id.iscsi_target_auth_user, id.iscsi_target_auth_secret,
                                                                    id.iscsi_target_auth_peeruser, id.iscsi_target_auth_peersecret))
        elif AUTH not == "Mutual":
            AUTH = "CHAP"
            cf_contents.append("\tchap %s %s\n" % (id.iscsi_target_auth_user, id.iscsi_target_auth_secret))
    cf_contents.append("}\n")

if __name__ == "__main__":
    main()
