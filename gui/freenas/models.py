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
from freenasUI.freenas.choices import *

class RadioFieldRendererEx(RadioFieldRenderer):
    outer = u"<span>%s</span>"
    inner= u"%s"
    def render(self):
         return mark_safe(self.outer % u'\n'.join ([ self.inner % w for w in self ]))


class systemGeneralSetup(models.Model):
    hostname = models.CharField(
            max_length=120, 
            verbose_name="Hostname"
            )
    domain = models.CharField(
            max_length=120, 
            verbose_name="Domain"
            )
    username = models.CharField(
            max_length=120, 
            verbose_name="Username"
            )
    guiprotocol = models.CharField(
            max_length=120, 
            choices=PROTOCOL_CHOICES, 
            default="http", 
            verbose_name="Protocol"
            )
    language = models.CharField(
            max_length=120, 
            choices=LANG_CHOICES, 
            default="english", 
            verbose_name="Language"
            )
    timezone = models.CharField(
            max_length=120, 
            choices=TIMEZONE_CHOICES, 
            default="america-los_angeles", 
            verbose_name="Timezone"
            )

## System|General|Password
class systemGeneralPassword(models.Model):
    currentpw = models.CharField(max_length=120)
    newpw = models.CharField(max_length=120)
    newpw2 = models.CharField(max_length=120)

###  END System|General ###
class NewCharField(models.CharField):
    _metaclass_  = models.SubfieldBase
    def __init__(self, *args, **kwds):
        super(NewCharField, self).__init__(*args, **kwds)
    def formfield(self, **kwargs):
        defaults = {'choices': self.get_choices(include_blank=False)}
        defaults.update(kwargs)
        super(NewCharField, self).formfield(**defaults)
    #_metaclass_ = models.SubfieldBase
    #def __init__(self, *args, **kwds):
    #super(NewCharField, self).__init__(*args, **kwds)
    #def formfield(self, **kwargs):
       # super(NewCharField, self).formfield(**kwargs)
        #defaults = {'required': not self.blank, 'label': capfirst(self.verbose_name), 'help_text': self.help_text}
        #defaults['choices'] = self.get_choices(include_blank=False)

## System|Advanced
class systemAdvanced(models.Model):
    consolemenu = models.BooleanField()
    serialconsole = models.BooleanField()
    consolescreensaver = models.BooleanField()
    firmwarevc = models.BooleanField()
    systembeep = models.BooleanField()
    tuning = models.BooleanField()
    powerdaemon = models.BooleanField()
    zeroconfbonjour = models.BooleanField()
    motd = models.TextField(verbose_name="MOTD") 

## System|Advanced|Email
class systemAdvancedEmail(models.Model):
    fromemail = models.CharField(
            max_length=120, 
            verbose_name="From email", 
            blank=True
            )
    outgoingserver = models.CharField(
            max_length=120, 
            verbose_name="Outgoing mail server", 
            blank=True
            )
    port = models.CharField(
            max_length=120, 
            verbose_name="Port"
            )
    security = models.CharField(
            max_length=120, 
            choices=EMAILSECURITY_CHOICES, 
            default="none", 
            verbose_name="Security"
            )
    smtp = models.BooleanField()

## System|Advanced|Proxy

#### If the server is behind a proxy set this parameters 
#### to give local services access to the internet via proxy. 

class systemAdvancedProxy(models.Model):
    httpproxy = models.BooleanField()
    httpproxyaddress = models.CharField(
            max_length=120, 
            verbose_name="Address"
            )
    httpproxyport = models.CharField(
            max_length=120, 
            verbose_name="Port"
            )
    httpproxyauth = models.BooleanField()
    ftpproxy = models.BooleanField()
    ftpproxyaddress = models.CharField(
            max_length=120, 
            verbose_name="Address"
            )
    ftpproxyport = models.CharField(
            max_length=120, 
            verbose_name="Port"
            )
    ftpproxyauth = models.BooleanField()

## System|Advanced|Swap
class systemAdvancedSwap(models.Model):
    swapmemory = models.BooleanField()
    swaptype = models.CharField(
            max_length=120, 
            choices=SWAPTYPE_CHOICES, 
            verbose_name="Swap Type"
            )
    # mountpoint info goes here
    mountpoint = models.CharField(
            max_length=120, 
            choices=MOUNTPOINT_CHOICES, 
            verbose_name="Mount point"
            )
    swapsize = models.CharField(
            max_length=120, 
            verbose_name="Size"
            )

## Command Scripts
class CommandScripts(models.Model):
    command = models.CharField(
            max_length=120, 
            verbose_name="Command"
            )
    commandtype = models.CharField(
            max_length=120, 
            choices=COMMANDSCRIPT_CHOICES, 
            verbose_name="Type"
            )

## System|Advanced|Command scripts
class systemAdvancedCommandScripts(models.Model):
    commandscripts = models.ForeignKey(CommandScripts, verbose_name="Command") 


