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
import logging

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _

from freenasUI.api.resources import (
    KerberosRealmResourceMixin,
    KerberosKeytabResourceMixin,
    KerberosSettingsResourceMixin
)
from freenasUI.directoryservice import models
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site

log = logging.getLogger('directoryservice.admin')


class ActiveDirectoryFAdmin(BaseFreeAdmin):
    create_modelform = "ActiveDirectoryForm"
    deletable = False
    edit_modelform = "ActiveDirectoryForm"
    icon_object = "ActiveDirectoryIcon"
    icon_model = "ActiveDirectoryIcon"
    icon_add = "ActiveDirectoryIcon"
    icon_view = "ActiveDirectoryIcon"


class LDAPFAdmin(BaseFreeAdmin):
    create_modelform = "LDAPForm"
    deletable = False
    edit_modelform = "LDAPForm"
    icon_object = "LDAPIcon"
    icon_model = "LDAPIcon"
    icon_add = "LDAPIcon"
    icon_view = "LDAPIcon"


class NISFAdmin(BaseFreeAdmin):
    create_modelform = "NISForm"
    deletable = False
    edit_modelform = "NISForm"
    icon_object = "NISIcon"
    icon_model = "NISIcon"
    icon_add = "NISIcon"
    icon_view = "NISIcon"


class KerberosRealmFAdmin(BaseFreeAdmin):
    create_modelform = "KerberosRealmForm"
    edit_modelform = "KerberosRealmForm"
    icon_object = "KerberosRealmIcon"
    icon_model = "KerberosRealmIcon"
    icon_add = "KerberosRealmIcon"
    icon_view = "KerberosRealmIcon"

    resource_mixin = KerberosRealmResourceMixin


class KerberosKeytabFAdmin(BaseFreeAdmin):
    create_modelform = "KerberosKeytabCreateForm"
    edit_modelform = "KerberosKeytabEditForm"
    icon_object = "KerberosKeytabIcon"
    icon_model = "KerberosKeytabIcon"
    icon_add = "KerberosKeytabIcon"
    icon_view = "KerberosKeytabIcon"

    resource_mixin = KerberosKeytabResourceMixin

    def get_datagrid_columns(self):
        columns = []

        columns.append({
            'name': "keytab_name",
            'label': _("Name")
        })

        return columns

    def get_datagrid_context(self, request):
        context = super(KerberosKeytabFAdmin, self).get_datagrid_context(request)
        context.update({'add_url': reverse('directoryservice_kerberoskeytab_add')})
        return context


class KerberosSettingsFAdmin(BaseFreeAdmin):
    create_modelform = "KerberosSettingsForm"
    edit_modelform = "KerberosSettingsForm"
    icon_object = "SettingsIcon"
    icon_model = "SettingsIcon"
    icon_add = "SettingsIcon"
    icon_view = "SettingsIcon"
    deletable = False

    resource_mixin = KerberosSettingsResourceMixin

site.register(models.ActiveDirectory, ActiveDirectoryFAdmin)
site.register(models.LDAP, LDAPFAdmin)
site.register(models.NIS, NISFAdmin)
site.register(models.KerberosRealm, KerberosRealmFAdmin)
site.register(models.KerberosKeytab, KerberosKeytabFAdmin)
site.register(models.KerberosSettings, KerberosSettingsFAdmin)
