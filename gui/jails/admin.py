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
from django.utils.translation import ugettext as _

from freenasUI.freeadmin.site import site
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.api.resources import JailsResource

from freenasUI.jails import models

class JailsFAdmin(BaseFreeAdmin):

    create_modelform = "JailsForm"
    edit_modelform = "JailsEditForm"
    icon_object = u"ServicesIcon"
    icon_model = u"ServicesIcon"
    icon_add = u"ServicesIcon"
    icon_view = u"ServicesIcon"

    resource = JailsResource

    def get_datagrid_columns(self):
        columns = []

        columns.append({
            'name': 'jail_host',
            'label': _('Jail'),
            'sortable': True,
        })

        columns.append({
            'name': 'jail_ip',
            'label': _('IP/Netmask'),
            'sortable': True,
        })

        columns.append({
            'name': 'jail_autostart',
            'label': _('Autostart'),
            'sortable': True,
        })

        columns.append({
            'name': 'jail_status',
            'label': _('Status'),
            'sortable': True,
        })

        columns.append({
            'name': 'jail_type',
            'label': _('Type'),
            'sortable': True,
        })

        return columns


site.register(models.Jails, JailsFAdmin)
