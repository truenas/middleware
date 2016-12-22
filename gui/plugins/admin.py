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

from collections import OrderedDict

from django.utils.html import escapejs
from django.utils.translation import ugettext as _

from freenasUI.api.resources import (
    AvailablePluginsResource,
    PluginsResourceMixin,
)
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.plugins import models

log = logging.getLogger('plugins.admin')


class PluginsFAdmin(BaseFreeAdmin):

    icon_model = u"PluginsIcon"

    resource_mixin = PluginsResourceMixin

    fields = (
        'plugin_name',
        'plugin_version',
    )


class AvailableFAdmin(BaseFreeAdmin):

    icon_model = u"PluginsIcon"

    resource = AvailablePluginsResource

    double_click = {
        'label': _('Install'),
        'field': '_install_url',
    }

    def get_actions(self):
        actions = OrderedDict()
        actions["Install"] = {
            'button_name': _("Install"),
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    editObject('%s', data._install_url, [mybtn,]);
                }
            }""" % (escapejs(_('Install plugin')), ),
        }
        return actions

    def get_column_name_extra(self):
        return {
            'formatter': """function(value, obj) {
                return '<img src="/plugins/plugin/available/icon/' + obj['id'] + '/" height="16" width="16"/> &nbsp; ' + value;
            }"""
        }

site.register(models.Plugins, PluginsFAdmin)
site.register(models.Available, AvailableFAdmin)
