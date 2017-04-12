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


def get_ds_object(obj_type, obj_id):
    ds_obj = None

    if obj_type == models.DS_TYPE_ACTIVEDIRECTORY:
        ds_obj = models.ActiveDirectory.objects.filter(pk=obj_id)[0]

    elif obj_type == models.DS_TYPE_LDAP:
        ds_obj = models.LDAP.objects.filter(pk=obj_id)[0]

    elif obj_type == models.DS_TYPE_NT4:
        ds_obj = models.NT4.objects.filter(pk=obj_id)[0]

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

    get_ds_object(obj_type)
    dsi = get_ds_object_backend_type(obj_type)

    return dsi


def get_idmap_object(obj_type, obj_id, idmap_type):
    obj_type = int(obj_type)

    if idmap_type == "ad":
        idmap = models.idmap_ad.objects.get(
            idmap_ds_type=obj_type,
            idmap_ds_id=obj_id
        )

    elif idmap_type == "adex":
        idmap = models.idmap_adex.objects.get(
            idmap_ds_type=obj_type,
            idmap_ds_id=obj_id
        )

    elif idmap_type == "autorid":
        idmap = models.idmap_autorid.objects.get(
            idmap_ds_type=obj_type,
            idmap_ds_id=obj_id
        )

    elif idmap_type == "fruit":
        idmap = models.idmap_fruit.objects.get(
            idmap_ds_type=obj_type,
            idmap_ds_id=obj_id
        )

    elif idmap_type == "hash":
        idmap = models.idmap_hash.objects.get(
            idmap_ds_type=obj_type,
            idmap_ds_id=obj_id
        )

    elif idmap_type == "ldap":
        idmap = models.idmap_ldap.objects.get(
            idmap_ds_type=obj_type,
            idmap_ds_id=obj_id
        )

    elif idmap_type == "nss":
        idmap = models.idmap_nss.objects.get(
            idmap_ds_type=obj_type,
            idmap_ds_id=obj_id
        )

    elif idmap_type == "rfc2307":
        idmap = models.idmap_rfc2307.objects.get(
            idmap_ds_type=obj_type,
            idmap_ds_id=obj_id
        )

    elif idmap_type == "rid":
        idmap = models.idmap_rid.objects.get(
            idmap_ds_type=obj_type,
            idmap_ds_id=obj_id
        )

    elif idmap_type == "tdb":
        idmap = models.idmap_tdb.objects.get(
            idmap_ds_type=obj_type,
            idmap_ds_id=obj_id
        )

    elif idmap_type == "tdb2":
        idmap = models.idmap_tdb2.objects.get(
            idmap_ds_type=obj_type,
            idmap_ds_id=obj_id
        )

    return idmap


def get_idmap(obj_type, obj_id, idmap_type):
    obj_type = int(obj_type)

    ds = get_ds_object(obj_type, obj_id)

    try:
        idmap = get_idmap_object(obj_type, obj_id, idmap_type)
    except:
        idmap = None

    if idmap_type == "ad":
        if not idmap:
            idmap = models.idmap_ad()

    elif idmap_type == "adex":
        if not idmap:
            idmap = models.idmap_adex()

    elif idmap_type == "autorid":
        if not idmap:
            idmap = models.idmap_autorid()

    elif idmap_type == "fruit":
        if not idmap:
            idmap = models.idmap_fruit()

    elif idmap_type == "hash":
        if not idmap:
            idmap = models.idmap_hash()

    elif idmap_type == "ldap":
        if not idmap:
            idmap = models.idmap_ldap()

    elif idmap_type == "nss":
        if not idmap:
            idmap = models.idmap_nss()

    elif idmap_type == "rfc2307":
        if not idmap:
            idmap = models.idmap_rfc2307()

    elif idmap_type == "rid":
        if not idmap:
            idmap = models.idmap_rid()

    elif idmap_type == "tdb":
        if not idmap:
            idmap = models.idmap_tdb()

    elif idmap_type == "tdb2":
        if not idmap:
            idmap = models.idmap_tdb2()

    idmap.idmap_ds_type = ds.ds_type
    idmap.idmap_ds_id = ds.id
    idmap.save()

    data = {
        'idmap_type': idmap_type,
        'idmap_id': idmap.id
    }

    return data
