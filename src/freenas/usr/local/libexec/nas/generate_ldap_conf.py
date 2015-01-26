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

from freenasUI.common.freenasldap import (
    FreeNAS_ActiveDirectory,
    FreeNAS_LDAP,
    FLAGS_DBINIT
)
from freenasUI.common.ssl import get_certificateauthority_path
from freenasUI.common.system import (
    activedirectory_enabled,
    ldap_enabled
)
from freenasUI.directoryservice import models

def ldap_conf_ldap(ldap_conf):
    try:
        ldap = models.LDAP.objects.all()[0]
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

def ldap_conf_activedirectory(ldap_conf):
    ad = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)
    
    f = open(ldap_conf, "w")
    f.write("URI %s://%s\n" % (
        "ldaps" if ad.ssl == "on" else "ldap",
        ad.domainname
    ))
    f.write("BASE %s\n" % ad.basedn)

    if ad.ssl in ("start_tls", "on"):
        if ad.certfile: 
            f.write("TLS_CACERT %s\n" % ad.certfile)
        f.write("TLS_REQCERT allow\n")

    f.close()
    os.chmod(ldap_conf, 0644)

def main():
    ldap_conf = "/usr/local/etc/openldap/ldap.conf"

    if ldap_enabled():
        ldap_conf_ldap(ldap_conf)
    elif activedirectory_enabled():
        ldap_conf_activedirectory(ldap_conf)

if __name__ == '__main__':
    main()
