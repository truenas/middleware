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
import random
import re
import string

from django.core.validators import RegexValidator
from django.db import models, transaction
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.contrib.IPAddressField import (IPAddressField, IP4AddressField,
    IP6AddressField)
from freenasUI.freeadmin.models import Model, NewModel, ConfigQuerySet, NewManager
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.services.models import CIFS
from fnutils.query import wrap
from fnutils import force_none


class GlobalConfiguration(NewModel):
    gc_hostname = models.CharField(
        max_length=120,
        verbose_name=_("Hostname"),
        default='nas',
        validators=[RegexValidator(
            regex=r'^[a-zA-Z\.\-\_0-9]+$',
        )],
    )
    gc_hostname_b = models.CharField(
        max_length=120,
        verbose_name=_("Hostname"),
        validators=[RegexValidator(
            regex=r'^[a-zA-Z\.\-\_0-9]+$',
        )],
        blank=True,
        null=True,
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
    gc_httpproxy = models.CharField(
        verbose_name=_('HTTP Proxy'),
        blank=True,
        max_length=255,
    )
    gc_netwait_enabled = models.BooleanField(
        verbose_name=_("Enable netwait feature"),
        help_text=_("If enabled, delays the start of network-reliant services "
            "until interface is up and ICMP packets to a destination defined "
            "in netwait ip list are flowing.  Link state is examined first, "
            "followed by \"pinging\" an IP address to verify network "
            "usability.  If no destination can be reached or timeouts are "
            "exceeded, network services are started anyway with no guarantee "
            "that the network is usable."),
        default=False,
        )
    gc_netwait_ip = models.CharField(
        verbose_name=_("Netwait IP list"),
        help_text=_("Space-delimited list of IP addresses to ping(8). If "
            "multiple IP addresses are specified, each will be tried until "
            "one is successful or the list is exhausted. If it is empty the "
            "default gateway will be used."),
        blank=True,
        max_length=300,
        )

    def __init__(self, *args, **kwargs):
        super(GlobalConfiguration, self).__init__(*args, **kwargs)
        self._orig_gc_hostname = self.__dict__.get('gc_hostname')
        self._orig_gc_ipv4gateway = self.__dict__.get('gc_ipv4gateway')
        self._orig_gc_ipv6gateway = self.__dict__.get('gc_ipv6gateway')

    def __unicode__(self):
        return u'%s' % self.id

    def get_hostname(self):
        _n = notifier()
        if not _n.is_freenas():
            if _n.failover_node() == 'B':
                return self.gc_hostname_b
            else:
                return self.gc_hostname
        else:
            return self.gc_hostname

    def save(self, *args, **kwargs):
        # See #3437
        if self._orig_gc_hostname != self.gc_hostname:
            try:
                cifs = CIFS.objects.order_by('-id')[0]
                cifs.cifs_srv_netbiosname = self.gc_hostname
                cifs.save()
            except:
                pass
        return super(GlobalConfiguration, self).save(*args, **kwargs)

    class Meta:
        verbose_name = _("Global Configuration")
        verbose_name_plural = _("Global Configuration")

    objects = NewManager(qs_class=ConfigQuerySet)

    class Middleware:
        configstore = True

    class FreeAdmin:
        deletable = False

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        network = wrap(dispatcher.call_sync('network.config.get_global_config'))
        general = wrap(dispatcher.call_sync('system.general.get_config'))

        return cls(**dict(
            id=1,
            gc_hostname=general['hostname'],
            gc_ipv4gateway=network['gateway.ipv4'],
            gc_ipv6gateway=network['gateway.ipv6'],
            gc_nameserver1=network.get('dns.addresses.0'),
            gc_nameserver2=network.get('dns.addresses.1'),
            gc_nameserver3=network.get('dns.addresses.2'),
            gc_netwait_enabled=network.get('netwait.enabled'),
            gc_netwait_ip=' '.join(network.get('netwait.addresses', []))
        ))

    def _save(self, *args, **kwargs):
        dns_servers = []
        for i in ("gc_nameserver1", "gc_nameserver2", "gc_nameserver3"):
            v = getattr(self, i)
            if v:
                dns_servers.append(v)

        self._save_task_call('system.general.configure', {
            'hostname': self.gc_hostname
        })

        self._save_task_call('network.configure', {
            'gateway': {
                'ipv4': force_none(self.gc_ipv4gateway),
                'ipv6': force_none(self.gc_ipv6gateway)
            },
            'dns': {
                'addresses': dns_servers
            },
            'netwait': {
                'enable': self.gc_netwait_enabled,
                'addresses': self.gc_netwait_ip.split()
            }
        })


class Interfaces(NewModel):
    id = models.CharField(
        max_length=120,
        primary_key=True
    )

    int_interface = models.CharField(
        max_length=300,
        blank=False,
        verbose_name=_("NIC"),
        help_text=_("Pick your NIC")
    )

    int_name = models.CharField(
            max_length="120",
            verbose_name=_("Interface Name"),
            help_text=_("Name your NIC."),
            blank=True
    )

    int_dhcp = models.BooleanField(
        verbose_name=_("DHCP"),
        default=False,
        help_text=_("When enabled, use DHCP to obtain IPv4 address as well"
            " as default router, etc.")
    )

    int_ipv6auto = models.BooleanField(
        verbose_name=_("Auto configure IPv6"),
        default=False,
        help_text=_(
            "When enabled, automatically configurate IPv6 address "
            "via rtsol(8)."
        ),
    )

    int_disableipv6 = models.BooleanField(
        verbose_name=_("Disable IPv6"),
        default=False
    )

    int_mtu = models.IntegerField(
        verbose_name=_("MTU"),
        null=True,
        blank=True
    )

    def __unicode__(self):
        if not self.int_name:
            return self.int_interface
        return u'%s' % self.int_name

    def __init__(self, *args, **kwargs):
        super(Interfaces, self).__init__(*args, **kwargs)

    def delete(self):
        with transaction.atomic():
            for lagg in self.lagginterface_set.all():
                lagg.delete()
            if self.id:
                super(Interfaces, self).delete()
        notifier().stop("netif")
        notifier().start("network")

    class Meta:
        verbose_name = _("Interface")
        verbose_name_plural = _("Interfaces")
        ordering = ["int_interface"]

    class Middleware:
        provider_name = 'network.interfaces'
        field_mapping = (
            (('id', 'int_interface'), 'id'),
            ('int_name', 'name'),
            ('int_dhcp', 'dhcp'),
            ('int_ipv6auto', 'rtadv'),
            ('int_disableipv6', 'noipv6'),
            ('int_mtu', 'mtu')
        )

    @property
    def aliases(self):
        from freenasUI.middleware.connector import connection as dispatcher
        iface = dispatcher.call_sync('network.interfaces.query', [('id', '=', self.id)], {'single': True})
        return filter(lambda a: a['type'] != 'LINK', iface.get('aliases', []))

    def get_ipv4_addresses(self):
        """
        Includes IPv4 addresses in aliases
        """
        return map(lambda a: a['address'], filter(lambda a: a['type'] == 'INET', self.aliases))

    def get_ipv6_addresses(self):
        """
        Includes IPv6 addresses in aliases
        """
        return map(lambda a: a['address'], filter(lambda a: a['type'] == 'INET6', self.aliases))

    def get_media_status(self):
        return notifier().iface_media_status(self.int_interface)


class VLAN(NewModel):
    id = models.CharField(
        max_length=120,
        primary_key=True
    )

    vlan_vint = models.CharField(
        max_length=120,
        verbose_name=_("Virtual Interface"),
        help_text=_("Interface names must be vlanX where X is a number. "
            "Example: vlan0.")
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
        ordering = ["vlan_vint"]

    class Middleware:
        provider_name = 'network.interfaces'
        default_filters = [
            ('type', '=', 'VLAN')
        ]
        field_mapping = (
            (('id', 'vlan_vint'), 'id'),
            ('vlan_pint', 'vlan.parent'),
            ('vlan_tag', 'vlan.tag'),
            ('vlan_description', 'name')
        )

    class FreeAdmin:
        icon_object = u"VLANIcon"
        icon_model = u"VLANIcon"
        icon_add = u"AddVLANIcon"
        icon_view = u"ViewAllVLANsIcon"


class LAGGInterface(Model):
    # LAGG interface to protocol type map.
    # This model amends Interface to provide information regarding to a lagg
    # interface.
    # A corresponding interface is created as "laggX"
    lagg_interface = models.ForeignKey(
            Interfaces,
            unique=True,
            verbose_name=_("Interface")
            )
    lagg_protocol = models.CharField(
            max_length=120,
            verbose_name=_("Protocol Type"),
            choices=choices.LAGGType,
            )

    class Meta:
        verbose_name = _("Link Aggregation")
        verbose_name_plural = _("Link Aggregations")
        ordering = ["lagg_interface"]

    def __unicode__(self):
        interface_list = LAGGInterfaceMembers.objects.filter(
            lagg_interfacegroup=self.id)
        if interface_list != None:
            interfaces = ', '.join(
                [int.lagg_physnic for int in interface_list]
                )
        else:
            interfaces = 'None'
        return "%s (%s: %s)" % (
            self.lagg_interface,
            self.lagg_protocol,
            interfaces)

    def delete(self):
        super(LAGGInterface, self).delete()
        VLAN.objects.filter(
            vlan_pint=self.lagg_interface.int_interface
            ).delete()
        self.lagg_interface.delete()
        notifier().iface_destroy(self.lagg_interface.int_interface)


class LAGGInterfaceMembers(Model):
    # Physical interfaces list inside one LAGG group
    lagg_interfacegroup = models.ForeignKey(
            LAGGInterface,
            verbose_name=_("LAGG Interface Group")
            )
    lagg_ordernum = models.IntegerField(
            verbose_name=_("LAGG Priority Number"),
            )
    lagg_physnic = models.CharField(
            max_length=120,
            unique=True,
            verbose_name=_("Physical NIC")
            )
    lagg_deviceoptions = models.CharField(
            max_length=120,
            verbose_name=_("Options")
            )

    def __unicode__(self):
        return self.lagg_physnic

    def delete(self):
        notifier().lagg_remove_port(
            self.lagg_interfacegroup.lagg_interface.int_interface,
            self.lagg_physnic,
            )
        super(LAGGInterfaceMembers, self).delete()

    class Meta:
        verbose_name = _("Link Aggregation Member")
        verbose_name_plural = _("Link Aggregation Members")
        ordering = ["lagg_interfacegroup"]


class StaticRoute(NewModel):
    id = models.CharField(
        max_length=120,
        primary_key=True
    )

    sr_name = models.CharField(
        max_length=120,
        verbose_name=_("Name"),
    )

    sr_type = models.CharField(
        max_length=120,
        verbose_name=_("Protocol"),
        choices=choices.AddressFamily
    )

    sr_destination = IP4AddressField(
        max_length=120,
        verbose_name=_("Destination network")
    )

    sr_netmask = models.IntegerField(
        choices=choices.v4NetmaskBitList,
        verbose_name=_("Destination netmask")
    )

    sr_gateway = IP4AddressField(
        max_length=120,
        verbose_name=_("Gateway")
    )

    class Meta:
        verbose_name = _("Static Route")
        verbose_name_plural = _("Static Routes")
        ordering = ["sr_destination", "sr_netmask", "sr_gateway"]

    class Middleware:
        provider_name = 'network.routes'
        field_mapping = (
            (('id', 'sr_name'), 'id'),
            ('sr_type', 'type'),
            ('sr_destination', 'network'),
            ('sr_netmask', 'netmask'),
            ('sr_gateway', 'gateway')
        )

    class FreeAdmin:
        icon_object = u"StaticRouteIcon"
        icon_model = u"StaticRouteIcon"
        icon_add = u"AddStaticRouteIcon"
        icon_view = u"ViewAllStaticRoutesIcon"

    def __unicode__(self):
        return self.sr_destination


class Host(NewModel):
    id = models.CharField(
        max_length=255,
        primary_key=True
    )

    name = models.CharField(
        max_length=255,
        primary_key=True,
        verbose_name=_("Hostname")
    )

    address = IPAddressField(
        verbose_name=_("Address")
    )

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = _("Host")
        verbose_name_plural = _("Hosts")

    class Middleware:
        provider_name = 'network.hosts'
        field_mapping = (
            (('id', 'name'), 'id'),
            ('address', 'address')
        )

    class FreeAdmin:
        icon_object = u"StaticRouteIcon"
        icon_model = u"StaticRouteIcon"
        icon_add = u"AddStaticRouteIcon"
        icon_view = u"ViewAllStaticRoutesIcon"
