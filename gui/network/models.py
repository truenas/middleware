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

## Network|Global Configuration
class GlobalConfiguration(models.Model):
    gc_hostname = models.CharField(
            max_length=120,
            verbose_name="Hostname"
            )
    gc_domain = models.CharField(
            max_length=120,
            verbose_name="Domain"
            )
    gc_ipv4gateway = models.CharField(
            max_length=120, 
            verbose_name="IPv4 Default Gateway", 
            blank=True
            )
    gc_ipv6gateway = models.CharField(
            max_length=120, 
            verbose_name="IPv6 Default Gateway", 
            blank=True
            )
    gc_nameserver1 = models.CharField(
            max_length=120, 
            verbose_name="Nameserver 1", 
            blank=True
            )
    gc_nameserver2 = models.CharField(
            max_length=120, 
            verbose_name="Nameserver 2", 
            blank=True
            )
    gc_nameserver3 = models.CharField(
            max_length=120, 
            verbose_name="Nameserver 3", 
            blank=True
            )
    def __unicode__(self):
            return u'%s' % self.id 
    class Meta:
        verbose_name = "Global Configuration"



## Network|Interface Management
class Interfaces(models.Model):
    int_interface = models.CharField(
            max_length=300, 
            choices=NICChoices(), 
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
    int_ipv4address = models.CharField(
            max_length=18, 
            verbose_name="IPv4 Address", 
            blank=True
            )
    int_ipv6auto = models.BooleanField(
            verbose_name="Auto configure IPv6", 
            help_text="When enabled, automatically configurate IPv6 address via rtsol(8)."
            )
    int_ipv6address = models.CharField(
            max_length=42, 
            verbose_name="IPv6 Address", 
            blank=True
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


## Network|Interface Management|VLAN
class VLAN(models.Model):
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


class LAGG(models.Model):
    lagg_vint = models.CharField(
            max_length=120, 
            verbose_name="Virtual Interface"
            )
    lagg_ports = models.CharField(
            max_length=120, 
            verbose_name="Ports"
            )
    lagg_description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True
            )
    
    def __unicode__(self):
        return self.lagg_vint

    class Meta:
        verbose_name = "LAGG"

class StaticRoute(models.Model):
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

    def __unicode__(self):
        return self.sr_destination
    
    def save(self, *args, **kwargs):
        super(StaticRoute, self).save(*args, **kwargs)

