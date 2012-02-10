#+
# Copyright 2010 iXsystems, Inc.
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
import re

from django.utils.translation import ugettext_lazy as _
from django.db import models

from freenasUI import choices
from freenasUI.contrib.IPAddressField import IPAddressField, IP4AddressField,\
                                             IP6AddressField, IPNetworkField
from freeadmin.models import Model
from freenasUI.middleware.notifier import notifier

## Network|Global Configuration
class GlobalConfiguration(Model):
    gc_hostname = models.CharField(
            max_length=120,
            verbose_name=_("Hostname")
            )
    gc_domain = models.CharField(
            max_length=120,
            verbose_name=_("Domain")
            )
    gc_ipv4gateway = IP4AddressField(
            blank=True,
            default='',
            verbose_name=_("IPv4 Default Gateway"),
            )
    gc_ipv6gateway = IP6AddressField(
            blank=True,
            default='',
            verbose_name=_("IPv6 Default Gateway"),
            )
    gc_nameserver1 = IPAddressField(
            blank=True,
            default='',
            verbose_name=_("Nameserver 1")
            )
    gc_nameserver2 = IPAddressField(
            default='',
            blank=True,
            verbose_name=_("Nameserver 2")
            )
    gc_nameserver3 = IPAddressField(
            default='',
            blank=True,
            verbose_name=_("Nameserver 3")
            )
    def __unicode__(self):
            return u'%s' % self.id
    class Meta:
        verbose_name = _("Global Configuration")
        verbose_name_plural = _("Global Configuration")
    class FreeAdmin:
        deletable = False

## Network|Interface Management
class Interfaces(Model):
    int_interface = models.CharField(
            max_length=300,
            blank=False,
            verbose_name=_("NIC"),
            help_text=_("Pick your NIC")
            )
    int_name = models.CharField(
            max_length="120",
            verbose_name=_("Interface Name"),
            help_text=_("Name your NIC.")
            )
    int_dhcp = models.BooleanField(
            verbose_name=_("DHCP"),
            help_text=_("When enabled, use DHCP to obtain IPv4 address as well as default router, etc.")
            )
    int_ipv4address = IPAddressField(
            verbose_name=_("IPv4 Address"),
            blank=True,
            default='',
            )
    int_v4netmaskbit = models.CharField(
            max_length=3,
            choices=choices.v4NetmaskBitList,
            blank=True,
            default='',
            verbose_name=_("IPv4 Netmask"),
            help_text=""
            )
    int_ipv6auto = models.BooleanField(
            verbose_name=_("Auto configure IPv6"),
            help_text=_("When enabled, automatically configurate IPv6 address via rtsol(8).")
            )
    int_ipv6address = IPAddressField(
            verbose_name=_("IPv6 Address"),
            blank=True,
            default='',
            )
    int_v6netmaskbit = models.CharField(
            max_length=4,
            choices=choices.v6NetmaskBitList,
            blank=True,
            default='',
            verbose_name=_("IPv6 Prefix Length"),
            help_text=""
            )
    int_options = models.CharField(
            max_length=120,
            verbose_name=_("Options"),
            blank=True
            )

    def __unicode__(self):
            return u'%s' % self.int_name
    def __init__(self, *args, **kwargs):
        super(Interfaces, self).__init__(*args, **kwargs)
        self._original_int_options = self.int_options
    def delete(self):
        for lagg in self.lagginterface_set.all():
            lagg.delete()
        super(Interfaces, self).delete()
        notifier().stop("netif")
        notifier().start("network")
    def save(self, *args, **kwargs):
        super(Interfaces, self).save(*args, **kwargs)
        if self._original_int_options != self.int_options and \
                re.search(r'mtu \d+', self._original_int_options) and \
                self.int_options.find("mtu") == -1:
            notifier().interface_mtu(self.int_interface, "1500")
    class Meta:
        verbose_name = _("Interface")
        verbose_name_plural = _("Interfaces")
    class FreeAdmin:
        create_modelform = "InterfacesForm"
        edit_modelform = "InterfacesEditForm"
        icon_object = u"InterfacesIcon"
        icon_model = u"InterfacesIcon"
        icon_add = u"AddInterfaceIcon"
        icon_view = u"ViewAllInterfacesIcon"
        inlines = [
            {
                'form': 'AliasForm',
                'prefix': 'alias_set'
            },
        ]


