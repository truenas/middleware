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
import middlewared.logger

from collections import OrderedDict

from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.utils.html import escapejs

from freenasUI.api.resources import (
    JailsResourceMixin, JailTemplateResourceMixin, JailMountPointResourceMixin
)
from freenasUI.freeadmin.site import site
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.jails import models

log = middlewared.logger.Logger('jails.admin')


class JailsFAdmin(BaseFreeAdmin):

    create_modelform = "JailCreateForm"
    edit_modelform = "JailsEditForm"
    icon_object = u"ServicesIcon"
    icon_model = u"ServicesIcon"
    icon_add = u"ServicesIcon"
    icon_view = u"ServicesIcon"

    resource_mixin = JailsResourceMixin
    exclude_fields = [
        'id',
        'jail_ipv4',
        'jail_alias_ipv4',
        'jail_bridge_ipv4',
        'jail_alias_bridge_ipv4',
        'jail_defaultrouter_ipv4',
        'jail_ipv6',
        'jail_alias_ipv6',
        'jail_bridge_ipv6',
        'jail_alias_bridge_ipv6',
        'jail_defaultrouter_ipv6',
        'jail_vnet',
        'jail_nat'
    ]

    advanced_fields = [
        'jail_type',
        'jail_ipv4_dhcp',
        'jail_ipv4',
        'jail_ipv4_netmask',
        'jail_alias_ipv4',
        'jail_bridge_ipv4',
        'jail_bridge_ipv4_netmask',
        'jail_alias_bridge_ipv4',
        'jail_defaultrouter_ipv4',
        'jail_ipv6_autoconf',
        'jail_ipv6',
        'jail_ipv6_prefix',
        'jail_alias_ipv6',
        'jail_bridge_ipv6',
        'jail_bridge_ipv6_prefix',
        'jail_alias_bridge_ipv6',
        'jail_defaultrouter_ipv6',
        'jail_mac',
        'jail_iface',
        'jail_flags',
        'jail_autostart',
        'jail_status',
        'jail_vnet',
        'jail_nat'
    ]

    def get_datagrid_columns(self):
        columns = []

        columns.append({
            'name': 'jail_host',
            'label': _('Jail'),
        })

        columns.append({
            'name': 'jail_ipv4',
            'label': _('IPv4 Address'),
        })

        #
        # XXX Add IPv6 address when IPv6 works ;-)
        #

        columns.append({
            'name': 'jail_autostart',
            'label': _('Autostart'),
        })

        columns.append({
            'name': 'jail_status',
            'label': _('Status'),
        })

        columns.append({
            'name': 'jail_type',
            'label': _('Type'),
        })

        return columns

    def _action_builder(
        self, name, label=None, url=None, func="editObject", icon=None,
        show=None
    ):

        if url is None:
            url = "_%s_url" % (name, )

        if icon is None:
            icon = name
        if icon is not False:
            icon = '<img src="%simages/ui/buttons/%s.png" width="18px" height="18px">' % (
                settings.STATIC_URL,
                icon,
            )
        else:
            icon = label

        on_select_after = """function(evt, actionName, action) {
                for(var i=0;i < evt.rows.length;i++) {
                    var row = evt.rows[i];

                    if (row.data.jail_isplugin) {
                        if (actionName == 'delete') {
                            query(".grid" + actionName).forEach(function(item, idx) {
                                domStyle.set(item, "display", "none");
                            });
                        }
                    }

                    if (row.data.jail_type != 'pluginjail' || row.data.jail_status == 'Stopped') {
                        if (actionName == 'plugins') {
                            query(".grid" + actionName).forEach(function(item, idx) {
                                domStyle.set(item, "display", "none");
                            });
                        }
                    }

                    if (row.data.jail_status == 'Running') {
                        if (actionName == 'start') {
                            query(".grid" + actionName).forEach(function(item, idx) {
                                domStyle.set(item, "display", "none");
                            });
                        }
                        break;

                    } else if (row.data.jail_status == 'Stopped') {
                        if (actionName == 'stop') {
                            query(".grid" + actionName).forEach(function(item, idx) {
                                domStyle.set(item, "display", "none");
                            });
                        }
                        break;
                    }
                }
            }"""

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
            'button_name': icon,
            'tooltip': label,
            'on_select_after': on_select_after,
            'on_click': on_click,
        }

        return data

    def get_actions(self):
        actions = OrderedDict()

        actions['edit'] = self._action_builder(
            'edit', icon='jail_edit', label=_("Edit Jail")
        )
        actions['storage'] = self._action_builder(
            'jail_storage_add', label=_("Add Storage")
        )
        actions['plugins'] = self._action_builder(
            'upload', icon='plugin_install', label=_("Upload Plugin")
        )
        actions['start'] = self._action_builder('jail_start', label=_("Start"))
        actions['stop'] = self._action_builder('jail_stop', label=_("Stop"))
        actions['restart'] = self._action_builder(
            'jail_restart', label=_("Restart")
        )

        shell_button = '<img src="%simages/ui/buttons/shell.png" width="18px" height="18px">' % settings.STATIC_URL

        actions['shell'] = {
            'button_name': shell_button,
            'tooltip': 'Shell',
            'on_select_after': """function(evt, actionName, action) {
                for(var i=0;i < evt.rows.length;i++) {
                    var row = evt.rows[i];

                    if (row.data.jail_status == 'Stopped') {
                        query(".grid" + actionName).forEach(function(item, idx) {
                            domStyle.set(item, "display", "none");
                        });
                        break;
                    }
                }
            }""",
            'on_click': """function() {
                var mybtn = this;
                require(["freeadmin/WebShell"], function(WebShell) {
                    for (var i in grid.selection) {
                        var data = grid.row(i).data;
                        var shell = "/bin/csh";
                        if (data.jail_os == 'Linux') {
                            shell = '/bin/sh'
                        }
                        _webshell = new WebShell({jid: data.jail_jid, shell: shell});
                    }
                });
            }"""
        }
        actions['delete'] = self._action_builder(
            'jail_delete',
            label=_("Delete"),
            func='editScaryObject'
        )

        return actions


