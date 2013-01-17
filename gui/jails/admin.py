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
from django.conf import settings
from django.utils.translation import ugettext as _
from django.utils.html import escapejs

from freenasUI.freeadmin.site import site
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.api.resources import JailsResource
from freenasUI.jails import models

from collections import OrderedDict

import logging

log = logging.getLogger('jails.admin')

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

    def _action_builder(self, name, label=None, url=None,
        func="editObject", icon=None, show=None):

        if url is None:
            url = "_%s_url" % (name, )

        if icon is None:
            icon = name

        on_select_after = """function(evt, actionName, action) {
                for(var i=0;i < evt.rows.length;i++) {
                    var row = evt.rows[i];
                    if((%(hide)s) || (%(hide_fs)s) || (%(hide_enc)s) || (%(hide_hasenc)s)) {
                        query(".grid" + actionName).forEach(function(item, idx) {
                            domStyle.set(item, "display", "none");
                        });
                        break;
                    }
                }
            }""" % {
            'hide': "false",
            'hide_fs': "false",
            'hide_enc': "false",
            'hide_hasenc': "false",
            }

        on_click = """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    %(func)s('%(label)s', data.%(url)s, [mybtn,]);
                }
            }""" % {
                'func': func,
                'label': escapejs(label),
                'url': url,
                }

        data = {
            'button_name': '<img src="%simages/ui/buttons/%s.png" width="18px" height="18px">' % (
                settings.STATIC_URL,
                icon,
            ),
            'tooltip': label,
            'on_select_after': on_select_after,
            'on_click': on_click,
        }

        return data

    def get_actions(self):
        
        actions = OrderedDict()

        actions['auto'] = self._action_builder('jail_auto', label=_("Autostart"))
        actions['checkup'] = self._action_builder('jail_checkup', label=_("Checkup"))
        actions['detiuls'] = self._action_builder('jail_details', label=_("Details"))
        actions['export'] = self._action_builder('jail_export', label=_("Export"))
        actions['import'] = self._action_builder('jail_import', label=_("Import"))
        actions['options'] = self._action_builder('jail_options', label=_("Options"))
        actions['pkgs'] = self._action_builder('jail_pkgs', label=_("Packages"))
        actions['pbis'] = self._action_builder('jail_pbis', label=_("PBI's"))
        actions['start'] = self._action_builder('jail_start', label=_("Start"))
        actions['stop'] = self._action_builder('jail_stop', label=_("Stop"))

        actions['zfsmksnap'] = self._action_builder('jail_zfsmksnap',
            label=_("ZFS Snapshot"))
        actions['zfslistclone'] = self._action_builder('jail_zfslistclone',
            label=_("ZFS Clones"))
        actions['zfslistsnap'] = self._action_builder('jail_zfslistsnap',
            label=_("ZFS Snapshots"))
        actions['zfsclonesnap'] = self._action_builder('jail_zfsclonesnap',
            label=_("ZFS Clone Snapshot"))
        actions['zfscronsnap'] = self._action_builder('jail_zfscronsnap',
            label=_("ZFS Cron Snapshot"))
        actions['zfrevertsnap'] = self._action_builder('jail_zfsrevertsnap',
            label=_("ZFS Revert Snapshot"))
        actions['zfsrmclonesnap'] = self._action_builder('jail_zfsrmclonesnap',
            label=_("ZFS Remove Clone Snapshot"))
        actions['zfsrmsnap'] = self._action_builder('jail_zfsrmsnap',
            label=_("ZFS Remove Snapshot"))

        return actions


site.register(models.Jails, JailsFAdmin)
