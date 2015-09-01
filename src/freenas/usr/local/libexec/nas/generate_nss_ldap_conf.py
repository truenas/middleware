#!/usr/local/bin/python

import os
import re
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
from freenasUI.directoryservice.utils import get_idmap_object

def ldap_conf_ldap(ldap_conf):
    try:
        ldap = models.LDAP.objects.all()[0]
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
        capath = get_certificateauthority_path(ldap.ldap_certificate)
        if capath:
            f.write("tls_cacert %s\n" % capath)
        f.write("tls_reqcert allow\n")

    f.write("scope sub\n")
    f.write("timelimit 30\n")
    f.write("bind_timelimit 30\n")
    f.write("bind_policy soft\n")

    f.write("nss_map_attribute homeDirectory unixHomeDirectory\n")
    f.write("nss_override_attribute_value loginShell /bin/sh\n")

    if ldap.ldap_auxiliary_parameters:
        f.write(ldap.ldap_auxiliary_parameters)

    f.close()
    os.chmod(ldap_conf, 0644)

def main():
    ldap_conf = "/usr/local/etc/nss_ldap.conf"

    if ldap_enabled():
        ldap_conf_ldap(ldap_conf)

if __name__ == '__main__':
    main()
