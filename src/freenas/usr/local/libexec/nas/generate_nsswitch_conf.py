#!/usr/local/bin/python

import os
import string
import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

from django.db.models.loading import cache
cache.get_apps()

NSSWITCH_CONF_PATH = "/etc/nsswitch.conf"

from freenasUI.common.system import (
    activedirectory_enabled,
    activedirectory_has_unix_extensions,
    activedirectory_has_keytab,
    domaincontroller_enabled,
    ldap_enabled,
    ldap_sudo_configured,
    nis_enabled,
    nt4_enabled
)

def main():
    nsswitch_conf = {
        'group': ['files'],
        'hosts': ['files', 'dns'],
        'networks': ['files'],
        'passwd': ['files'],
        'shells': ['files'],
        'services': ['files'],
        'protocols': ['files'],
        'rpc': ['files'],
        'sudoers': ['files']
    }

    verb = "start"
    if len(sys.argv) > 1:
        verb = sys.argv[1].lower()

    if verb == 'start':
        if activedirectory_enabled() and \
            activedirectory_has_unix_extensions() and  \
            activedirectory_has_keytab():
            nsswitch_conf['passwd'].append('sss')
            nsswitch_conf['group'].append('sss')
        elif activedirectory_enabled() or \
            domaincontroller_enabled() or nt4_enabled():
            nsswitch_conf['passwd'].append('winbind')
            nsswitch_conf['group'].append('winbind')

        #if nt4_enabled():
        #    nsswitch_conf['hosts'].append('wins')

        if ldap_enabled():
            nsswitch_conf['passwd'].append('sss')
            nsswitch_conf['group'].append('sss')
            if ldap_sudo_configured():
                nsswitch_conf['sudoers'].append('sss')

        if nis_enabled():
            nsswitch_conf['passwd'].append('nis')
            nsswitch_conf['group'].append('nis')
            nsswitch_conf['hosts'].append('nis')

    try:
        fd = os.open(NSSWITCH_CONF_PATH, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0644)
        for key in nsswitch_conf:
            line = "%s: %s\n" % (
                key.strip(),
                string.join(map(lambda x: x.strip(), nsswitch_conf[key]), ' ')
            )
            os.write(fd, line)
        os.close(fd)

    except Exception as e:
        print >> sys.stderr, "can't create %s: %s" % (NSSWITCH_CONF_PATH, e)
        sys.exit(1)

if __name__ == '__main__':
    main()
