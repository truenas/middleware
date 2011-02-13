#+
# Copyright 2010 iXsystems
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
# $FreeBSD$
#####################################################################

from django.db import models
from django import forms
from django.contrib.auth.models import User
import datetime
import time
from os import popen
from django.utils.text import capfirst
from django.forms.widgets import RadioFieldRenderer
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext_lazy as _
from datetime import datetime
from freenasUI.choices import *
from freenasUI.contrib.IPAddressField import *
from freeadmin.models import Model

## Network|Global Configuration
class GlobalConfiguration(Model):

    gc_hostname = models.CharField(
            max_length=120,
            verbose_name="Hostname"
            )

    gc_domain = models.CharField(
            max_length=120,
            verbose_name="Domain"
            )

    gc_ipv4gateway = IP4AddressField(
            blank=True,
            default='',
            verbose_name="IPv4 Default Gateway", 
            )

    gc_ipv6gateway = IP6AddressField(
            blank=True,
            default='',
            verbose_name="IPv6 Default Gateway", 
            )

    gc_nameserver1 = IPAddressField(
            blank=True,
            default='',
            verbose_name="Nameserver 1"
            )

    gc_nameserver2 = IPAddressField(
            default='',
            blank=True,
            verbose_name="Nameserver 2"
            )

    gc_nameserver3 = IPAddressField(
            default='',
            blank=True,
            verbose_name="Nameserver 3"
            )

    def __unicode__(self):
            return u'%s' % self.id 
    class Meta:
        verbose_name = "Global Configuration"
        verbose_name_plural = "Global Configuration"

    class FreeAdmin:
        deletable = False

## Network|Interface Management
class Interfaces(Model):

    int_interface = models.CharField(
            max_length=300, 
            choices=list(NICChoices()), 
            blank=False, 
            verbose_name="NIC",
            help_text="Pick your NIC"
            )

    int_name = models.CharField(
            max_length="120", 
            verbose_name="Interface Name",
            help_text="Name your NIC."
            )

    int_dhcp = models.BooleanField(
            verbose_name="DHCP", 
            help_text="When enabled, use DHCP to obtain IPv4 address as well as default router, etc."
            )

    int_ipv4address = IPAddressField(
            verbose_name="IPv4 Address",
            blank=True,
            default='',
            )

    int_v4netmaskbit = models.CharField(
            max_length=3, 
            choices=v4NetmaskBitList, 
            blank=True, 
            default='',
            verbose_name="IPv4 Netmask",
            help_text=""
            )

    int_ipv6auto = models.BooleanField(
            verbose_name="Auto configure IPv6", 
            help_text="When enabled, automatically configurate IPv6 address via rtsol(8)."
            )

    int_ipv6address = IPAddressField(
            verbose_name="IPv6 Address",
            blank=True,
            default='',
            )

    int_v6netmaskbit = models.CharField(
            max_length=4, 
            choices=v6NetmaskBitList, 
            blank=True,
            default='',
            verbose_name="IPv6 Netmask",
            help_text=""
            )

    int_options = models.CharField(
            max_length=120, 
            verbose_name="Options", 
            blank=True
            )

    def __unicode__(self):
            return u'%s' % self.int_name 
    class Meta:
        verbose_name = "Interfaces"
        verbose_name_plural = "Interfaces"
    class FreeAdmin:
        create_modelform = "InterfacesForm"
        edit_modelform = "InterfacesEditForm"
        icon_object = u"InterfacesIcon"
        icon_model = u"InterfacesIcon"
        icon_add = u"AddInterfaceIcon"
        icon_view = u"ViewAllInterfacesIcon"


## Network|Interface Management|VLAN
class VLAN(Model):
    vlan_vint = models.CharField(
            max_length=120, 
            verbose_name="Virtual Interface"
            )
    vlan_pint = models.CharField(
            max_length=300, 
            choices=NICChoices(), 
            blank=False, 
            verbose_name="Physical Interface"
            )
    vlan_tag = models.CharField(
            max_length=120, 
            verbose_name="VLAN Tag"
            )
    vlan_description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True
            )
    
    def __unicode__(self):
        return self.vlan_vint

    class Meta:
        verbose_name = "VLAN"

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
            verbose_name="Interface"
            )
    lagg_protocol = models.CharField(
            max_length=120, 
            verbose_name="Protocol Type",
            choices=LAGGType,
            )
    def __unicode__(self):
        interface_list = LAGGInterfaceMembers.objects.filter(lagg_interfacegroup = self.id)
        if interface_list != None:
            interfaces = ', '.join([int.lagg_physnic for int in interface_list])
        else:
            interfaces = 'None'
        return "%s (%s: %s)" % (self.lagg_interface, self.lagg_protocol, interfaces)

    class FreeAdmin:
        icon_object = u"VLANIcon"
        icon_model = u"VLANIcon"
        icon_add = u"AddVLANIcon"
        icon_view = u"ViewAllVLANsIcon"

# Physical interfaces list inside one LAGG group
class LAGGInterfaceMembers(Model):
    lagg_interfacegroup = models.ForeignKey(
            LAGGInterface, 
            verbose_name="LAGG Interface group"
            )
    lagg_ordernum = models.IntegerField(
            verbose_name="LAGG Priority Number",
            )
    lagg_physnic = models.CharField(
            max_length=120, 
            choices=NICChoices(), 
            unique = True,
            verbose_name="Physical NIC"
            )
    lagg_deviceoptions = models.CharField(
            max_length=120, 
            verbose_name="Options"
            )
    def __unicode__(self):
        return self.lagg_physnic

    class Meta:
        verbose_name = "Link Aggregation"
    
    class FreeAdmin:
        icon_object = u"LAGGIcon"
        icon_model = u"LAGGIcon"

class StaticRoute(Model):
    sr_destination = models.CharField(
            max_length=120, 
            verbose_name="Destination network"
            )
    sr_gateway = models.CharField(
            max_length=120, 
            verbose_name="Gateway"
            )
    sr_description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True
            )

    class Meta:
        verbose_name = "Static Route"

    class FreeAdmin:
        icon_object = u"StaticRouteIcon"
        icon_model = u"StaticRouteIcon"
        icon_add = u"AddStaticRouteIcon"
        icon_view = u"ViewAllStaticRoutesIcon"

    def __unicode__(self):
        return self.sr_destination
    
    def save(self, *args, **kwargs):
        super(StaticRoute, self).save(*args, **kwargs)

