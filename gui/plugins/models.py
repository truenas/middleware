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

from django.db import models, transaction
from django.utils.translation import ugettext_lazy as _

from freenasUI.freeadmin.models import Model
from freenasUI.jails.models import Jails
from freenasUI.middleware.notifier import notifier

PLUGINS_INDEX = 'http://www.appcafe.org/freenas/json'


class Plugins(Model):
    plugin_name = models.CharField(
        max_length=120,
        verbose_name=_("Plugin name"),
        help_text=_("Name of the plugin")
        )

    plugin_pbiname = models.CharField(
        max_length=120,
        verbose_name=_("Plugin info name"),
        help_text=_("Info name of the plugin")
        )

    plugin_version = models.CharField(
        max_length=120,
        verbose_name=_("Plugin version"),
        help_text=_("Version of the plugin")
        )

    plugin_api_version = models.CharField(
        max_length=20,
        default="1",
        verbose_name=_("Plugin API version"),
        )

    plugin_arch = models.CharField(
        max_length=120,
        verbose_name=_("Plugin architecture"),
        help_text=_("Plugin architecture")
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
        verbose_name=_("Plugin archive path"),
        help_text=_("Path where the plugins are saved after installation")
        )

    plugin_jail = models.CharField(
        max_length=120,
        verbose_name=_("Plugin jail name"),
        help_text=_("Jail where the plugin is installed")
        )

    plugin_secret = models.ForeignKey(
        'services.RPCToken',
        on_delete=models.PROTECT,  # Do not allow foreign key to be deleted
        )

    class Meta:
        verbose_name = _(u"Plugin")
        verbose_name_plural = _(u"Plugins")

    def delete(self, *args, **kwargs):
        qs = Plugins.objects.filter(plugin_jail=self.plugin_jail).exclude(
            id__exact=self.id
        )
        with transaction.commit_on_success():
            notifier()._stop_plugins(self.plugin_name)
            if qs.count() > 0:
                notifier().delete_pbi(self)
            else:
                jail = Jails.objects.get(jail_host=self.plugin_jail)
                jail.delete()
            super(Plugins, self).delete(*args, **kwargs)
            self.plugin_secret.delete()


class Available(models.Model):

    name = models.CharField(
        verbose_name=_("Name"),
        max_length=200,
    )

    description = models.CharField(
        verbose_name=_("Description"),
        max_length=200,
    )

    version = models.CharField(
        verbose_name=_("Version"),
        max_length=200,
    )

    class Meta:
        abstract = True


class Configuration(Model):

    collectionurl = models.CharField(
        verbose_name=_("Collection URL"),
        max_length=255,
        help_text=_("URL for the plugins index"),
        blank=True,
    )

    class FreeAdmin:
        deletable = False

    class Meta:
        verbose_name = _("Configuration")
