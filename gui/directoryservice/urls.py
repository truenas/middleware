# Copyright 2014 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################
from django.conf.urls import url

from .views import (
    directoryservice_home, directoryservice_status,
    directoryservice_kerberosrealm, directoryservice_kerberoskeytab_edit,
    directoryservice_kerberoskeytab_delete,
    directoryservice_kerberoskeytab_add,
    directoryservice_idmap_ad, directoryservice_idmap_adex,
    directoryservice_idmap_autorid, directoryservice_idmap_hash,
    directoryservice_idmap_ldap, directoryservice_idmap_nss,
    directoryservice_idmap_rfc2307, directoryservice_idmap_rid,
    directoryservice_idmap_tdb, directoryservice_idmap_tdb2,
    directoryservice_idmap_backend, directoryservice_clearcache,
)


urlpatterns = [
    url(r"^home/$", directoryservice_home, name="directoryservice_home"),
    url(r"^status/$", directoryservice_status, name="directoryservice_status"),
    url(r"^kerberos_realm/(?P<id>\d+)/$", directoryservice_kerberosrealm,
        name="directoryservice_kerberosrealm"),
    url(r"^kerberos_keytab_edit/(?P<id>\d+)/$",
        directoryservice_kerberoskeytab_edit,
        name="directoryservice_kerberoskeytab_edit"),
    url(r"^kerberos_keytab_delete/(?P<id>\d+)/$",
        directoryservice_kerberoskeytab_delete,
        name="directoryservice_kerberoskeytab_delete"),
    url(r"^kerberos_keytab_add/$",
        directoryservice_kerberoskeytab_add,
        name="directoryservice_kerberoskeytab_add"),
    url(r"^idmap_ad/(?P<id>\d+)/$", directoryservice_idmap_ad,
        name="directoryservice_idmap_ad"),
    url(r"^idmap_adex/(?P<id>\d+)/$", directoryservice_idmap_adex,
        name="directoryservice_idmap_adex"),
    url(r"^idmap_autorid/(?P<id>\d+)/$", directoryservice_idmap_autorid,
        name="directoryservice_idmap_autorid"),
    url(r"^idmap_hash/(?P<id>\d+)/$", directoryservice_idmap_hash,
        name="directoryservice_idmap_hash"),
    url(r"^idmap_ldap/(?P<id>\d+)/$", directoryservice_idmap_ldap,
        name="directoryservice_idmap_ldap"),
    url(r"^idmap_nss/(?P<id>\d+)/$", directoryservice_idmap_nss,
        name="directoryservice_idmap_nss"),
    url(r"^idmap_rfc2307/(?P<id>\d+)/$", directoryservice_idmap_rfc2307,
        name="directoryservice_idmap_rfc2307"),
    url(r"^idmap_rid/(?P<id>\d+)/$", directoryservice_idmap_rid,
        name="directoryservice_idmap_rid"),
    url(r"^idmap_tdb/(?P<id>\d+)/$", directoryservice_idmap_tdb,
        name="directoryservice_idmap_tdb"),
    url(r"^idmap_tdb2/(?P<id>\d+)/$", directoryservice_idmap_tdb2,
        name="directoryservice_idmap_tdb2"),
    url(r"^idmap_backend/(?P<obj_type>\d+)/(?P<obj_id>\d+)/(?P<idmap_type>.+)/$",
        directoryservice_idmap_backend,
        name="directoryservice_idmap_backend"),
    url(r"^clearcache/$", directoryservice_clearcache,
        name="directoryservice_clearcache"),
]