## System|Advanced|Cron
class cronjob(models.Model):
    togglecron = models.BooleanField()
    croncommand = models.CharField(
            max_length=120, 
            verbose_name="Command"
            )
    cronwho = models.CharField(
            max_length=120, 
            choices=whoChoices(), 
            default="root", 
            verbose_name="Who"
            )
    description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True
            )
    ToggleMinutes = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Minutes"
            )
    Minutes1 = models.CharField(
            max_length=120, 
            choices=MINUTES1_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Minutes2 = models.CharField(
            max_length=120, 
            choices=MINUTES2_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Minutes3 = models.CharField(
            max_length=120, 
            choices=MINUTES3_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Minutes4 = models.CharField(
            max_length=120, 
            choices=MINUTES4_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    ToggleHours = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Hours"
            )
    Hours1 = models.CharField(
            max_length=120, 
            choices=HOURS1_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Hours2 = models.CharField(
            max_length=120, 
            choices=HOURS2_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    ToggleDays = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Days"
            )
    Days1 = models.CharField(
            max_length=120, 
            choices=DAYS1_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Days2 = models.CharField(
            max_length=120, 
            choices=DAYS2_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Days3 = models.CharField(
            max_length=120, 
            choices=DAYS3_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    ToggleMonths = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Months"
            )
    Months = models.CharField(
            max_length=120, 
            choices=MONTHS_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    ToggleWeekdays = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name=""
            )
    Weekdays = models.CharField(
            max_length=120, 
            choices=WEEKDAYS_CHOICES, 
            default="(NONE)", 
            verbose_name="Weekdays"
            )
class systemAdvancedCron(models.Model):
    cronjob = models.ForeignKey(cronjob, verbose_name="Cron job") 

## System|Advanced|rc.conf
class rcconf(models.Model):
    varname = models.CharField(
            max_length=120, 
            verbose_name="Name"
            )
    varvalue = models.CharField(
            max_length=120, 
            verbose_name="Value"
            )
    varcomment = models.CharField(
            max_length=120, 
            verbose_name="Comment"
            )
class systemAdvancedRCconf(models.Model):
    rcvariable = models.ForeignKey(rcconf, verbose_name="Variable") 

## System|Advanced|sysctl.conf
class sysctlMIB(models.Model):
    MIBname = models.CharField(
            max_length=120, 
            verbose_name="Name"
            )
    MIBvalue = models.CharField(
            max_length=120, 
            verbose_name="Value"
            )
    MIBcomment = models.CharField(
            max_length=120, 
            verbose_name="Comment"
            )
class systemAdvancedSYSCTLconf(models.Model):
    sysctlMIB = models.ForeignKey(sysctlMIB, verbose_name="sysctl") 

###  END System|Advanced ###

## Network|Interface Management
class networkInterfaceMGMT(models.Model):
    interface = models.CharField(
            max_length=300, 
            choices=NICChoices(), 
            blank=False, 
            verbose_name="NIC",
            help_text="Pick your NIC"
            )
    name = models.CharField(
            max_length="120", 
            verbose_name="Interface Name",
            help_text="Name your NIC."
            )
    ipv4address = models.CharField(
            max_length=18, 
            verbose_name="IPv4 Address", 
            blank=True
            )
    ipv6address = models.CharField(
            max_length=42, 
            verbose_name="IPv6 Address", 
            blank=True
            )
    options = models.CharField(
            max_length=120, 
            verbose_name="Options", 
            blank=True
            )
    def __unicode__(self):
        return self.name + " - " + self.interface
    class Meta:
        verbose_name = "Interfaces"

## Network|Hosts
"""
# active interfaces - unused

class networkHosts(models.Model):
    interface = models.ForeignKey(networkInterfaceMGMT, verbose_name="Interface")
    #hostac = models.TextField(max_length=120, verbose_name="Host access control")
    def __unicode__(self):
        return self.interface
    class Meta:
        verbose_name = "Host"
"""

## Network|Interface Management|VLAN
class networkVLAN(models.Model):
    vint = models.CharField(
            max_length=120, 
            verbose_name="Virtual Interface"
            )
    pint = models.CharField(
            max_length=300, 
            choices=NICChoices(), 
            blank=False, 
            verbose_name="Physical Interface"
            )
    tag = models.CharField(
            max_length=120, 
            verbose_name="VLAN Tag"
            )
    description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True
            )
    
    def __unicode__(self):
        return self.vint

    class Meta:
        verbose_name = "VLAN"

class networkInterfaceMGMTvlan(models.Model):
    vlanlist = models.ForeignKey(
            networkVLAN, 
            verbose_name="VLAN"
            )
    
    def __unicode__(self):
        return self.vlanlist

    class Meta:
        verbose_name = "VLAN"

class networkLAGG(models.Model):
    vint = models.CharField(
            max_length=120, 
            verbose_name="Virtual Interface"
            )
    ports = models.CharField(
            max_length=120, 
            verbose_name="Ports"
            )
    description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True
            )
    
    def __unicode__(self):
        return self.vint

    class Meta:
        verbose_name = "LAGG"

class networkInterfaceMGMTlagg(models.Model):
    lagglist = models.ForeignKey(networkLAGG, verbose_name="LAGG")
    
    def __unicode__(self):
        return self.lagglist

    class Meta:
        verbose_name = "LAGG"

class networkStaticRoute(models.Model):
    interface = models.ForeignKey(
            networkInterfaceMGMT, 
            verbose_name="Interface"
            )
    destination = models.CharField(
            max_length=120, 
            verbose_name="Destination network"
            )
    gateway = models.CharField(
            max_length=120, 
            verbose_name="Gateway"
            )
    description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True
            )

    class Meta:
        verbose_name = "Static Route"

    def __unicode__(self):
        return self.destination
    
    def save(self, *args, **kwargs):
        super(networkStaticRoute, self).save(*args, **kwargs)
    



""" Disk and Volume Management """

class Disk(models.Model):
    name = models.CharField(
            max_length=120, 
            verbose_name="Name"
            )
    disks = models.CharField(
            max_length=120, 
            choices=DiskChoices(),
            verbose_name="Disks"
            )
    description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True
            )
    sort_order = models.IntegerField(
            _('sort order'), 
            default=0, 
            help_text='The order in which disks will be displayed.')
    transfermode = models.CharField(
            max_length=120, 
            choices=TRANSFERMODE_CHOICES, 
            default="Auto", 
            verbose_name="Transfer Mode"
            )
    hddstandby = models.CharField(
            max_length=120, 
            choices=HDDSTANDBY_CHOICES, 
            default="Always On", 
            verbose_name="HDD Standby"
            )
    advpowermgmt = models.CharField(
            max_length=120, 
            choices=ADVPOWERMGMT_CHOICES, 
            default="Disabled", 
            verbose_name="Advanced Power Management"
            )
    acousticlevel = models.CharField(
            max_length=120, 
            choices=ACOUSTICLVL_CHOICES, 
            default="Disabled", 
            verbose_name="Acoustic Level"
            )
    togglesmart = models.BooleanField()
    smartoptions = models.CharField(
            max_length=120, 
            verbose_name="S.M.A.R.T. extra options", 
            blank=True
            )
    class Meta:
        verbose_name = "Disk"
        ordering = ['sort_order',]
    def __unicode__(self):
        return self.disks + ' (' + self.name + ')'
    def save(self, *args, **kwargs):
        super(Disk, self).save(*args, **kwargs)

class DiskGroup(models.Model):
    name = models.CharField(
            max_length=120, 
            verbose_name="Name"
            )
    members = models.ManyToManyField(Disk)
    type = models.CharField(
            max_length=120, 
            choices=ZFS_Choices, 
            default=" ", 
            verbose_name="Type", 
            blank="True"
            )
    
    def __unicode__(self):
        return self.name

class zpool(models.Model):
    zpool = models.CharField(
            max_length=120, 
            choices=ZFS_Choices, 
            verbose_name="zfs", 
            blank=True
            )




""" Volume Management """
class Volume(models.Model):
    name = models.CharField(
            max_length=120, 
            verbose_name="Name"
            )
    type = models.CharField(
            max_length=120, 
            choices=VolumeType_Choices, 
            default=" ", 
            verbose_name="Volume Type", 
            blank="True"
            )
    groups = models.ManyToManyField(DiskGroup)
    class Meta:
        verbose_name = "Volume"
    def __unicode__(self):
        return self.name
    def save(self, *args, **kwargs):
        super(Volume, self).save(*args, **kwargs)


class MountPoint(models.Model):
    volumeid = models.ForeignKey(Volume)
    mountpoint = models.CharField(
            max_length=120,
            verbose_name="Mount Point",
            help_text="Path to mount point",
            )
    mountoptions = models.CharField(
            max_length=120,
            verbose_name="Mount options",
            help_text="Enter Mount Point options here",
            )
    sharero = models.BooleanField()
    cifs = models.BooleanField()
    afp = models.BooleanField()
    nfs = models.BooleanField()


class WindowsShare(models.Model):
    name = models.CharField(
            max_length=120, 
            verbose_name="Name"
            )
    comment = models.CharField(
            max_length=120, 
            verbose_name="Comment"
            )
    path = models.ManyToManyField(MountPoint)
    globalro = models.BooleanField()
    cifsro = models.BooleanField()
    browsable = models.BooleanField()
    inheritperms = models.BooleanField()
    recyclebin = models.BooleanField()
    showhiddenfiles = models.BooleanField()
    hostsallow = models.CharField(
            max_length=120, 
            blank=True, 
            verbose_name="Hosts allow",
            help_text="This option is a comma, space, or tab delimited set of hosts which are permitted to access this share. You can specify the hosts by name or IP number. Leave this field empty to use default settings."
            )
    hostsdeny = models.CharField(
            max_length=120, 
            blank=True, 
            verbose_name="Hosts deny",
            help_text="This option is a comma, space, or tab delimited set of host which are NOT permitted to access this share. Where the lists conflict, the allow list takes precedence. In the event that it is necessary to deny all by default, use the keyword ALL (or the netmask 0.0.0.0/0) and then explicitly specify to the hosts allow parameter those hosts that should be permitted access. Leave this field empty to use default settings."
            )
    auxsmbconf = models.TextField(
            max_length=120, 
            verbose_name="Auxiliary paramters", 
            blank=True,
            help_text="These parameters are added to [Share] section of smb.conf"
            )
    
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = "Windows Share"

       
class AppleShare(models.Model):
    name = models.CharField(
            max_length=120, 
            verbose_name="Name"
            )
    comment = models.CharField(
            max_length=120, 
            verbose_name="Comment"
            )
    path = models.ManyToManyField(MountPoint)
    globalro = models.BooleanField()
    sharepw = models.CharField(
            max_length=120, 
            verbose_name="Share password",
            help_text="This controls the access to this share with an access password."
        )
    sharecharset = models.CharField(
            max_length=120, 
            verbose_name="Share character set", 
            help_text="Specifies the share character set. For example UTF8, UTF8-MAC, ISO-8859-15, etc."
            )
    allow = models.CharField(
            max_length=120, 
            verbose_name="Allow",
            help_text="This option allows the users and groups that access a share to be specified. Users and groups are specified, delimited by commas. Groups are designated by a @ prefix."
            )
    deny = models.CharField(
            max_length=120, 
            verbose_name="Allow",
            help_text="The deny option specifies users and groups who are not allowed access to the share. It follows the same format as the allow option."
            )
    afpro = models.CharField(
            max_length=120, 
            verbose_name="Read-only access",
            help_text="Allows certain users and groups to have read-only access to a share. This follows the allow option format."
        )
    afprw = models.CharField(
            max_length=120, 
            verbose_name="Read-only access",
            help_text="Allows certain users and groups to have read/write access to a share. This follows the allow option format. "
            )
    diskdiscovery = models.BooleanField()
    discoverymode = models.CharField(
            max_length=120, 
            choices=DISKDISCOVERY_CHOICES, 
            default='Default', 
            verbose_name="Disk discovery mode",
            help_text="Note! Selecting 'Time Machine' on multiple shares will may cause unpredictable behavior in MacOS."
            )
    dbpath = models.CharField(
            max_length=120, 
            verbose_name="Path",
            help_text="Path to be shared."
            )
    cachecnid = models.BooleanField()
    crlf = models.BooleanField()
    mswindows = models.BooleanField()
    noadouble = models.BooleanField()
    nodev = models.BooleanField()
    nofileid = models.BooleanField()
    nohex = models.BooleanField()
    prodos = models.BooleanField()
    nostat = models.BooleanField()
    upriv = models.BooleanField()
    
    def __unicode__(self):
        return self.path

    class Meta:
        verbose_name = "Share"
    
class UnixShare(models.Model):
    name = models.CharField(
            max_length=120, 
            verbose_name="Name"
            )
    comment = models.CharField(
            max_length=120, 
            verbose_name="Comment"
            )
    path = models.ManyToManyField(MountPoint)
    globalro = models.BooleanField()
    allroot = models.BooleanField()
    network = models.CharField(
            max_length=120, 
            verbose_name="Authorized network",
            help_text="Network that is authorised to access the NFS share."
            )
    alldirs = models.BooleanField()
    nfsro = models.BooleanField()
    quiet = models.BooleanField()
    
    def __unicode__(self):
        return self.path

    class Meta:
        verbose_name = "UNIX Share"     


   


class clientrsyncjob(models.Model):
    localshare = models.CharField(
            max_length=120, verbose_name="Local Share",
            help_text="Path to be shared."
            )
    remoteserver = models.CharField(
            max_length=120, 
            verbose_name="Remote RSYNC server",
            help_text="IP or FQDN address of remote Rsync server."
            )
    who = models.CharField(
            max_length=120, 
            choices=whoChoices(), 
            default="root", 
            verbose_name="Who"
            )
    description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True
            )
    ToggleMinutes = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Minutes"
            )
    Minutes1 = models.CharField(
            max_length=120, 
            choices=MINUTES1_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Minutes2 = models.CharField(
            max_length=120, 
            choices=MINUTES2_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Minutes3 = models.CharField(
            max_length=120, 
            choices=MINUTES3_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Minutes4 = models.CharField(
            max_length=120, 
            choices=MINUTES4_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    ToggleHours = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Hours"
            )
    Hours1 = models.CharField(
            max_length=120, 
            choices=HOURS1_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Hours2 = models.CharField(
            max_length=120, 
            choices=HOURS2_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    ToggleDays = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Days"
            )
    Days1 = models.CharField(
            max_length=120, 
            choices=DAYS1_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Days2 = models.CharField(
            max_length=120, 
            choices=DAYS2_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Days3 = models.CharField(
            max_length=120, 
            choices=DAYS3_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    ToggleMonths = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Months"
            )
    Months = models.CharField(
            max_length=120, 
            choices=MONTHS_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    ToggleWeekdays = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name=""
            )
    Weekdays = models.CharField(
            max_length=120, 
            choices=WEEKDAYS_CHOICES, 
            default="(NONE)", 
            verbose_name="Weekdays"
            )
    recursive = models.BooleanField()
    times = models.BooleanField()
    compress = models.BooleanField()
    archive = models.BooleanField()
    delete = models.BooleanField()
    quiet = models.BooleanField()
    preserveperms = models.BooleanField()
    extattr = models.BooleanField()
    options = models.CharField(
            max_length=120, 
            verbose_name="Extra options",
            help_text="Extra options to rsync (usually empty)."
            )
class localrsyncjob(models.Model):
    sourceshare = models.CharField(
            max_length=120, 
            verbose_name="Source Share",
            help_text="Source directory to be synchronized."
            )
    destinationshare = models.CharField(
            max_length=120, 
            verbose_name="Destination Share",
            help_text="Target directory."
            )
    who = models.CharField(
            max_length=120, 
            choices=whoChoices(), 
            default="root", 
            verbose_name="Who"
            )
    description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True
            )
    ToggleMinutes = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Minutes"
            )
    Minutes1 = models.CharField(
            max_length=120, 
            choices=MINUTES1_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Minutes2 = models.CharField(
            max_length=120, 
            choices=MINUTES2_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Minutes3 = models.CharField(
            max_length=120, 
            choices=MINUTES3_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Minutes4 = models.CharField(
            max_length=120, 
            choices=MINUTES4_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    ToggleHours = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES,
            default="Selected", 
            verbose_name="Hours"
            )
    Hours1 = models.CharField(
            max_length=120, 
            choices=HOURS1_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Hours2 = models.CharField(
            max_length=120, 
            choices=HOURS2_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    ToggleDays = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Days"
            )
    Days1 = models.CharField(
            max_length=120, 
            choices=DAYS1_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Days2 = models.CharField(
            max_length=120, 
            choices=DAYS2_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    Days3 = models.CharField(
            max_length=120,
            choices=DAYS3_CHOICES, 
            default="(NONE)", 
            verbose_name="")
    ToggleMonths = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected",
            verbose_name="Months"
            )
    Months = models.CharField(
            max_length=120, 
            choices=MONTHS_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    ToggleWeekdays = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name=""
            )
    Weekdays = models.CharField(
            max_length=120, 
            choices=WEEKDAYS_CHOICES, 
            default="(NONE)", 
            verbose_name="Weekdays"
            )
    recursive = models.BooleanField()
    times = models.BooleanField()
    compress = models.BooleanField()
    archive = models.BooleanField()
    delete = models.BooleanField()
    quiet = models.BooleanField()
    preserveperms = models.BooleanField()
    extattr = models.BooleanField()
    options = models.CharField(
            max_length=120, verbose_name="Extra options",
            help_text="Extra options to rsync (usually empty)."
            )

class servicesCIFS(models.Model):
    toggleCIFS = models.BooleanField()
    netbiosname = models.CharField(
            max_length=120, 
            verbose_name="NetBIOS name"
            )
    workgroup = models.CharField(
            max_length=120, 
            verbose_name="Workgroup",
            help_text="Workgroup the server will appear to be in when queried by clients (maximum 15 characters)."
            )
    cifs_description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True,
            help_text="Server description. This can usually be left blank."
            )
    doscharset = models.CharField(
            max_length=120, 
            choices=DOSCHARSET_CHOICES, 
            default="CP437", 
            verbose_name="DOS charset"
            )
    unixcharset = models.CharField(
            max_length=120, 
            choices=UNIXCHARSET_CHOICES, 
            default="UTF-8", 
            verbose_name="UNIX charset"
            )
    loglevel = models.CharField(
            max_length=120, 
            choices=LOGLEVEL_CHOICES, 
            default="Minimum", 
            verbose_name="Log level"
            )
    localmaster = models.BooleanField()
    timeserver = models.BooleanField()
    guest = models.CharField(
            max_length=120, 
            choices=whoChoices(), 
            default="www", 
            verbose_name="Guest account", 
            help_text="Use this option to override the username ('ftp' by default) which will be used for access to services which are specified as guest. Whatever privileges this user has will be available to any client connecting to the guest service. This user must exist in the password file, but does not require a valid login."
            )
    cifs_filemask = models.CharField(
            max_length=120, 
            verbose_name="File mask", 
            blank=True,
            help_text="Use this option to override the file creation mask (0666 by default)."
            )
    cifs_dirmask = models.CharField(
            max_length=120, 
            verbose_name="Directory mask", 
            blank=True,
            help_text="Use this option to override the directory creation mask (0777 by default)."
            )
    sendbuffer = models.CharField(
            max_length=120, 
            verbose_name="Send Buffer Size", 
            blank=True,
            help_text="Size of send buffer (64240 by default)."
            )
    recbuffer = models.CharField(
            max_length=120, 
            verbose_name="Receive Buffer Size", 
            blank=True,
            help_text="Size of receive buffer (64240 by default)."
            )
    largerw = models.BooleanField()
    sendfile = models.BooleanField()
    easupport = models.BooleanField()
    dosattr = models.BooleanField()
    nullpw = models.BooleanField()
    smb_options = models.TextField(
            max_length=120, 
            verbose_name="Auxiliary paramters", 
            blank=True,
            help_text="These parameters are added to [Global] section of smb.conf"
            )

class servicesAFP(models.Model):            
    toggleAFP = models.BooleanField()
    name = models.CharField(
            max_length=120, 
            verbose_name="Server Name",
            help_text="Name of the server. If this field is left empty the default server is specified."
            )
    guest = models.BooleanField()
    local = models.BooleanField()
    ddp = models.BooleanField()
class servicesNFS(models.Model):            
    toggleNFS = models.BooleanField()
    servers = models.CharField(
            max_length=120, 
            verbose_name="Number of servers",
            help_text="Specifies how many servers to create. There should be enough to handle the maximum level of concurrency from its clients, typically four to six."
            )

class servicesRSYNC(models.Model):
    toggleRSYNC = models.BooleanField()
    clientrsync = models.ForeignKey(
            clientrsyncjob, 
            verbose_name="Client RSYNC jobs"
            ) 
    localrsync = models.ForeignKey(
            localrsyncjob, 
            verbose_name="Local RSYNC jobs"
            ) 
    class Meta:
        verbose_name = "RSYNC"

class servicesUnison(models.Model):            
    toggleUnison = models.BooleanField()
    workingdir = models.CharField(
            max_length=120, 
            verbose_name="Working directory", 
            blank=True
            )
    createworkingdir = models.BooleanField()
    class Meta:
        verbose_name = "Unison"

class servicesiSCSITarget(models.Model):            
    toggleiSCSITarget = models.BooleanField()
    basename = models.CharField(
            max_length=120, 
            verbose_name="Base Name",
            help_text="The base name (e.g. iqn.2007-09.jp.ne.peach.istgt) will append the target name that is not starting with 'iqn.' "
            )
    discoveryauthmethod = models.CharField(
            max_length=120, 
            choices=DISCOVERYAUTHMETHOD_CHOICES, 
            default='auto', 
            verbose_name="Discovery Auth Method"
            )
    discoveryauthgroup = models.CharField(
            max_length=120, 
            choices=DISCOVERYAUTHGROUP_CHOICES, 
            default='none', 
            verbose_name="Discovery Auth Group"
            )
    io = models.CharField(
            max_length=120, 
            verbose_name="I/O Timeout",
            help_text="I/O timeout in seconds (30 by default)."
            )
    nopinint = models.CharField(
            max_length=120, 
            verbose_name="NOPIN Interval",
            help_text="NOPIN sending interval in seconds (20 by default)."
            )
    maxsesh = models.CharField(
            max_length=120, 
            verbose_name="Max. sessions",
            help_text="Maximum number of sessions holding at same time (32 by default)."
            )
    maxconnect = models.CharField(
            max_length=120, 
            verbose_name="Max. connections",
            help_text="Maximum number of connections in each session (8 by default)."
            )
    firstburst = models.CharField(
            max_length=120, 
            verbose_name="First burst length",
            help_text="iSCSI initial parameter (65536 by default)."
            )
    maxburst = models.CharField(
            max_length=120, 
            verbose_name="Max burst length",
            help_text="iSCSI initial parameter (262144 by default)."
            )
    maxrecdata = models.CharField(
            max_length=120, 
            verbose_name="Max receive data segment length",
            help_text="iSCSI initial parameter (262144 by default)."
            )
    toggleluc = models.BooleanField()

class servicesDynamicDNS(models.Model):            
    toggleDynamicDNS = models.BooleanField()
    provider = models.CharField(
            max_length=120, 
            choices=DYNDNSPROVIDER_CHOICES, 
            default='dyndns', 
            verbose_name="Provider"
            )
    domain = models.CharField(
            max_length=120, 
            verbose_name="Domain name", 
            blank=True,
            help_text="A host name alias. This option can appear multiple times, for each domain that has the same IP. Use a space to separate multiple alias names."
            )
    dyndns_username = models.CharField(
            max_length=120, 
            verbose_name="Username"
            )
    password = models.CharField(
            max_length=120, 
            verbose_name="Password"
            ) # need to make this a 'password' field, but not available in django Models 
    updateperiod = models.CharField(
            max_length=120, 
            verbose_name="Update period", 
            blank=True
            )
    fupdateperiod = models.CharField(
            max_length=120, 
            verbose_name="Forced update period", 
            blank=True
            )
    wildcard = models.BooleanField()
    dyndns_options = models.TextField(
            verbose_name="Auxiliary parameters", 
            blank=True,
            help_text="These parameters will be added to global settings in inadyn.conf."
            ) 

class servicesSNMP(models.Model):
    toggleSNMP = models.BooleanField()
    location = models.CharField(
            max_length=120, 
            verbose_name="Location", 
            blank=True,
            help_text="Location information, e.g. physical location of this system: 'Floor of building, Room xyz'."
            )
    contact = models.CharField(
            max_length=120, 
            verbose_name="Contact", 
            blank=True,
            help_text="Contact information, e.g. name or email of the person responsible for this system: 'admin@email.address'."
            )
    community = models.CharField(
            max_length=120, 
            verbose_name="Community",
            help_text="In most cases, 'public' is used here."
            )
    traps = models.BooleanField()
    snmp_options = models.TextField(
            verbose_name="Auxiliary parameters", 
            blank=True,
            help_text="These parameters will be added to global settings in inadyn.conf."
            ) 

class servicesUPS(models.Model):            
    toggleUPS = models.BooleanField()
    identifier = models.CharField(
            max_length=120, 
            verbose_name="Identifier",
            help_text="This name is used to uniquely identify your UPS on this system."
            )
    driver = models.CharField(
            max_length=120, 
            verbose_name="Driver", 
            blank=True,
            help_text="The driver used to communicate with your UPS."
            )
    ups_port = models.CharField(
            max_length=120, 
            verbose_name="Port", 
            blank=True,
            help_text="The serial or USB port where your UPS is connected."
            )
    ups_options = models.TextField(
            verbose_name="Auxiliary parameters", 
            blank=True,
            help_text="These parameters will be added to global settings in inadyn.conf."
            ) 
    ups_description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True
            )
    shutdown = models.CharField(
            max_length=120, 
            choices=UPS_CHOICES, 
            default='batt', 
            verbose_name="Shutdown mode"
            )
    shutdowntimer = models.CharField(
            max_length=120, 
            verbose_name="Shutdown timer",
            help_text="The time in seconds until shutdown is initiated. If the UPS happens to come back before the time is up the shutdown is canceled."
            )
    rmonitor = models.BooleanField()
    emailnotify = models.BooleanField()
    toemail = models.CharField(
            max_length=120, 
            verbose_name="To email", 
            blank=True,
            help_text="Destination email address. Separate email addresses by semi-colon."
            )
    subject = models.CharField(
            max_length=120, 
            verbose_name="To email",
            help_text="The subject of the email. You can use the following parameters for substitution:<br /><ul><li>%d - Date</li><li>%h - Hostname</li></ul>"
            )

class servicesWebserver(models.Model):            
    toggleWebserver = models.BooleanField()
    protocol = models.CharField(
            max_length=120, 
            choices=PROTOCOL_CHOICES, 
            default='OFF', 
            verbose_name="Protocol"
            )
    webserver_port = models.CharField(
            max_length=120, 
            verbose_name="Port",
            help_text="TCP port to bind the server to."
            )
    docroot = models.CharField(
            max_length=120, 
            verbose_name="Document root",
            help_text="Document root of the webserver. Home of the web page files."
            )
    auth = models.BooleanField()
    dirlisting = models.BooleanField()

class servicesBitTorrent(models.Model):            
    toggleBitTorrent = models.BooleanField()
    peerport = models.CharField(
            max_length=120, 
            verbose_name="Peer port",
            help_text="Port to listen for incoming peer connections. Default port is 51413."
            )
    downloaddir = models.CharField(
            max_length=120, 
            verbose_name="Download directory", 
            blank=True,
            help_text="Where to save downloaded data."
            )
    configdir = models.CharField(
            max_length=120, 
            verbose_name="Configuration directory",
            help_text="Alternative configuration directory (usually empty)", 
            blank=True
            )
    portfwd = models.BooleanField()
    pex = models.BooleanField()
    disthash = models.BooleanField()
    encrypt = models.CharField(
            max_length=120, 
            choices=BTENCRYPT_CHOICES, 
            default='preferred',
            verbose_name="Encryption",
            help_text="The peer connection encryption mode.", 
            blank=True
            )
    uploadbw = models.CharField(
            max_length=120, 
            verbose_name="Upload bandwidth",
            help_text="The maximum upload bandwith in KB/s. An empty field means infinity.", 
            blank=True
            )
    downloadbw = models.CharField(
            max_length=120, 
            verbose_name="Download bandwidth",
            help_text="The maximum download bandwith in KiB/s. An empty field means infinity.",
            blank=True
            )
    watchdir = models.CharField(
            max_length=120,
            verbose_name="Watch directory",
            help_text="Directory to watch for new .torrent files.",
            blank=True
            )
    incompletedir = models.CharField(
            max_length=120, 
            verbose_name="Incomplete directory",
            help_text="Directory to incomplete files. An empty field means disable.", 
            blank=True
            )
    bt_umask = models.CharField(
            max_length=120,
            verbose_name="User mask",
            help_text="Use this option to override the default permission modes for newly created files (0002 by default).", 
            blank=True
            )
    bt_options = models.CharField(
            max_length=120, 
            verbose_name="Extra Options", 
            blank=True
            )
    adminport = models.CharField(
            max_length=120, 
            verbose_name="Web admin port",
            help_text="Port to run bittorrent's web administration app on"
            )
    adminauth = models.CharField(
            max_length=120, 
            verbose_name="Authorize Web Interface",
            help_text="When turned on, require authorization before allowing access to the web interface"
            )
    adminuser = models.CharField(
            max_length=120, 
            verbose_name="Web admin username",
            help_text="Username to authenticate to web interface with"
            )
    adminpass = models.CharField(
            max_length=120, 
            verbose_name="Web admin password",
            help_text="Password to authenticate to web interface with"
            )

class servicesFTP(models.Model):            
    toggleFTP = models.BooleanField()
    clients = models.CharField(
            max_length=120, 
            verbose_name="Clients",
            help_text="Maximum number of simultaneous clients."
            )
    ipconnections = models.CharField(
            max_length=120, 
            verbose_name="Connections",
            help_text="Maximum number of connections per IP address (0 = unlimited)."
            )
    loginattempt = models.CharField(
            max_length=120, 
            verbose_name="Login Attempts",
            help_text="Maximum number of allowed password attempts before disconnection."
            )
    timeout = models.CharField(
            max_length=120, 
            verbose_name="Timeout",
            help_text="Maximum idle time in seconds."
            )
    ftp_rootlogin = models.BooleanField()
    onlyanonymous = models.BooleanField()
    onlylocal = models.BooleanField()
    banner = models.TextField(
            max_length=120, 
            verbose_name="Banner", 
            blank=True,
            help_text="Greeting banner displayed by FTP when a connection first comes in."
            )
    ftp_filemask = models.CharField(
            max_length=120, 
            verbose_name="File mask",
            help_text="Use this option to override the file creation mask (077 by default)."
            )
    ftp_dirmask = models.CharField(
            max_length=120, 
            verbose_name="Directory mask",
            help_text="Use this option to override the file creation mask (077 by default)."
            )
    fxp = models.BooleanField()
    resume = models.BooleanField()
    defaultroot = models.BooleanField()
    ident = models.BooleanField()
    reversedns = models.BooleanField()
    masqaddress = models.CharField(
            max_length=120, 
            verbose_name="Masquerade address", 
            blank=True,
            help_text="Causes the server to display the network information for the specified IP address or DNS hostname to the client, on the assumption that that IP address or DNS host is acting as a NAT gateway or port forwarder for the server."
            )
    passiveportsmin = models.CharField(
            max_length=120, 
            verbose_name="Passive ports",
            help_text="The minimum port to allocate for PASV style data connections (0 = use any port)."
            )
    passiveportsmax = models.CharField(
            max_length=120, 
            verbose_name="Passive ports",
            help_text="The maximum port to allocate for PASV style data connections (0 = use any port). Passive ports restricts the range of ports from which the server will select when sent the PASV command from a client. The server will randomly choose a number from within the specified range until an open port is found. The port range selected must be in the non-privileged range (eg. greater than or equal to 1024). It is strongly recommended that the chosen range be large enough to handle many simultaneous passive connections (for example, 49152-65534, the IANA-registered ephemeral port range)."
            )
    localuserbw = models.CharField(
            max_length=120, 
            verbose_name="User bandwidth", 
            blank=True,
            help_text="Local user upload bandwith in KB/s. An empty field means infinity."
            )
    localuserdlbw = models.CharField(
            max_length=120, 
            verbose_name="Download bandwidth", 
            blank=True,
            help_text="Local user download bandwith in KB/s. An empty field means infinity."
            )
    anonuserbw = models.CharField(
            max_length=120, 
            verbose_name="Download bandwidth", 
            blank=True,
            help_text="Anonymous user upload bandwith in KB/s. An empty field means infinity."
            )
    anonuserdlbw = models.CharField(
            max_length=120, 
            verbose_name="Download bandwidth", 
            blank=True,
            help_text="Anonymous user download bandwith in KB/s. An empty field means infinity."
            )
    ssltls = models.BooleanField()
    ftp_options = models.TextField(
            max_length=120, 
            verbose_name="Banner", 
            blank=True,
            help_text="These parameters are added to proftpd.conf."
            )



class servicesTFTP(models.Model):            
    toggleTFTP = models.BooleanField()
    directory = models.CharField(
            max_length=120, 
            verbose_name="Directory",
            help_text="The directory containing the files you want to publish. The remote host does not need to pass along the directory as part of the transfer."
            )
    newfiles = models.BooleanField()
    tftp_port = models.CharField(
            max_length=120, 
            verbose_name="Port",
            help_text="The port to listen to. The default is to listen to the tftp port specified in /etc/services."
            )
    tftp_username = models.CharField(
            max_length=120, 
            choices=whoChoices(), 
            default="nobody", 
            verbose_name="Username", 
            help_text="Specifies the username which the service will run as."
            )
    tftp_umask = models.CharField(
            max_length=120, 
            verbose_name="umask",
            help_text="Set the umask for newly created files to the specified value. The default is 022 (everyone can read, nobody can write)."
            )
    tftp_options = models.CharField(
            max_length=120, 
            verbose_name="Extra options",
            blank=True, 
            help_text="Extra command line options (usually empty)."
            )

class servicesSSH(models.Model):            
    toggleSSH = models.BooleanField()
    tcpport = models.CharField(
            max_length=120, 
            verbose_name="TCP Port",
            help_text="Alternate TCP port. Default is 22"
            )
    ssh_rootlogin = models.BooleanField()
    passwordauth = models.BooleanField()
    tcpfwd = models.BooleanField()
    compression = models.BooleanField()
    privatekey = models.TextField(
            max_length=120, 
            verbose_name="Private Key", 
            blank=True,
            help_text="Paste a DSA PRIVATE KEY in PEM format here."
            )
    ssh_options = models.TextField(
            max_length=120, 
            verbose_name="Banner", 
            blank=True,
            help_text="Extra options to /etc/ssh/sshd_config (usually empty). Note, incorrect entered options prevent SSH service to be started."
            )
   
""" Access Section """

class accessActiveDirectory(models.Model):            
    toggle = models.BooleanField()
    dcname = models.CharField(
            max_length=120, 
            verbose_name="Domain Controller Name",
            help_text="AD or PDC name."
            )
    dnsrealmname = models.CharField(
            max_length=120, 
            verbose_name="Domain Name (DNS/Realm-Name)",
            help_text="Domain Name, eg example.com"
            )
    netbiosname = models.CharField(
            max_length=120,
            verbose_name="Domain Name (NetBIOS-Name)",
            help_text="Domain Name in old format, eg EXAMPLE"
            )
    adminname = models.CharField(
            max_length=120, 
            verbose_name="Administrator Name",
            help_text="Username of Domain Administrator Account"
            )
    adminpw = models.CharField(
            max_length=120, 
            verbose_name="Administrator Password",
            help_text="Password of Domain Administrator account."
            )

class accessLDAP(models.Model):            
    toggle = models.BooleanField()
    hostname = models.CharField(
            max_length=120, 
            verbose_name="Hostname", 
            blank=True,
            help_text="The name or IP address of the LDAP server"
            )
    basedn = models.CharField(
            max_length=120, 
            verbose_name="Base DN",
            blank=True,
            help_text="The default base Distinguished Name (DN) to use for seraches, eg dc=test,dc=org"
            )
    anonbind = models.BooleanField()
    rootbasedn = models.CharField(
            max_length=120, 
            verbose_name="Root bind DN", 
            blank=True,
            help_text="The distinguished name with which to bind to the directory server, e.g. cn=admin,dc=test,dc=org"
            )
    rootbindpw = models.CharField(
            max_length=120, 
            verbose_name="Root bind password",
            blank=True,
            help_text="The credentials with which to bind."
            )
    pwencyption = models.CharField(
            max_length=120, 
            choices=PWEncryptionChoices, 
            verbose_name="Password Encryption",
            help_text="The password change protocol to use."
            )
    usersuffix = models.CharField(
            max_length=120, 
            verbose_name="User Suffix",
            blank=True,
            help_text="This parameter specifies the suffix that is used for users when these are added to the LDAP directory, e.g. ou=Users"
            )
    groupsuffix = models.CharField(
            max_length=120, 
            verbose_name="Group Suffix", 
            blank=True,
            help_text="This parameter specifies the suffix that is used for groups when these are added to the LDAP directory, e.g. ou=Groups"
            )
    paswordsuffix = models.CharField(
            max_length=120, 
            verbose_name="Password Suffix", 
            blank=True,
            help_text="This parameter specifies the suffix that is used for passwords when these are added to the LDAP directory, e.g. ou=Passwords"
            )
    machinesuffix = models.CharField(
            max_length=120, 
            verbose_name="Machine Suffix", 
            blank=True,
            help_text="This parameter specifies the suffix that is used for machines when these are added to the LDAP directory, e.g. ou=Computers"
            )
    auxparams = models.TextField(
            max_length=120,
            verbose_name="Auxillary Parameters",
            blank=True,
            help_text="These parameters are added to ldap.conf."
            )