class JailsConfigurationFAdmin(BaseFreeAdmin):

    deletable = False
    resource_name = 'jails/configuration'


class JailTemplateFAdmin(BaseFreeAdmin):

    create_modelform = "JailTemplateCreateForm"
    edit_modelform = "JailTemplateEditForm"
    icon_object = u"ServicesIcon"
    icon_model = u"ServicesIcon"
    icon_add = u"ServicesIcon"
    icon_view = u"ServicesIcon"

    resource_mixin = JailTemplateResourceMixin
    resource_name = 'jails/templates'

    def get_datagrid_columns(self):
        columns = []

        columns.append({
            'name': 'jt_name',
            'label': _('Name'),
            'sortable': False
        })

        columns.append({
            'name': 'jt_url',
            'label': _('URL'),
            'sortable': False
        })

        columns.append({
            'name': 'jt_instances',
            'label': _('Instances'),
            'sortable': False
        })

        return columns

    def get_actions(self):
        actions = super(JailTemplateFAdmin, self).get_actions()

        on_select_after = """
            function(evt, actionName, action) {
                for (var i=0;i < evt.rows.length;i++) {
                    var row = evt.rows[i];
                    if ((row.data.jt_instances > 0 || \
                        row.data.jt_readonly) \
                        && actionName == 'Delete') {
                        query(".grid" + actionName).forEach(
                            function(item, idx) {
                            domStyle.set(item, "display", "none");
                        });
                    }
                }
            }
        """
        actions['Edit']['on_select_after'] = on_select_after
        actions['Delete']['on_select_after'] = on_select_after

        return actions

    def get_datagrid_context(self, request):
        context = super(JailTemplateFAdmin, self).get_datagrid_context(request)
        context.update({'add_url': reverse('jail_template_create')})
        return context


class JailMountPointFAdmin(BaseFreeAdmin):

    icon_model = u"MountPointIcon"
    icon_object = u"MountPointIcon"
    icon_add = u"AddMountPointIcon"
    icon_view = u"ViewMountPointIcon"

    resource_mixin = JailMountPointResourceMixin
    resource_name = 'jails/mountpoints'

    def get_datagrid_columns(self):
        columns = super(JailMountPointFAdmin, self).get_datagrid_columns()
        columns.insert(3, {
            'name': 'mounted',
            'label': _('Mounted?'),
            'sortable': False,
        })
        return columns

site.register(models.Jails, JailsFAdmin)
site.register(models.JailsConfiguration, JailsConfigurationFAdmin)
site.register(models.JailTemplate, JailTemplateFAdmin)
site.register(models.JailMountPoint, JailMountPointFAdmin)
