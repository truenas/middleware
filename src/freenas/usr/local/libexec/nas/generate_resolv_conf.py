#!/usr/local/bin/python
from middlewared.client import Client
from middlewared.client.utils import Struct

import os
import errno
import sys

RESOLV_CONF_PATH = "/etc/resolv.conf"


def main():

    client = Client()
    domain = None
    nameservers = []

    if client.call('notifier.common', 'system', 'domaincontroller_enabled'):
        try:
            cifs = Struct(client.call('datastore.query', 'services.cifs', None, {'get': True}))
            dc = Struct(client.call('datastore.query', 'services.DomainController', None, {'get': True}))

            domain = dc.dc_realm
            if cifs.cifs_srv_bindip:
                for ip in cifs.cifs_srv_bindip:
                    nameservers.append(ip)
            else:
                nameservers.append("127.0.0.1")

        except Exception as e:
            print >> sys.stderr, "ix-resolv: ERROR: %s" % e
            sys.exit(1)

    else:
        try:
            gc = client.call('datastore.query', 'network.globalconfiguration', None, {'get': True})
            if gc['gc_domain']:
                domain = gc['gc_domain']
            if gc['gc_nameserver1']:
                nameservers.append(gc['gc_nameserver1'])
            if gc['gc_nameserver2']:
                nameservers.append(gc['gc_nameserver2'])
            if gc['gc_nameserver3']:
                nameservers.append(gc['gc_nameserver3'])

        except Exception as e:
            print >> sys.stderr, "ix-resolv: ERROR: %s" % e
            sys.exit(1)

    iface_count = client.call('datastore.query', 'network.interfaces', None, {'count': True})
    iface_dhcp = client.call('datastore.query', 'network.interfaces', [('int_dhcp', '=', True)], {'count': True})

    if (
        not nameservers and
        (iface_count == 0 or iface_dhcp > 0)
    ):
        # since we have set a dhclient hook that disables dhclient from writing to /etc/resolv.conf
        # we should remove it now
        try:
            os.remove("/etc/dhclient-enter-hooks")
        except OSError as e:
            # if this error is not due to the file not existing then we have a problem
            if e.errno != errno.ENOENT:
                raise
            # else we never wrote that file so....moving on
            pass
        sys.exit(0)

    try:
        fd = os.open(RESOLV_CONF_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0x0644)
        if domain:
            os.write(fd, "search %s\n" % domain)
        for ns in nameservers:
            os.write(fd, "nameserver %s\n" % ns)
        os.close(fd)
        with open("/etc/dhclient-enter-hooks", 'w') as f:
            f.write(
                """
                add_new_resolv_conf() {
                    # We don't want /etc/resolv.conf changed
                    # So this is an empty function
                    return 0
                }
                """
            )
        os.chmod("/etc/dhclient-enter-hooks", 0x0744)

    except Exception as e:
        print >> sys.stderr, "can't create %s: %s" % (RESOLV_CONF_PATH, e)
        sys.exit(1)

if __name__ == '__main__':
    main()
