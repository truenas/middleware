#!/usr/local/bin/python
from middlewared.client import Client

import os
import sys


NSSWITCH_CONF_PATH = "/etc/nsswitch.conf"


def main():
    nsswitch_conf = {
        'group': ['files'],
        'hosts': ['files', 'mdns', 'dns'],
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

    client = Client()
    activedirectory_enabled = client.call('notifier.common', 'system', 'activedirectory_enabled')
    domaincontroller_enabled = client.call('notifier.common', 'system', 'domaincontroller_enabled')
    ldap_enabled = client.call('notifier.common', 'system', 'ldap_enabled')
    nis_enabled = client.call('notifier.common', 'system', 'nis_enabled')
    nt4_enabled = client.call('notifier.common', 'system', 'nt4_enabled')

    if verb == 'start':
        if activedirectory_enabled and \
            client.call('notifier.common', 'system', 'activedirectory_has_unix_extensions') and \
            client.call('notifier.common', 'system', 'activedirectory_has_principal'):
            nsswitch_conf['passwd'].append('sss')
            nsswitch_conf['group'].append('sss')
        elif activedirectory_enabled or \
            domaincontroller_enabled or nt4_enabled:
            nsswitch_conf['passwd'].append('winbind')
            nsswitch_conf['group'].append('winbind')

        #if nt4_enabled():
        #    nsswitch_conf['hosts'].append('wins')

        if ldap_enabled and client.call('notifier.common', 'system', 'ldap_anonymous_bind'):
            nsswitch_conf['passwd'].append('ldap')
            nsswitch_conf['group'].append('ldap')
        elif ldap_enabled:
            nsswitch_conf['passwd'].append('sss')
            nsswitch_conf['group'].append('sss')
            if client.call('notifier.common', 'system', 'ldap_sudo_configured'):
                nsswitch_conf['sudoers'].append('sss')

        if nis_enabled:
            nsswitch_conf['passwd'].append('nis')
            nsswitch_conf['group'].append('nis')
            nsswitch_conf['hosts'].append('nis')

    try:
        fd = os.open(NSSWITCH_CONF_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        for key in nsswitch_conf:
            line = "%s: %s\n" % (
                key.strip(),
                ' '.join([x.strip() for x in nsswitch_conf[key]])
            )
            os.write(fd, line.encode('utf8'))
        os.close(fd)

    except Exception as e:
        print("can't create %s: %s" % (NSSWITCH_CONF_PATH, e), file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
