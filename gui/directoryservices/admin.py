#+
# Copyright 2013 iXsystems, Inc.
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

from django.utils.translation import ugettext as _

from freenasUI.api.resources import DirectoryServicesResourceMixin

from freenasUI.directoryservices import models
from freenasUI.directoryservices.directoryservice import DirectoryService
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site

log = logging.getLogger('directoryservices.admin')

class DirectoryServicesFAdmin(BaseFreeAdmin):

    create_modelform = "DirectoryServiceCreateForm"
    edit_modelform = "DirectoryServiceEditForm"
    icon_object = u"SettingsIcon"
    icon_model = u"SettingsIcon"
    icon_add = u"SettingsIcon"
    icon_view = u"SettingsIcon"

    resource_mixin = DirectoryServicesResourceMixin
    def get_datagrid_columns(self):
        columns = []

        columns.append({
            'name': 'ds_name',
            'label': _('Name'),
            'sortable': False
        })

        columns.append({
            'name': 'ds_type',
            'label': _('Type'),
            'sortable': False
        })

        columns.append({
            'name': 'ds_enable',
            'label': _('Enabled'),
            'sortable': False
        })

        return columns


site.register(DirectoryService, DirectoryServicesFAdmin)
