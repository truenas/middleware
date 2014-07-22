#+
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
from freenasUI.directoryservice import models

def get_ds_object(obj_type):
    ds_obj = None

    if obj_type == models.DS_TYPE_ACTIVEDIRECTORY:
        ds_obj = models.ActiveDirectory.objects.all()[0]

    elif obj_type == models.DS_TYPE_LDAP:
        ds_obj = models.LDAP.objects.all()[0]

    elif obj_type == models.DS_TYPE_NT4:
        ds_obj = models.NT4.objects.all()[0]

    return ds_obj


def get_ds_object_backend_type(obj_type):
    ds_obj_backend_type = None

    if obj_type == models.DS_TYPE_ACTIVEDIRECTORY:
        ad = models.ActiveDirectory.objects.all()[0]
        ds_obj_backend_type = ad.ad_idmap_backend_type

    elif obj_type == models.DS_TYPE_LDAP:
        ldap = models.LDAP.objects.all()[0]
        ds_obj_backend_type = ldap.ldap_idmap_backend_type

    elif obj_type == models.DS_TYPE_NT4:
        nt4 = models.NT4.objects.all()[0]
        ds_obj_backend_type = nt4.nt4_idmap_backend_type

    return ds_obj_backend_type


def get_directoryservice_idmap_object(obj_type):
    obj_type = int(obj_type)

    ds_obj = get_ds_object(obj_type)
    dsi = get_ds_object_backend_type(obj_type)

    return dsi


def get_idmap_object(obj_type, idmap_type):
    obj_type = int(obj_type)

    dsi = get_directoryservice_idmap_object(obj_type)
    if not dsi:
        return None

    if idmap_type == "idmap_ad":
        idmap = dsi.dsi_idmap_ad

    elif idmap_type == "idmap_autorid":
        idmap = dsi.dsi_idmap_autorid

    elif idmap_type == "idmap_hash":
        idmap = dsi.dsi_idmap_hash

    elif idmap_type == "idmap_ldap":
        idmap = dsi.dsi_idmap_ldap

    elif idmap_type == "idmap_nss":
        idmap = dsi.dsi_idmap_nss

    elif idmap_type == "idmap_rfc2307":
        idmap = dsi.dsi_idmap_rfc2307

    elif idmap_type == "idmap_rid":
        idmap = dsi.dsi_idmap_rid

    elif idmap_type == "idmap_tdb":
        idmap = dsi.dsi_idmap_tdb

    elif idmap_type == "idmap_tdb2":
        idmap = dsi.dsi_idmap_tdb2

    return idmap


def get_idmap(obj_type, idmap_type):
    obj_type = int(obj_type)

    dsi = get_directoryservice_idmap_object(obj_type)
    if not dsi:
        dsi = models.directoryservice_idmap()

    idmap = get_idmap_object(obj_type, idmap_type)
    if idmap_type == "idmap_ad":
        if not idmap:
            idmap = models.idmap_ad()
            idmap.save()

            dsi.dsi_idmap_ad = idmap
            dsi.save() 

    elif idmap_type == "idmap_autorid":
        if not idmap:
            idmap = models.idmap_autorid()
            idmap.save()

            dsi.dsi_idmap_autorid = idamp
            dsi.save() 

    elif idmap_type == "idmap_hash":
        if not idmap:
            idmap = models.idmap_hash()
            idmap.save()

            dsi.dsi_idmap_hash = idmap
            dsi.save() 

    elif idmap_type == "idmap_ldap":
        if not idmap:
            idmap = models.idmap_ldap()
            idmap.save()

            dsi.dsi_idmap_ldap = idmap
            dsi.save() 

    elif idmap_type == "idmap_nss":
        if not idmap:
            idmap = models.idmap_nss()
            idmap.save()

            dsi.dsi_idmap_nss = idmap
            dsi.save() 

    elif idmap_type == "idmap_rfc2307":
        if not idmap:
            idmap = models.idmap_rfc2307()
            idmap.save()

            dsi.dsi_idmap_rfc2307 = idmap
            dsi.save() 

    elif idmap_type == "idmap_rid":
        if not idmap:
            idmap = models.idmap_rid()
            idmap.save()

            dsi.dsi_idmap_rid = idmap
            dsi.save() 

    elif idmap_type == "idmap_tdb":
        if not idmap:
            idmap = models.idmap_tdb()
            idmap.save()

            dsi.dsi_idmap_tdb = idmap
            dsi.save() 

    elif idmap_type == "idmap_tdb2":
        if not idmap:
            idmap = models.idmap_tdb2()
            idmap.save()

            dsi.dsi_idmap_tdb2 = idmap
            dsi.save() 

    ds = get_ds_object(obj_type)
    if obj_type == models.DS_TYPE_ACTIVEDIRECTORY:
        ds.ad_idmap_backend_type = dsi

    elif obj_type == models.DS_TYPE_LDAP:
        ds.ldap_idmap_backend_type = dsi

    elif obj_type == models.DS_TYPE_NT4:
        ds.nt4_idmap_backend_type = dsi

    ds.save()

    data = {
        'idmap_type': idmap_type,
        'idmap_id': idmap.id
    }

    return data
