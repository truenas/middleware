#!/usr/local/bin/python
from middlewared.client import Client
from middlewared.client.utils import Struct

import os
import sys


def ldap_conf_ldap(client, ldap_conf):
    try:
        ldap = Struct(client.call('datastore.query', 'directoryservice.LDAP', None, {'get': True}))
    except:
        sys.exit(0)

    f = open(ldap_conf, "w")
    f.write("uri %s://%s\n" % (
        "ldaps" if ldap.ldap_ssl == "on" else "ldap",
        ldap.ldap_hostname
    ))
    f.write("base %s\n" % ldap.ldap_basedn)

    if ldap.ldap_ssl in ("start_tls", "on"):
        f.write("ssl %s\n" % ldap.ldap_ssl)
        cert = client.call('certificateauthority.query', [('id', '=', ldap.ldap_certificate.id)], {'get': True})
        capath = cert['cert_certificate_path']
        if capath:
            f.write("tls_cacert %s\n" % capath)
        f.write("tls_reqcert allow\n")

    f.write("scope sub\n")
    f.write("timelimit 30\n")
    f.write("bind_timelimit 30\n")
    f.write("bind_policy soft\n")

#    f.write("nss_map_attribute homeDirectory unixHomeDirectory\n")
    f.write("nss_override_attribute_value loginShell /bin/sh\n")

    if ldap.ldap_auxiliary_parameters:
        f.write(ldap.ldap_auxiliary_parameters)

    f.close()
    os.chmod(ldap_conf, 0o644)


def main():
    client = Client()
    ldap_conf = "/usr/local/etc/nss_ldap.conf"

    if client.call('notifier.common', 'system', 'ldap_enabled'):
        ldap_conf_ldap(client, ldap_conf)

if __name__ == '__main__':
    main()
