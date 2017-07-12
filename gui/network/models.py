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
import os
import random
import string
import logging
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.contrib.IPAddressField import (
    IPAddressField, IP4AddressField, IP6AddressField
)
from freenasUI.freeadmin.models import Model
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.services.models import CIFS


log = logging.getLogger('network.models')


class GlobalConfiguration(Model):
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
    gc_domain = models.CharField(
        max_length=120,
        verbose_name=_("Domain"),
        default='local',
        validators=[RegexValidator(
            regex=r'^[a-zA-Z\.\-\_0-9]+$',
        )],
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
        help_text=_(
            "If enabled, delays the start of network-reliant services "
            "until interface is up and ICMP packets to a destination defined "
            "in netwait ip list are flowing.  Link state is examined first, "
            "followed by \"pinging\" an IP address to verify network "
            "usability.  If no destination can be reached or timeouts are "
            "exceeded, network services are started anyway with no guarantee "
            "that the network is usable."
        ),
        default=False,
    )
    gc_netwait_ip = models.CharField(
        verbose_name=_("Netwait IP list"),
        help_text=_(
            "Space-delimited list of IP addresses to ping(8). If "
            "multiple IP addresses are specified, each will be tried until "
            "one is successful or the list is exhausted. If it is empty the "
            "default gateway will be used."
        ),
        blank=True,
        max_length=300,
    )
    gc_hosts = models.TextField(
        verbose_name=_("Host name data base"),
        help_text=_(
            "This field is appended to /etc/hosts which contains "
            "information regarding known hosts on the network. hosts(5)"
        ),
        default='',
        blank=True,
    )

    def __init__(self, *args, **kwargs):
        super(GlobalConfiguration, self).__init__(*args, **kwargs)
        self._n = notifier()
        for name in (
            'gc_hostname',
            'gc_hostname_b',
            'gc_ipv4gateway',
            'gc_ipv6gateway',
            'gc_domain',
            'gc_nameserver1',
            'gc_nameserver2',
            'gc_nameserver3',
            'gc_httpproxy',
        ):
            setattr(self, "_orig_%s" % name, self.__dict__.get(name))

    def __str__(self):
        return str(self.id)

    def get_hostname(self):
        if not self._n.is_freenas() and self._n.failover_node() == 'B':
            return self.gc_hostname_b
        else:
            return self.gc_hostname

    def save(self, *args, **kwargs):
        # See #3437
        if (
            self._orig_gc_hostname != self.gc_hostname or
            self._orig_gc_hostname_b != self.gc_hostname_b
        ):
            try:
                cifs = CIFS.objects.order_by('-id')[0]
                cifs.cifs_srv_netbiosname = self.gc_hostname
                cifs.cifs_srv_netbiosname_b = self.gc_hostname_b
                cifs.save()
            except Exception:
                log.debug("Setting netbios names failed", exc_info=True)
        return super(GlobalConfiguration, self).save(*args, **kwargs)

    class Meta:
        verbose_name = _("Global Configuration")
        verbose_name_plural = _("Global Configuration")


class Interfaces(Model):
    int_interface = models.CharField(
        max_length=300,
        blank=False,
        verbose_name=_("NIC"),
        help_text=_("Pick your NIC")
    )
    int_name = models.CharField(
        max_length=120,
        verbose_name=_("Interface Name"),
        help_text=_("Name your NIC.")
    )
    int_dhcp = models.BooleanField(
        verbose_name=_("DHCP"),
        default=False,
        help_text=_(
            "When enabled, use DHCP to obtain IPv4 address as well"
            " as default router, etc."
        ),
    )
    int_ipv4address = IPAddressField(
        verbose_name=_("IPv4 Address"),
        blank=True,
        default='',
    )
    int_ipv4address_b = IPAddressField(
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
        default=False,
        help_text=_(
            "When enabled, automatically configurate IPv6 address "
            "via rtsol(8)."
        ),
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
    int_vip = IPAddressField(
        verbose_name=_("Virtual IP"),
        blank=True,
        null=True,
    )
    int_vhid = models.PositiveIntegerField(
        verbose_name=_("Virtual Host ID"),
        null=True,
        blank=True,
    )
    int_pass = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Password"),
        editable=False,
    )
    int_critical = models.BooleanField(
        default=False,
        verbose_name=_("Critical for Failover"),
    )
    int_group = models.IntegerField(
        verbose_name=_('Group'),
        choices=[(i, i) for i in range(1, 33)],
        null=True,
        blank=True,
    )
    int_options = models.CharField(
        max_length=120,
        verbose_name=_("Options"),
        blank=True
    )

    def __str__(self):
        if not self.int_name:
            return self.int_interface
        return str(self.int_name)

    def __init__(self, *args, **kwargs):
        super(Interfaces, self).__init__(*args, **kwargs)
        self._original_int_options = self.int_options

    def delete(self):
        with transaction.atomic():
            LAGGInterface.objects.filter(lagg_interface__id=self.id).delete()
            # Delete VLAN entries for this interface
            VLAN.objects.filter(vlan_vint=self.int_interface).delete()
            if self.id:
                super(Interfaces, self).delete()
        os.system("sleep 2")
        notifier().start("network")

    def save(self, *args, **kwargs):
        if self.int_vip and not self.int_pass:
            self.int_pass = ''.join([
                random.SystemRandom().choice(
                    string.ascii_letters + string.digits
                )
                for n in range(16)
            ])
        return super(Interfaces, self).save(*args, **kwargs)

    class Meta:
        verbose_name = _("Interface")
        verbose_name_plural = _("Interfaces")
        ordering = ["int_interface"]

    def get_ipv4_addresses(self):
        """
        Includes IPv4 addresses in aliases
        """
        ips = []
        if self.int_ipv4address:
            ips.append("%s/%s" % (
                str(self.int_ipv4address),
                str(self.int_v4netmaskbit),
            ))
        if self.int_ipv4address_b:
            ips.append("%s/%s" % (
                str(self.int_ipv4address_b),
                str(self.int_v4netmaskbit),
            ))
        for alias in self.alias_set.exclude(alias_v4address=''):
            ips.append("%s/%s" % (
                str(alias.alias_v4address),
                str(alias.alias_v4netmaskbit),
            ))
        return ips

    def get_my_ipv4_addresses(self, vip=None):
        """
        Includes IPv4 addresses of this node, aliases of this node,
        and (optionally) VIPs
        """
        ips = []
        _n = notifier()
        if not _n.is_freenas() and _n.failover_node() == 'B':
            if self.int_ipv4address_b:
                ips.append("%s" % str(self.int_ipv4address_b))
            for alias in self.alias_set.exclude(alias_v4address_b=''):
                ips.append("%s" % str(alias.alias_v4address_b))
        else:
            if self.int_ipv4address:
                ips.append("%s" % str(self.int_ipv4address))
            for alias in self.alias_set.exclude(alias_v4address=''):
                ips.append("%s" % str(alias.alias_v4address))
        if vip:
            if self.int_vip:
                ips.append("%s" % str(self.int_vip))
            for alias in self.alias_set.exclude(alias_vip=''):
                ips.append("%s" % str(alias.alias_vip))
        return ips

    def get_ipv6_addresses(self):
        """
        Includes IPv6 addresses in aliases
        """
        ips = []
        if self.int_ipv6address:
            ips.append("%s/%s" % (
                str(self.int_ipv6address),
                str(self.int_v6netmaskbit),
            ))
        for alias in self.alias_set.exclude(alias_v6address=''):
            ips.append("%s/%s" % (
                str(alias.alias_v6address),
                str(alias.alias_v6netmaskbit),
            ))
        return ips

    def get_media_status(self):
        return notifier().iface_media_status(self.int_interface)


