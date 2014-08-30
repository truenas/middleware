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

from freenasUI.directoryservice import models
from freenasUI.common.ssl import get_certificateauthority_path

def main():
    ldap_conf = "/usr/local/etc/openldap/ldap.conf"

    try:
        ldap = models.LDAP.objects.all()[0]
    except:
        sys.exit(0)
    
    f = open(ldap_conf, "w")
    f.write("HOST %s\n" % ldap.ldap_hostname)
    f.write("BASE %s\n" % ldap.ldap_basedn)

    if ldap.ldap_ssl in ("start_tls", "on"):
        if ldap.ldap_ssl == "on":
            f.write("URI ldap://%s\n" % ldap.ldap_hostname)

        capath = get_certificateauthority_path(ldap.ldap_certificate)
        if capath:
            f.write("TLS_CACERT %s\n" % capath)
        f.write("TLS_REQCERT allow\n")

    f.close()
    os.chmod(ldap_conf, 0644)

if __name__ == '__main__':
    main()
