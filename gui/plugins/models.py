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

from freenasUI.common.system import is_mounted, mount, umount
from freenasUI.freeadmin.models import Model


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

    plugin_secret = models.ForeignKey(
        'services.RPCToken',
        on_delete=models.PROTECT,  # Do not allow foreign key to be deleted
        )

    class Meta:
        verbose_name = _(u"Plugins")
        verbose_name_plural = _(u"Plugins")

    class FreeAdmin:
        icon_model = u"PluginsIcon"

    def delete(self, *args, **kwargs):
        with transaction.commit_on_success():
            super(Plugins, self).delete(*args, **kwargs)
            self.plugin_secret.delete()


class NullMountPoint(Model):

    source = models.CharField(
        max_length=300,
        verbose_name=_("Source"),
        )

    destination = models.CharField(
        max_length=300,
        verbose_name=_("Destination"),
        )

    class Meta:
        verbose_name = _(u"Mount Point")
        verbose_name_plural = _(u"Mount Points")

    def __unicode__(self):
        return self.source

    def delete(self, *args, **kwargs):
        if self.mounted:
            self.umount()
        super(NullMountPoint, self).delete(*args, **kwargs)

    @property
    def mounted(self):
        return is_mounted(device=self.source, path=self.destination_jail)

    def __get_jail(self):
        from freenasUI.services.models import PluginsJail
        if not hasattr(self, "__jail"):
            self.__jail = PluginsJail.objects.order_by('-id')[0]
        return self.__jail

    @property
    def destination_jail(self):
        jail = self.__get_jail()
        return u"%s/%s%s" % (jail.jail_path, jail.jail_name, self.destination)

    def mount(self):
        mount(self.source, self.destination_jail, fstype="nullfs")
        return self.mounted

    def umount(self):
        umount(self.destination_jail)
        return not self.mounted
