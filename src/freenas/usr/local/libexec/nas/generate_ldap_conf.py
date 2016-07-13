#!/usr/local/bin/python
from middlewared.client import Client
from middlewared.client.utils import Struct

import os
import re
import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

from django.db.models.loading import cache
cache.get_apps()

from freenasUI.common.freenasldap import (
    FreeNAS_ActiveDirectory,
    FLAGS_DBINIT
)
from freenasUI.common.ssl import get_certificateauthority_path
from freenasUI.directoryservice.utils import get_idmap_object


def ldap_conf_ldap(client, ldap_conf):
    try:
        ldap = Struct(client.call('datastore.query', 'directoryservice.ldap', None, {'get': True}))
    except:
        sys.exit(0)

    f = open(ldap_conf, "w")
    f.write("URI %s://%s\n" % (
        "ldaps" if ldap.ldap_ssl == "on" else "ldap",
        ldap.ldap_hostname
    ))
    f.write("BASE %s\n" % ldap.ldap_basedn)

    if ldap.ldap_ssl in ("start_tls", "on"):
        capath = get_certificateauthority_path(ldap.ldap_certificate)
        if capath:
            f.write("TLS_CACERT %s\n" % capath)
        f.write("TLS_REQCERT allow\n")

    f.close()
    os.chmod(ldap_conf, 0644)


def ldap_conf_activedirectory(client, ldap_conf):
    ad = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)

    config = {}
    config["URI"] = "%s://%s" % (
        "ldaps" if ad.ssl == "on" else "ldap",
        ad.domainname
    )
    config["BASE"] = ad.basedn

    if ad.ssl in ("start_tls", "on"):
        if ad.certfile:
            config["TLS_CACERT"] = ad.certfile
        config["TLS_REQCERT"] = "allow"

    #
    # So what if the AD server is configured to use SSL or TLS,
    # and the idmap backend is as well? WTF? whaddoyoudo?
    #
    ad = Struct(client.call('datastore.query', 'directoryservice.activedirectory', None, {'get': True}))
    if ad.ad_idmap_backend in ("rfc2307", "ldap"):
        idmap = get_idmap_object(ad.ds_type, ad.id, ad.ad_idmap_backend)
        idmap_url = idmap.get_url()
        idmap_url = re.sub('^(ldaps?://)', '', idmap_url)

        config["URI"] = "%s://%s" % (
            "ldaps" if idmap.get_ssl() == "on" else "ldap",
            idmap_url
        )

        if idmap.get_ssl() in ('start_tls', 'on'):
            capath = get_certificateauthority_path(idmap.get_certificate())
            if capath:
                config["TLS_CACERT"] = capath
            config["TLS_REQCERT"] = "allow"

    keys = ["URI", "BASE", "TLS_CACERT", "TLS_REQCERT"]
    with open(ldap_conf, "w") as f:
        for key in keys:
            if key in config:
                f.write("%s %s\n" % (key, config[key]))
        f.close()
    os.chmod(ldap_conf, 0644)


def main():
    client = Client()
    ldap_conf = "/usr/local/etc/openldap/ldap.conf"

    if client.call('notifier.common', 'system', 'ldap_enabled'):
        ldap_conf_ldap(client, ldap_conf)
    elif client.call('notifier.common', 'system', 'activedirectory_enabled'):
        ldap_conf_activedirectory(client, ldap_conf)

if __name__ == '__main__':
    main()
