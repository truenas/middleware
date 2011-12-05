#+
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

from django.db import models
from django.utils.translation import ugettext_lazy as _

from freeadmin.models import Model, UserField, GroupField, PathField

class Plugins(Model):
    plugin_name = models.CharField(
        max_length=120,
        verbose_name=_("Plugin name"),
        help_text=_("Name of the plugin")
        )

    plugin_uname = models.CharField(
        max_length=120,
        verbose_name=_("Plugin uname"),
        help_text=_("UName of the plugin")
        )

    plugin_view = models.CharField(
        max_length=120,
        verbose_name=_("Plugin view"),
        help_text=_("Plugin view")
        )

    plugin_icon = models.CharField(
        max_length=120,
        verbose_name=_("Plugin icon"),
        help_text=_("Plugin icon")
        )

    plugin_enabled = models.BooleanField(
        verbose_name=_("Plugin enabled"),
        help_text=_("Plugin enabled"),
        default=False
        )

    plugin_ip = models.IPAddressField(
        max_length=120,
        verbose_name=_("Plugin IP address"),
        help_text=_("Plugin IP address")
        )

    plugin_port = models.IntegerField(
        max_length=120,
        verbose_name=_("Plugin TCP port"),
        help_text=_("Plugin TCP port"),
        )

    plugin_path = models.CharField(
        max_length=1024,
        verbose_name=_("Path to plugin"),
        help_text=_("Path to plugin")
        )

    class Meta:
        verbose_name = _(u"Plugins")
        verbose_name_plural = _(u"Plugins")

    class FreeAdmin:
        deletable = False
        icon_model = u"PluginsIcon"