class Alias(Model):
    alias_interface = models.ForeignKey(
            Interfaces,
            verbose_name=_("Interface")
            )
    alias_v4address = IP4AddressField(
            verbose_name=_("IPv4 Address"),
            default='',
            blank=True,
            )
    alias_v4netmaskbit = models.CharField(
            max_length=3,
            choices=choices.v4NetmaskBitList,
            default='',
            blank=True,
            verbose_name=_("IPv4 Netmask"),
            help_text=""
            )
    alias_v6address = IP6AddressField(
            verbose_name=_("IPv6 Address"),
            default='',
            blank=True,
            )
    alias_v6netmaskbit = models.CharField(
            max_length=3,
            choices=choices.v6NetmaskBitList,
            default='',
            blank=True,
            verbose_name=_("IPv6 Prefix Length"),
            help_text=""
            )

    def __unicode__(self):
            return u'%s:%s' % (self.alias_interface.int_name, self.alias_v4address)
    def delete(self):
        super(Alias, self).delete()
        notifier().stop("netif")
        notifier().start("network")
    class Meta:
        verbose_name = _("Alias")
        verbose_name_plural = _("Aliases")
    class FreeAdmin:
        pass
        #create_modelform = "InterfacesForm"
        #edit_modelform = "InterfacesEditForm"

## Network|Interface Management|VLAN
class VLAN(Model):
    vlan_vint = models.CharField(
            max_length=120,
            verbose_name=_("Virtual Interface"),
            help_text=_("Interface names must be vlanXX where XX is a number. Example: vlan0.")
            )
    vlan_pint = models.CharField(
            max_length=300,
            blank=False,
            verbose_name=_("Physical Interface")
            )
    vlan_tag = models.PositiveIntegerField(
            verbose_name=_("VLAN Tag")
            )
    vlan_description = models.CharField(
            max_length=120,
            verbose_name=_("Description"),
            blank=True
            )

    def __unicode__(self):
        return self.vlan_vint

    def delete(self):
        vint = self.vlan_vint
        super(VLAN, self).delete()
        Interfaces.objects.filter(int_interface=vint).delete()
        notifier().iface_destroy(vint)

    class Meta:
        verbose_name = _("VLAN")
        verbose_name_plural = _("VLANs")

    class FreeAdmin:
        icon_object = u"VLANIcon"
        icon_model = u"VLANIcon"
        icon_add = u"AddVLANIcon"
        icon_view = u"ViewAllVLANsIcon"


# LAGG interface to protocol type map.
# This model amends Interface to provide information regarding to a lagg interface
class LAGGInterface(Model):
    # A corresponding interface is created as "laggX"
    lagg_interface = models.ForeignKey(
            Interfaces,
            unique = True,
            verbose_name=_("Interface")
            )
    lagg_protocol = models.CharField(
            max_length=120,
            verbose_name=_("Protocol Type"),
            choices=choices.LAGGType,
            )
    def __unicode__(self):
        interface_list = LAGGInterfaceMembers.objects.filter(lagg_interfacegroup = self.id)
        if interface_list != None:
            interfaces = ', '.join([int.lagg_physnic for int in interface_list])
        else:
            interfaces = 'None'
        return "%s (%s: %s)" % (self.lagg_interface, self.lagg_protocol, interfaces)

    def delete(self):
        super(LAGGInterface, self).delete()
        notifier().iface_destroy(self.lagg_interface.int_interface)

    class FreeAdmin:
        icon_object = u"VLANIcon"
        icon_model = u"VLANIcon"
        icon_add = u"AddVLANIcon"
        icon_view = u"ViewAllVLANsIcon"

# Physical interfaces list inside one LAGG group
class LAGGInterfaceMembers(Model):
    lagg_interfacegroup = models.ForeignKey(
            LAGGInterface,
            verbose_name=_("LAGG Interface group")
            )
    lagg_ordernum = models.IntegerField(
            verbose_name=_("LAGG Priority Number"),
            )
    lagg_physnic = models.CharField(
            max_length=120,
            unique = True,
            verbose_name=_("Physical NIC")
            )
    lagg_deviceoptions = models.CharField(
            max_length=120,
            verbose_name=_("Options")
            )
    def __unicode__(self):
        return self.lagg_physnic

    def delete(self):
        import os
        os.system("ifconfig %s -laggport %s" % (self.lagg_interfacegroup.lagg_interface.int_interface, self.lagg_physnic))
        super(LAGGInterfaceMembers, self).delete()

    class Meta:
        verbose_name = _("Link Aggregation")
        verbose_name_plural = _("Link Aggregations")

    class FreeAdmin:
        icon_object = u"LAGGIcon"
        icon_model = u"LAGGIcon"

class StaticRoute(Model):
    sr_destination = models.CharField(
            max_length=120,
            verbose_name=_("Destination network")
            )
    sr_gateway = IP4AddressField(
            max_length=120,
            verbose_name=_("Gateway")
            )
    sr_description = models.CharField(
            max_length=120,
            verbose_name=_("Description"),
            blank=True
            )

    class Meta:
        verbose_name = _("Static Route")
        verbose_name_plural = _("Static Routes")

    class FreeAdmin:
        icon_object = u"StaticRouteIcon"
        icon_model = u"StaticRouteIcon"
        icon_add = u"AddStaticRouteIcon"
        icon_view = u"ViewAllStaticRoutesIcon"

    def __unicode__(self):
        return self.sr_destination

    def save(self, *args, **kwargs):
        super(StaticRoute, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        super(StaticRoute, self).delete(*args, **kwargs)
        notifier().staticroute_delete(self)
