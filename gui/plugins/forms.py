# Copyright 2011 iXsystems, Inc.
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

from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI.common.forms import ModelForm
from freenasUI.middleware.notifier import notifier
from freenasUI.network.models import Alias, Interfaces
from freenasUI.plugins import models

log = logging.getLogger('plugins.forms')


def _clean_jail_ipv4address(jip):
    if (
        Alias.objects.filter(alias_v4address=jip).exists() or
        Interfaces.objects.filter(int_ipv4address=jip).exists()
    ):
        raise forms.ValidationError(_("This IP is already in use."))
    return jip


class PluginsForm(ModelForm):

    class Meta:
        model = models.Plugins
        exclude = (
            'plugin_pbiname', 'plugin_arch', 'plugin_version',
            'plugin_path', 'plugin_key', 'plugin_secret',
        )

    def __init__(self, *args, **kwargs):
        super(PluginsForm, self).__init__(*args, **kwargs)
        self.instance._original_plugin_enabled = self.instance.plugin_enabled

    def save(self):
        super(PluginsForm, self).save()
        notifier()._restart_plugins(
            jail=self.instance.plugin_jail,
            plugin=self.instance.plugin_name
        )

    def delete(self, request=None, events=None):
        super(PluginsForm, self).delete(request=request, events=events)
        if events is not None:
            events.append('reloadHttpd()')