class Alias(Model):
    alias_interface = models.ForeignKey(
        Interfaces,
        verbose_name=_("Interface")
    )
    alias_vip = IP4AddressField(
        verbose_name=_("Virtual IPv4"),
        default='',
        blank=True,
    )
    alias_v4address = IP4AddressField(
        verbose_name=_("IPv4 Address"),
        default='',
        blank=True,
    )
    alias_v4address_b = IP4AddressField(
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
    alias_v6address_b = IP6AddressField(
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

    def __str__(self):
        if self.alias_v4address:
            return '%s:%s' % (
                self.alias_interface.int_name,
                self.alias_v4address)
        elif self.alias_v6address:
            return '%s:%s' % (
                self.alias_interface.int_name,
                self.alias_v6address)

    @property
    def alias_network(self):
        if self.alias_v4address:
            return '%s/%s' % (self.alias_v4address, self.alias_v4netmaskbit)
        else:
            return '%s/%s' % (self.alias_v6address, self.alias_v6netmaskbit)

    def delete(self):
        super(Alias, self).delete()
        notifier().start("network")

    class Meta:
        verbose_name = _("Alias")
        verbose_name_plural = _("Aliases")

    class FreeAdmin:
        pass


class VLAN(Model):
    vlan_vint = models.CharField(
        max_length=120,
        verbose_name=_("Virtual Interface"),
        help_text=_(
            "Interface names must be vlanX where X is a number. "
            "Example: vlan0."
        ),
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

    def __str__(self):
        return self.vlan_vint

    def delete(self):
        vint = self.vlan_vint
        super(VLAN, self).delete()
        Interfaces.objects.filter(int_interface=vint).delete()

    class Meta:
        verbose_name = _("VLAN")
        verbose_name_plural = _("VLANs")
        ordering = ["vlan_vint"]

    class FreeAdmin:
        icon_object = "VLANIcon"
        icon_model = "VLANIcon"
        icon_add = "AddVLANIcon"
        icon_view = "ViewAllVLANsIcon"


class LAGGInterface(Model):
    # LAGG interface to protocol type map.
    # This model amends Interface to provide information regarding to a lagg
    # interface.
    # A corresponding interface is created as "laggX"
    lagg_interface = models.OneToOneField(
        Interfaces,
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

    def __str__(self):
        interface_list = LAGGInterfaceMembers.objects.filter(
            lagg_interfacegroup=self.id)
        if interface_list is not None:
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

    def __str__(self):
        return self.lagg_physnic

    class Meta:
        verbose_name = _("Link Aggregation Member")
        verbose_name_plural = _("Link Aggregation Members")
        ordering = ["lagg_interfacegroup"]


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
        ordering = ["sr_destination", "sr_gateway"]

    class FreeAdmin:
        icon_object = "StaticRouteIcon"
        icon_model = "StaticRouteIcon"
        icon_add = "AddStaticRouteIcon"
        icon_view = "ViewAllStaticRoutesIcon"

    def __str__(self):
        return self.sr_destination

    def save(self, *args, **kwargs):
        super(StaticRoute, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        super(StaticRoute, self).delete(*args, **kwargs)
        try:
            # TODO: async user notification
            notifier().staticroute_delete(self)
        except MiddlewareError:
            pass
