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

class RadioFieldRendererEx(RadioFieldRenderer):
    outer = u"<span>%s</span>"
    inner= u"%s"
    def render(self):
         return mark_safe(self.outer % u'\n'.join ([ self.inner % w for w in self ]))


# The following classes are needed by urls.py in order to pull
# in system info (like system load)  and use them as template variables.
# I'm not sure this is normally done, so feel free to view
# freenas/urls.py to see what I am doing

class Freenas(models.Model):
    name = models.CharField(max_length=60)
class Top(models.Model):
    name = models.CharField(max_length=60)

YESNO_CHOICES = (
        ('DO NOTHING', 'DO NOTHING'),
        ('YES', 'YES'),
        ('NO', 'NO'),
        )
SMTPAUTH_CHOICES = (
        ('plain', 'Plain'),
        ('ssl', 'SSL'),
        ('tls', 'TLS'),
        )
# GUI protocol choice
PROTOCOL_CHOICES = (
        ('http', 'HTTP'),
        ('https', 'HTTPS'),
        )
# Language for the GUI 
LANG_CHOICES = (
        ('english', 'English'),
        )
# TIMEZONE_CHOICES should be replaced by system timezone info 
TIMEZONE_CHOICES = (
        ('america-los_angeles', 'America/Los_Angeles'),
        )
ZPOOL_CHOICES = (
        ('Basic', 'Basic'),
        ('Mirror', 'Mirror'),
        ('RAID-Z', 'RAID-Z'),
        ('RAID-Z2', 'RAID-Z2'),
        )
# enable/disable system options
TOGGLE_CHOICES = (
        ('ON', 'ON'),
        ('OFF', 'OFF'),
        )
EMAILSECURITY_CHOICES = (
        ('None', 'None'),
        ('SSL', 'SSL'),
        ('TLS', 'TLS'),
        )
SWAPTYPE_CHOICES = (
        ('File', 'File'),
        ('Device', 'Device'),
        )
# need to pull in mountpoints here
MOUNTPOINT_CHOICES = (
        ('FAKE', 'FAKE'),
        )
COMMANDSCRIPT_CHOICES = (
        ('PreInit', 'PreInit'),
        ('PostInit', 'PostInit'),
        ('Shutdown', 'Shutdown'),
        )
TOGGLECRON_CHOICES = (
        ('All', 'All'),
        ('Selected', 'Selected'),
        ('Deselected', 'Deselected'),
        )
MINUTES1_CHOICES = (
        ('0', '0'),
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4'),
        ('5', '5'),
        ('6', '6'),
        ('7', '7'),
        ('8', '8'),
        ('9', '9'),
        ('10', '10'),
        ('11', '11'),
        )
MINUTES2_CHOICES = (
        ('12', '12'),
        ('13', '13'),
        ('14', '14'),
        ('15', '15'),
        ('16', '16'),
        ('17', '17'),
        ('18', '18'),
        ('19', '19'),
        ('20', '20'),
        ('21', '21'),
        ('22', '22'),
        ('23', '23'),
        )
MINUTES3_CHOICES = (
        ('24', '24'),
        ('25', '25'),
        ('26', '26'),
        ('27', '27'),
        ('28', '28'),
        ('29', '29'),
        ('30', '30'),
        ('31', '31'),
        ('32', '32'),
        ('33', '33'),
        ('34', '34'),
        ('35', '35'),
        )
MINUTES4_CHOICES = (
        ('36', '36'),
        ('37', '37'),
        ('38', '38'),
        ('39', '39'),
        ('40', '40'),
        ('41', '41'),
        ('42', '42'),
        ('43', '43'),
        ('44', '44'),
        ('45', '45'),
        ('46', '46'),
        ('47', '47'),
        )
MINUTES5_CHOICES = (
        ('48', '48'),
        ('49', '49'),
        ('50', '50'),
        ('51', '51'),
        ('52', '52'),
        ('53', '53'),
        ('54', '54'),
        ('55', '55'),
        ('56', '56'),
        ('57', '57'),
        ('58', '58'),
        ('59', '59'),
        )
HOURS1_CHOICES = (
        ('0', '0'),
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4'),
        ('5', '5'),
        ('6', '6'),
        ('7', '7'),
        ('8', '8'),
        ('9', '9'),
        ('10', '10'),
        ('11', '11'),
        )
HOURS2_CHOICES = (
        ('12', '12'),
        ('13', '13'),
        ('14', '14'),
        ('15', '15'),
        ('16', '16'),
        ('17', '17'),
        ('18', '18'),
        ('19', '19'),
        ('20', '20'),
        ('21', '21'),
        ('22', '22'),
        ('23', '23'),
        )
DAYS1_CHOICES = (
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4'),
        ('5', '5'),
        ('6', '6'),
        ('7', '7'),
        ('8', '8'),
        ('9', '9'),
        ('10', '10'),
        ('11', '11'),
        ('12', '12'),
        )
DAYS2_CHOICES = (
        ('13', '13'),
        ('14', '14'),
        ('15', '15'),
        ('16', '16'),
        ('17', '17'),
        ('18', '18'),
        ('19', '19'),
        ('20', '20'),
        ('21', '21'),
        ('22', '22'),
        ('23', '23'),
        ('24', '24'),
        )
DAYS3_CHOICES = (
        ('25', '25'),
        ('26', '26'),
        ('27', '27'),
        ('28', '28'),
        ('29', '29'),
        ('30', '30'),
        ('31', '31'),
        )
MONTHS_CHOICES = (
        ('January', 'January'),
        ('February', 'February'),
        ('March', 'March'),
        ('April', 'April'),
        ('May', 'May'),
        ('June', 'June'),
        ('July', 'July'),
        ('August', 'August'),
        ('September', 'September'),
        ('October', 'October'),
        ('November', 'November'),
        ('December', 'December'),
        )
WEEKDAYS_CHOICES = (
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuseday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
        )


class systemGeneralSetup(models.Model):
    hostname = models.CharField(max_length=120, verbose_name="Hostname")
    domain = models.CharField(max_length=120, verbose_name="Domain")
    ## username is placeholder; needs to use django-auth
    username = models.CharField(max_length=120, verbose_name="Username")
    guiprotocol = models.CharField(max_length=120, choices=PROTOCOL_CHOICES, default="http", verbose_name="Protocol")
    # language and timezone to be replaced 
    # not sure what to do
    language = models.CharField(max_length=120, choices=LANG_CHOICES, default="english", verbose_name="Language")
    timezone = models.CharField(max_length=120, choices=TIMEZONE_CHOICES, default="america-los_angeles", verbose_name="Timezone")

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
    consolemenu = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default="OFF", verbose_name="Console Menu")
    serialconsole = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default="OFF", verbose_name="Serial Console")
    consolescreensaver = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default="OFF", verbose_name="Console screensaver")
    firmwarevc = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default="OFF", verbose_name="Firmware Version Check")
    systembeep = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default="OFF", verbose_name="System Beep")
    tuning = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default="OFF", verbose_name="Kernel Tuning")
    powerdaemon = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default="OFF", verbose_name="Power Daemon")
    zeroconfbonjour = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default="OFF", verbose_name="Zeroconf/Bonjour")
    motd = models.TextField(verbose_name="MOTD") 

## System|Advanced|Email
class systemAdvancedEmail(models.Model):
    fromemail = models.CharField(max_length=120, verbose_name="From email")
    outgoingserver = models.CharField(max_length=120, verbose_name="Outgoing mail server")
    port = models.CharField(max_length=120, verbose_name="Port")
    security = models.CharField(max_length=120, choices=EMAILSECURITY_CHOICES, default="none", verbose_name="Security")
    smtp = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default="OFF", verbose_name="SMTP Authentication")

## System|Advanced|Proxy

#### If the server is behind a proxy set this parameters 
#### to give local services access to the internet via proxy. 

class systemAdvancedProxy(models.Model):
    httpproxy = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default="OFF", verbose_name="HTTP Proxy")
    httpproxyaddress = models.CharField(max_length=120, verbose_name="Address")
    httpproxyport = models.CharField(max_length=120, verbose_name="Port")
    httpproxyauth = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default="OFF", verbose_name="HTTP Authentication")
    ftpproxy = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default="OFF", verbose_name="FTP Proxy")
    ftpproxyaddress = models.CharField(max_length=120, verbose_name="Address")
    ftpproxyport = models.CharField(max_length=120, verbose_name="Port")
    ftpproxyauth = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default="OFF", verbose_name="FTP Authentication")

## System|Advanced|Swap
class systemAdvancedSwap(models.Model):
    swapmemory = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default="OFF", verbose_name="Swap Memory")
    swaptype = models.CharField(max_length=120, choices=SWAPTYPE_CHOICES, verbose_name="Swap Type")
    # mountpoint info goes here
    mountpoint = models.CharField(max_length=120, choices=MOUNTPOINT_CHOICES, verbose_name="Mount point")
    swapsize = models.CharField(max_length=120, verbose_name="Size")

## Command Scripts
class CommandScripts(models.Model):
    command = models.CharField(max_length=120, verbose_name="Command")
    commandtype = models.CharField(max_length=120, choices=COMMANDSCRIPT_CHOICES, verbose_name="Type")

## System|Advanced|Command scripts
class systemAdvancedCommandScripts(models.Model):
    commandscripts = models.ForeignKey(CommandScripts, verbose_name="Command") 

class whoChoices:
    """Populate a list of system user choices"""
    def __init__(self):
        # This doesn't work right, lol
        pipe = popen("pw usershow -a | cut -d: -f1")
        self._wholist = pipe.read().strip().split('\n')
        self.max_choices = len(self._wholist)

    def __iter__(self):
        return iter((i, i) for i in self._wholist)

## System|Advanced|Cron
class cronjob(models.Model):
    togglecron = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Cron")
    croncommand = models.CharField(max_length=120, verbose_name="Command")
    cronwho = models.CharField(max_length=120, choices=whoChoices(), default="root", verbose_name="Who")
    description = models.CharField(max_length=120, verbose_name="Description", blank=True)
    ToggleMinutes = models.CharField(max_length=120, choices=TOGGLECRON_CHOICES, default="Selected", verbose_name="Minutes")
    Minutes1 = models.CharField(max_length=120, choices=MINUTES1_CHOICES, default="(NONE)", verbose_name="")
    Minutes2 = models.CharField(max_length=120, choices=MINUTES2_CHOICES, default="(NONE)", verbose_name="")
    Minutes3 = models.CharField(max_length=120, choices=MINUTES3_CHOICES, default="(NONE)", verbose_name="")
    Minutes4 = models.CharField(max_length=120, choices=MINUTES4_CHOICES, default="(NONE)", verbose_name="")
    ToggleHours = models.CharField(max_length=120, choices=TOGGLECRON_CHOICES, default="Selected", verbose_name="Hours")
    Hours1 = models.CharField(max_length=120, choices=HOURS1_CHOICES, default="(NONE)", verbose_name="")
    Hours2 = models.CharField(max_length=120, choices=HOURS2_CHOICES, default="(NONE)", verbose_name="")
    ToggleDays = models.CharField(max_length=120, choices=TOGGLECRON_CHOICES, default="Selected", verbose_name="Days")
    Days1 = models.CharField(max_length=120, choices=DAYS1_CHOICES, default="(NONE)", verbose_name="")
    Days2 = models.CharField(max_length=120, choices=DAYS2_CHOICES, default="(NONE)", verbose_name="")
    Days3 = models.CharField(max_length=120, choices=DAYS3_CHOICES, default="(NONE)", verbose_name="")
    ToggleMonths = models.CharField(max_length=120, choices=TOGGLECRON_CHOICES, default="Selected", verbose_name="Months")
    Months = models.CharField(max_length=120, choices=MONTHS_CHOICES, default="(NONE)", verbose_name="")
    ToggleWeekdays = models.CharField(max_length=120, choices=TOGGLECRON_CHOICES, default="Selected", verbose_name="")
    Weekdays = models.CharField(max_length=120, choices=WEEKDAYS_CHOICES, default="(NONE)", verbose_name="Weekdays")
class systemAdvancedCron(models.Model):
    cronjob = models.ForeignKey(cronjob, verbose_name="Cron job") 

## System|Advanced|rc.conf
class rcconf(models.Model):
    varname = models.CharField(max_length=120, verbose_name="Name")
    varvalue = models.CharField(max_length=120, verbose_name="Value")
    varcomment = models.CharField(max_length=120, verbose_name="Comment")
class systemAdvancedRCconf(models.Model):
    rcvariable = models.ForeignKey(rcconf, verbose_name="Variable") 

## System|Advanced|sysctl.conf
class sysctlMIB(models.Model):
    MIBname = models.CharField(max_length=120, verbose_name="Name")
    MIBvalue = models.CharField(max_length=120, verbose_name="Value")
    MIBcomment = models.CharField(max_length=120, verbose_name="Comment")
class systemAdvancedSYSCTLconf(models.Model):
    sysctlMIB = models.ForeignKey(sysctlMIB, verbose_name="sysctl") 

###  END System|Advanced ###

## Network|Interface Management
class NICChoices:
    """Populate a list of NIC choices"""
    def __init__(self):
        pipe = popen("/sbin/ifconfig -l")
        self._NIClist = pipe.read().strip().split(' ')
        self.max_choices = len(self._NIClist)

    def __iter__(self):
        return iter((i, i) for i in self._NIClist)

class networkInterfaceMGMT(models.Model):
    interface = models.CharField(max_length=300, choices=NICChoices(), blank=False, verbose_name="NIC",
            help_text="Pick your NIC")
    name = models.CharField(max_length="120", verbose_name="Interface Name",
            help_text="Name your NIC.")
    ipv4address = models.CharField(max_length=18, verbose_name="IPv4 Address", blank=True)
    ipv6address = models.CharField(max_length=42, verbose_name="IPv6 Address", blank=True)
    options = models.CharField(max_length=120, verbose_name="Options", blank=True)

    def __unicode__(self):
        return self.name + " - " + self.interface

    class Meta:
        verbose_name = "Interfaces"

## Network|Hosts
class networkHosts(models.Model):
    interface = models.ForeignKey(networkInterfaceMGMT, verbose_name="Interface")
    #hostac = models.TextField(max_length=120, verbose_name="Host access control")
    
    def __unicode__(self):
        return self.interface

    class Meta:
        verbose_name = "Host"

## Network|Interface Management|VLAN
class networkVLAN(models.Model):
    vint = models.CharField(max_length=120, verbose_name="Virtual Interface")
    pint = models.CharField(max_length=300, choices=NICChoices(), blank=False, verbose_name="Physical Interface")
    tag = models.CharField(max_length=120, verbose_name="VLAN Tag")
    description = models.CharField(max_length=120, verbose_name="Description", blank=True)
    
    def __unicode__(self):
        return self.vint

    class Meta:
        verbose_name = "VLAN"

class networkInterfaceMGMTvlan(models.Model):
    vlanlist = models.ForeignKey(networkVLAN, verbose_name="VLAN")
    
    def __unicode__(self):
        return self.vlanlist

    class Meta:
        verbose_name = "VLAN"

class networkLAGG(models.Model):
    vint = models.CharField(max_length=120, verbose_name="Virtual Interface")
    ports = models.CharField(max_length=120, verbose_name="Ports")
    description = models.CharField(max_length=120, verbose_name="Description", blank=True)
    
    def __unicode__(self):
        return self.vint

    class Meta:
        verbose_name = "LAGG"

class networkInterfaceMGMTlagg(models.Model):
    lagglist = models.ForeignKey(networkLAGG, verbose_name="LAGG")
    
    def __unicode__(self):
        return self.laglist

    class Meta:
        verbose_name = "LAGG"




class StaticRoutes(models.Model):
    interface = models.ForeignKey(networkInterfaceMGMT, verbose_name="Interface")
    destination = models.CharField(max_length=120, verbose_name="Destination network")
    gateway = models.CharField(max_length=120, verbose_name="Gateway")
    description = models.CharField(max_length=120, verbose_name="Description", blank=True)
    
    def __unicode__(self):
        return self.destination

    class Meta:
        verbose_name = "Static Routes"

class networkStaticRoutes(models.Model):
    staticroutes = models.ForeignKey(StaticRoutes, verbose_name="Static Route")
    
    def __unicode__(self):
        return self.staticroutes

    class Meta:
        verbose_name = "Static Routes"
    
## Disks|Management
TRANSFERMODE_CHOICES = (
        ('Auto', 'Auto'),
        ('PIO0', 'PIO0'),
        ('PIO1', 'PIO1'),
        ('PIO2', 'PIO2'),
        ('PIO3', 'PIO3'),
        ('PIO4', 'PIO4'),
        ('WDMA2', 'WDMA2'),
        ('UDMA-33', 'UDMA-33'),
        ('UDMA-66', 'UDMA-66'),
        ('UDMA-100', 'UDMA-133'),
        ('UDMA-100', 'UDMA-133'),
        )
HDDSTANDBY_CHOICES = (
        ('Always On', 'Always On'),
        ('5', '5'),
        ('10', '10'),
        ('20', '20'),
        ('30', '30'),
        ('60', '60'),
        ('120', '120'),
        ('180', '180'),
        ('240', '240'),
        ('300', '300'),
        ('360', '360'),
        )
ADVPOWERMGMT_CHOICES = (
        ('Disabled', 'Disabled'),
        ('1', 'Level 1 - Minimum power usage with Standby (spindown)'),
        ('64', 'Level 64 - Intermediate power usage with Standby'),
        ('127', 'Level 127 - Intermediate power usage with Standby'),
        ('128', 'Level 128 - Minimum power usgae without Standby (no spindown)'),
        ('192', 'Level 192 - Intermediate power usage withot Standby'),
        ('254', 'Level 254 - Maximum performance, maximum power usage'),
        )
ACOUSTICLVL_CHOICES = (
        ('Disabled', 'Disabled'),
        ('Minimum', 'Minimum'),
        ('Medium', 'Medium'),
        ('Maximum', 'Maximum'),
        )

class DiskChoices:
    """Populate a list of disk choices"""
    def __init__(self):
        pipe = popen("/sbin/sysctl -n kern.disks")
        self._disklist = pipe.read().strip().split(' ')
        self.max_choices = len(self._disklist)

    def __iter__(self):
        return iter((i, i) for i in self._disklist)





""" Disk and Volume Management """

class Disk(models.Model):
    name = models.CharField(max_length=120, verbose_name="Name")
    disks = models.CharField(max_length=120, choices=DiskChoices(),verbose_name="Disks")
    description = models.CharField(max_length=120, verbose_name="Description", blank=True)
    sort_order = models.IntegerField(_('sort order'), default=0, help_text='The order in which disks will be displayed.')

    class Meta:
        verbose_name = "Disk"
        ordering = ['sort_order',]

    def __unicode__(self):
        return self.disks + ' (' + self.name + ')'

    def save(self, *args, **kwargs):
        super(Disk, self).save(*args, **kwargs)

class DiskAdvanced(Disk):
    transfermode = models.CharField(max_length=120, choices=TRANSFERMODE_CHOICES, default="Auto", verbose_name="Transfer Mode")
    hddstandby = models.CharField(max_length=120, choices=HDDSTANDBY_CHOICES, default="Always On", verbose_name="HDD Standby")
    advpowermgmt = models.CharField(max_length=120, choices=ADVPOWERMGMT_CHOICES, default="Disabled", verbose_name="Advanced Power Management")
    acousticlevel = models.CharField(max_length=120, choices=ACOUSTICLVL_CHOICES, default="Disabled", verbose_name="Acoustic Level")
    togglesmart = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default="ON", verbose_name="S.M.A.R.T.")
    smartoptions = models.CharField(max_length=120, verbose_name="S.M.A.R.T. extra options", blank=True)
    def __unicode__(self):
        return Disk.disk

    class Meta:
        verbose_name = "Disk"

GroupType_Choices = (
        ('single', 'single disk'),
        ('raidz', 'raidz'),
        ('mirror', 'mirror'),
        )
class DiskGroup(models.Model):
    name = models.CharField(max_length=120, verbose_name="Name")
    type = models.CharField(max_length=120, choices=GroupType_Choices, default="(NONE)", verbose_name="Group Type")
    members = models.ManyToManyField(Disk)
    
    def __unicode__(self):
        return self.name

""" End Disk Management """

""" Volume Management """
VolumeType_Choices = (
        ('ufs', 'ufs'),
        ('zfs', 'zfs'),
        )
class Volume(models.Model):
    name = models.CharField(max_length=120, verbose_name="Name")
    type = models.CharField(max_length=120, choices=VolumeType_Choices, default="(NONE)", verbose_name="Filesystem")
    mountpoint = models.CharField(max_length=120, verbose_name="Mount Point")
    group = models.ManyToManyField(DiskGroup)
    
    class Meta:
        verbose_name = "Volume"

    def __unicode__(self):
        return self.name + ' (' + self.type + ')'

    def save(self, *args, **kwargs):
        super(Volume, self).save(*args, **kwargs)
    

zpool_Choices = (
        ('disk', 'disk'),
        ('mirror', 'mirror'),
        ('raidz1', 'raidz1'),
        ('raidz2', 'raidz2'),
        ('spare', 'spare'),
        ('log', 'log'),
        ('cache', 'cache'),
        )
SingleDisk_Choices = (
        ('ufs', 'UFS'),
        )
class zpool(models.Model):
    zpool = models.CharField(max_length=120, choices=zpool_Choices, verbose_name="zfs")
class SingleDisk(models.Model):
    fs = models.CharField(max_length=120, choices=SingleDisk_Choices, verbose_name="Filesystem")



## Services|CIFS/SMB|Settings
CIFSAUTH_CHOICES = (
        ('Anonymous', 'Anonymous'),
        ('Local User', 'Local User'),
        ('Domain', 'Domain'),
        )
DOSCHARSET_CHOICES = (
        ('CP437', 'CP437'),
        ('CP850', 'CP850'),
        ('CP852', 'CP852'),
        ('CP866', 'CP866'),
        ('CP932', 'CP932'),
        ('CP1251', 'CP1251'),
        ('ASCII', 'ASCII'),
        )
UNIXCHARSET_CHOICES = (
        ('UTF-8', 'UTF-8'),
        ('iso-8859-1', 'iso-8859-1'),
        ('iso-8859-15', 'iso-8859-15'),
        ('gb2312', 'gb2312'),
        ('EUC-JP', 'EUC-JP'),
        ('ASCII', 'ASCII'),
        )
LOGLEVEL_CHOICES = (
        ('Minimum', 'Minimum'),
        ('Normal', 'Normal'),
        ('Full', 'Full'),
        ('Debug', 'Debug'),
        )

class servicesCIFS(models.Model):
    togglecifs = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="CIFS")
    netbiosname = models.CharField(max_length=120, verbose_name="NetBIOS name")
    workgroup = models.CharField(max_length=120, verbose_name="Workgroup",
            help_text="Workgroup the server will appear to be in when queried by clients (maximum 15 characters).")
    description = models.CharField(max_length=120, verbose_name="Description", blank=True,
            help_text="Server description. This can usually be left blank.")
    doscharset = models.CharField(max_length=120, choices=DOSCHARSET_CHOICES, default="CP437", verbose_name="DOS charset")
    unixcharset = models.CharField(max_length=120, choices=UNIXCHARSET_CHOICES, default="UTF-8", verbose_name="UNIX charset")
    loglevel = models.CharField(max_length=120, choices=LOGLEVEL_CHOICES, default="Minimum", verbose_name="Log level")
    localmaster = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='ON', verbose_name="Local Master Browser",
            help_text="Allows FreeNAS to try and become a local master browser.")
    timeserver = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='ON', verbose_name="Time Server",
            help_text="FreeNAS advertises itself as a time server to Windows clients.")
    guest = models.CharField(max_length=120, choices=whoChoices(), default="www", verbose_name="Guest account", 
            help_text="Use this option to override the username ('ftp' by default) which will be used for access to services which are specified as guest. Whatever privileges this user has will be available to any client connecting to the guest service. This user must exist in the password file, but does not require a valid login.")
    filemask = models.CharField(max_length=120, verbose_name="File mask", blank=True,
            help_text="Use this option to override the file creation mask (0666 by default).")
    dirmask = models.CharField(max_length=120, verbose_name="Directory mask", blank=True,
            help_text="Use this option to override the directory creation mask (0777 by default).")
    sendbuffer = models.CharField(max_length=120, verbose_name="Send Buffer Size", blank=True,
            help_text="Size of send buffer (64240 by default).")
    recbuffer = models.CharField(max_length=120, verbose_name="Receive Buffer Size", blank=True,
            help_text="Size of receive buffer (64240 by default).")
    largerw = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="large read/write",
            help_text="Use the new 64k streaming read and write varient SMB requests introduced with Windows 2000.")
    sendfile = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='ON', verbose_name="sendfile",
            help_text="This may make more efficient use of the system CPU's and cause Samba to be faster. Samba automatically turns this off for clients that use protocol levels lower than NT LM 0.12 and when it detects a client is Windows 9x.")
    easupport = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="EA support",
            help_text="Allow clients to attempt to store OS/2 style extended attributes on a share.")
    dosattr = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='ON', verbose_name="Store DOS attributes",
            help_text="If this parameter is set, Samba attempts to first read DOS attributes (SYSTEM, HIDDEN, ARCHIVE or READ-ONLY) from a filesystem extended attribute, before mapping DOS attributes to UNIX permission bits. When set, DOS attributes will be stored onto an extended attribute in the UNIX filesystem, associated with the file or directory.")
    nullpw = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="null password",
            help_text="Allow client access to accounts that have null passwords.")
    auxsmbconf = models.TextField(max_length=120, verbose_name="Auxiliary paramters", blank=True,
            help_text="These parameters are added to [Global] section of smb.conf")

class shareCIFS(models.Model):
    name = models.CharField(max_length=120, verbose_name="Name")
    comment = models.CharField(max_length=120, verbose_name="Comment")
    path = models.CharField(max_length=120, verbose_name="Path",
            help_text="Path to be shared")
    ro = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Read Only",
            help_text="If enabled, users may not create or modify files in the share.")
    browseable = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='ON', verbose_name="Browsable",
            help_text="This controls whether this share is seen in the list of available shares in a net view and in the browse list.")
    inheritperms = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='ON', verbose_name="Inherit permissions",
            help_text="The permissions on new files and directories are normally governed by create mask and directory mask but the inherit permissions parameter overrides this. This can be particularly useful on systems with many users to allow a single share to be used flexibly by each user.")
    recyclebin = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Recycling bin",
            help_text="This will create a recycle bin on the share.")
    showhiddenfiles = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='ON', verbose_name="Show Hidden Files",
            help_text="Controls whether files starting with a dot are shown to the user.")
    hostsallow = models.CharField(max_length=120, blank=True, verbose_name="Hosts allow",
            help_text="This option is a comma, space, or tab delimited set of hosts which are permitted to access this share. You can specify the hosts by name or IP number. Leave this field empty to use default settings.")
    hostsdeny = models.CharField(max_length=120, blank=True, verbose_name="Hosts deny",
            help_text="This option is a comma, space, or tab delimited set of host which are NOT permitted to access this share. Where the lists conflict, the allow list takes precedence. In the event that it is necessary to deny all by default, use the keyword ALL (or the netmask 0.0.0.0/0) and then explicitly specify to the hosts allow parameter those hosts that should be permitted access. Leave this field empty to use default settings.")
    auxsmbconf = models.TextField(max_length=120, verbose_name="Auxiliary paramters", blank=True,
            help_text="These parameters are added to [Share] section of smb.conf")
    
    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = "Share"

class servicesCIFSshare(models.Model):
    share = models.ForeignKey(shareCIFS, verbose_name="Share")
    
    def __unicode__(self):
        return self.share

    class Meta:
        verbose_name = "Share"


class servicesFTP(models.Model):            
    toggleFTP = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="FTP")
    clients = models.CharField(max_length=120, verbose_name="Clients",
            help_text="Maximum number of simultaneous clients.")
    ipconnections = models.CharField(max_length=120, verbose_name="Connections",
            help_text="Maximum number of connections per IP address (0 = unlimited).")
    loginattempt = models.CharField(max_length=120, verbose_name="Login Attempts",
            help_text="Maximum number of allowed password attempts before disconnection.")
    timeout = models.CharField(max_length=120, verbose_name="Timeout",
            help_text="Maximum idle time in seconds.")
    rootlogin = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="root login",
            help_text="Specifies whether it is allowed to login as superuser (root) directly. ")
    onlyanonymous = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Anonymous users only",
            help_text="Only allow anonymous users. Use this on a public FTP site with no remote FTP access to real accounts. ")
    onlylocal = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Local users only",
            help_text="Only allow authenticated users. Anonymous logins are prohibited. ")
    banner = models.TextField(max_length=120, verbose_name="Banner", blank=True,
            help_text="Greeting banner displayed by FTP when a connection first comes in.")
    filemask = models.CharField(max_length=120, verbose_name="File mask",
            help_text="Use this option to override the file creation mask (077 by default).")
    dirmask = models.CharField(max_length=120, verbose_name="Directory mask",
            help_text="Use this option to override the file creation mask (077 by default).")
    fxp = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="FXP",
            help_text="FXP allows transfers between two remote servers without any file data going to the client asking for the transfer (insecure!).")
    resume = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Resume",
            help_text="Allow clients to resume interrupted uploads and downloads. ")
    defaultroot = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Default root",
            help_text="If default root is enabled, a chroot operation is performed immediately after a client authenticates. This can be used to effectively isolate the client from a portion of the host system filespace.")
    ident = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Ident protocol",
            help_text="When a client initially connects to the server the ident protocol is used to attempt to identify the remote username.")
    reversedns = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Reverse DNS lookup",
            help_text="Enable reverse DNS lookup performed on the remote host's IP address for incoming active mode data connections and outgoing passive mode data connections.")
    masqaddress = models.CharField(max_length=120, verbose_name="Masquerade address",
            help_text="Causes the server to display the network information for the specified IP address or DNS hostname to the client, on the assumption that that IP address or DNS host is acting as a NAT gateway or port forwarder for the server.")
    passiveportsimin = models.CharField(max_length=120, verbose_name="Passive ports",
            help_text="The minimum port to allocate for PASV style data connections (0 = use any port).")
    passiveportsmax = models.CharField(max_length=120, verbose_name="Passive ports",
            help_text="The maximum port to allocate for PASV style data connections (0 = use any port). Passive ports restricts the range of ports from which the server will select when sent the PASV command from a client. The server will randomly choose a number from within the specified range until an open port is found. The port range selected must be in the non-privileged range (eg. greater than or equal to 1024). It is strongly recommended that the chosen range be large enough to handle many simultaneous passive connections (for example, 49152-65534, the IANA-registered ephemeral port range).")
    localuserbw = models.CharField(max_length=120, verbose_name="User bandwidth",
            help_text="Local user upload bandwith in KB/s. An empty field means infinity.")
    localuserdlbw = models.CharField(max_length=120, verbose_name="Download bandwidth",
            help_text="Local user download bandwith in KB/s. An empty field means infinity.")
    anonuserbw = models.CharField(max_length=120, verbose_name="Download bandwidth",
            help_text="Anonymous user upload bandwith in KB/s. An empty field means infinity.")
    anonuserdlbw = models.CharField(max_length=120, verbose_name="Download bandwidth",
            help_text="Anonymous user download bandwith in KB/s. An empty field means infinity.")
    ssltls = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="root login",
            help_text="Enable TLS/SSL connections. ")
    auxparams = models.TextField(max_length=120, verbose_name="Banner", blank=True,
            help_text="These parameters are added to proftpd.conf.")
    
class servicesTFTP(models.Model):            
    toggleTFTP = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="TFTP")
    directory = models.CharField(max_length=120, verbose_name="Directory",
            help_text="The directory containing the files you want to publish. The remote host does not need to pass along the directory as part of the transfer.")
    newfiles = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="New Files")
    port = models.CharField(max_length=120, verbose_name="Port",
            help_text="The port to listen to. The default is to listen to the tftp port specified in /etc/services.")
    username = models.CharField(max_length=120, choices=whoChoices(), default="nobody", verbose_name="Username", 
            help_text="Specifies the username which the service will run as.")
    umask = models.CharField(max_length=120, verbose_name="umask",
            help_text="Set the umask for newly created files to the specified value. The default is 022 (everyone can read, nobody can write).")
    options = models.CharField(max_length=120, verbose_name="Extra options",
	    blank=True, help_text="Extra command line options (usually empty).")

class servicesSSH(models.Model):            
    toggleSSH = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="SSH")
    tcpport = models.CharField(max_length=120, verbose_name="TCP Port",
            help_text="Alternate TCP port. Default is 22")
    rootlogin = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="root login",
            help_text="Specifies whether it is allowed to login as superuser (root) directly.")
    passwordauth = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Password authentication",
            help_text="Enable keyboard-interactive authentication.")
    tcpfwd = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="TCP Forwarding",
            help_text="Allow SSH tunnels.")
    compression = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Compression",
            help_text="Compression is worth using if your connection is slow. The efficiency of the compression depends on the type of the file, and varies widely. Useful for internet transfer only.")
    privatekey = models.TextField(max_length=120, verbose_name="Private Key",
            help_text="Paste a DSA PRIVATE KEY in PEM format here.")
    opions = models.TextField(max_length=120, verbose_name="Banner", blank=True,
            help_text="Extra options to /etc/ssh/sshd_config (usually empty). Note, incorrect entered options prevent SSH service to be started.")
    
class servicesNFS(models.Model):            
    toggleNFS = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="NFS")
    servers = models.CharField(max_length=120, verbose_name="Number of servers",
            help_text="Specifies how many servers to create. There should be enough to handle the maximum level of concurrency from its clients, typically four to six.")
class shareNFS(models.Model):
    path = models.CharField(max_length=120, verbose_name="Path",
            help_text="Path to be shared. Please note that blanks in path names are not allowed.")
    allroot = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Map users to root",
            help_text="All users will have the root privilege.")
    network = models.CharField(max_length=120, verbose_name="Authorized network",
            help_text="Network that is authorised to access the NFS share.")
    comment = models.CharField(max_length=120, verbose_name="Comment")
    alldirs = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="All directories",
            help_text="Share all sub directories.")
    readonly = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Read only",
            help_text="Specifies that the file system should be exported read-only.")
    quiet = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Quiet",
            help_text="Inhibit some of the syslog diagnostics for bad lines in /etc/exports.")
    
    def __unicode__(self):
        return self.path

    class Meta:
        verbose_name = "Share"

class servicesNFSshare(models.Model):
    share = models.ForeignKey(shareNFS, verbose_name="Share")
    
    def __unicode__(self):
        return self.share

    class Meta:
        verbose_name = "Share"
class servicesAFP(models.Model):            
    toggleAFP = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="AFP")
    name = models.CharField(max_length=120, verbose_name="Server Name",
            help_text="Name of the server. If this field is left empty the default server is specified.")
    guest = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Guest access",
        help_text="Enable guest access.")
    local = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Local access",
        help_text="Enable local user authentication. ")
    ddp = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="DDP",
            help_text="DDP connections, enabled by default")
DISKDISCOVERY_CHOICES = (
        ('default', 'Default'),
        ('time machine', 'Time Machine'),
        )
CASEFOLDING_CHOICES = (
        ('none', 'No case folding'),
        ('lowercaseboth', 'Lowercase names in both directions'),
        ('uppercaseboth', 'Lowercase names in both directions'),
        ('lowercaseclient', 'Client sees lowercase, server sees uppercase'),
        ('uppercaseclient', 'Client sees uppercase, server sees lowercase'),
        )
class shareAFP(models.Model):
    name = models.CharField(max_length=120, verbose_name="Name")
    path = models.CharField(max_length=120, verbose_name="Path",
            help_text="Path to be shared.")
    comment = models.CharField(max_length=120, verbose_name="Name")
    sharepw = models.CharField(max_length=120, verbose_name="Share password",
        help_text="This controls the access to this share with an access password.")
    sharecharset = models.CharField(max_length=120, verbose_name="Share character set",
        help_text="Specifies the share character set. For example UTF8, UTF8-MAC, ISO-8859-15, etc.")
    allow = models.CharField(max_length=120, verbose_name="Allow",
        help_text="This option allows the users and groups that access a share to be specified. Users and groups are specified, delimited by commas. Groups are designated by a @ prefix.")
    deny = models.CharField(max_length=120, verbose_name="Allow",
        help_text="The deny option specifies users and groups who are not allowed access to the share. It follows the same format as the allow option.")
    roaccess = models.CharField(max_length=120, verbose_name="Read-only access",
        help_text="Allows certain users and groups to have read-only access to a share. This follows the allow option format.")
    rwaccess = models.CharField(max_length=120, verbose_name="Read-only access",
        help_text="Allows certain users and groups to have read/write access to a share. This follows the allow option format. ")
    diskdiscovery = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Automatic Disk Discovery")
    discoverymode = models.CharField(max_length=120, choices=DISKDISCOVERY_CHOICES, default='Default', verbose_name="Disk discovery mode",
            help_text="Note! Selecting 'Time Machine' on multiple shares will may cause unpredictable behavior in MacOS.")
    dbpath = models.CharField(max_length=120, verbose_name="Path",
            help_text="Path to be shared.")
    cachecnid = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF',
            help_text="If set afpd uses the ID information stored in AppleDouble V2 header files to reduce database load. Don't set this option if the volume is modified by non AFP clients (NFS/SMB/local).")
    crlf = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', 
            help_text="crlf translation for TEXT files, automatically converting macintosh line breaks into Unix ones. Use of this option might be dangerous since some older programs store binary data files as type 'TEXT' when saving and switch the filetype in a second step. Afpd will potentially destroy such files when 'erroneously' changing bytes in order to do line break translation.")
    mswindows = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', 
            help_text="This forces filenames to be restricted to the character set used by Windows. This is not recommended for shares used principally by Mac computers.")
    noadouble = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', 
            help_text="This controls whether the .AppleDouble directory gets created unless absolutely needed. This option should not be used if files are access mostly by Mac computers.")
    nodev = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF',
            help_text="use 0 for device number, helps when the device number is not constant across a reboot, cluster, ...")
    nofileid = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF',
            help_text="advertise createfileid, resolveid, deleteid calls.")
    nohex = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', 
            help_text="hex translations for anything except dot files. Disabling this option makes the '/' character illegal.")
    prodos = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF',
            help_text="Provides compatibility with Apple II clients.")
    nostat = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF',
            help_text="stat volume path when enumerating volumes list, useful for automounting or volumes created by a preexec script.")
    upriv = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', 
            help_text="Use AFP3 unix privileges.")
    
    def __unicode__(self):
        return self.path

    class Meta:
        verbose_name = "Share"

class servicesAFPshare(models.Model):
    share = models.ForeignKey(shareAFP, verbose_name="Share")
    
    def __unicode__(self):
        return self.share

    class Meta:
        verbose_name = "Share"
class clientrsyncjob(models.Model):
    localshare = models.CharField(max_length=120, verbose_name="Local Share",
            help_text="Path to be shared.")
    remoteserver = models.CharField(max_length=120, verbose_name="Remote RSYNC server",
            help_text="IP or FQDN address of remote Rsync server.")
    who = models.CharField(max_length=120, choices=whoChoices(), default="root", verbose_name="Who")
    description = models.CharField(max_length=120, verbose_name="Description", blank=True)
    ToggleMinutes = models.CharField(max_length=120, choices=TOGGLECRON_CHOICES, default="Selected", verbose_name="Minutes")
    Minutes1 = models.CharField(max_length=120, choices=MINUTES1_CHOICES, default="(NONE)", verbose_name="")
    Minutes2 = models.CharField(max_length=120, choices=MINUTES2_CHOICES, default="(NONE)", verbose_name="")
    Minutes3 = models.CharField(max_length=120, choices=MINUTES3_CHOICES, default="(NONE)", verbose_name="")
    Minutes4 = models.CharField(max_length=120, choices=MINUTES4_CHOICES, default="(NONE)", verbose_name="")
    ToggleHours = models.CharField(max_length=120, choices=TOGGLECRON_CHOICES, default="Selected", verbose_name="Hours")
    Hours1 = models.CharField(max_length=120, choices=HOURS1_CHOICES, default="(NONE)", verbose_name="")
    Hours2 = models.CharField(max_length=120, choices=HOURS2_CHOICES, default="(NONE)", verbose_name="")
    ToggleDays = models.CharField(max_length=120, choices=TOGGLECRON_CHOICES, default="Selected", verbose_name="Days")
    Days1 = models.CharField(max_length=120, choices=DAYS1_CHOICES, default="(NONE)", verbose_name="")
    Days2 = models.CharField(max_length=120, choices=DAYS2_CHOICES, default="(NONE)", verbose_name="")
    Days3 = models.CharField(max_length=120, choices=DAYS3_CHOICES, default="(NONE)", verbose_name="")
    ToggleMonths = models.CharField(max_length=120, choices=TOGGLECRON_CHOICES, default="Selected", verbose_name="Months")
    Months = models.CharField(max_length=120, choices=MONTHS_CHOICES, default="(NONE)", verbose_name="")
    ToggleWeekdays = models.CharField(max_length=120, choices=TOGGLECRON_CHOICES, default="Selected", verbose_name="")
    Weekdays = models.CharField(max_length=120, choices=WEEKDAYS_CHOICES, default="(NONE)", verbose_name="Weekdays")
    recursive = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='ON', verbose_name="Recursive",
            help_text="Recurse into directories.")
    times = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='ON', verbose_name="Times",
            help_text="Preserve modification times. ")
    compress = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='ON', verbose_name="Compress",
            help_text="Compress file data during the transfer.")
    archive = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Archive",
            help_text="Archive mode.")
    delete = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Delete",
            help_text="Delete files on the receiving side that don't exist on sender.")
    quiet = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Quiet",
            help_text="Suppress non-error messages.")
    preserveperms = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Preserve Permissions",
            help_text="This option causes the receiving rsync to set the destination permissions to be the same as the source permissions.")
    extattr = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Extended attributes",
            help_text="This option causes rsync to update the remote extended attributes to be the same as the local ones.")
    options = models.CharField(max_length=120, verbose_name="Extra options",
            help_text="Extra options to rsync (usually empty).")
class localrsyncjob(models.Model):
    sourceshare = models.CharField(max_length=120, verbose_name="Source Share",
            help_text="Source directory to be synchronized.")
    destinationshare = models.CharField(max_length=120, verbose_name="Destination Share",
            help_text="Target directory.")
    who = models.CharField(max_length=120, choices=whoChoices(), default="root", verbose_name="Who")
    description = models.CharField(max_length=120, verbose_name="Description", blank=True)
    ToggleMinutes = models.CharField(max_length=120, choices=TOGGLECRON_CHOICES, default="Selected", verbose_name="Minutes")
    Minutes1 = models.CharField(max_length=120, choices=MINUTES1_CHOICES, default="(NONE)", verbose_name="")
    Minutes2 = models.CharField(max_length=120, choices=MINUTES2_CHOICES, default="(NONE)", verbose_name="")
    Minutes3 = models.CharField(max_length=120, choices=MINUTES3_CHOICES, default="(NONE)", verbose_name="")
    Minutes4 = models.CharField(max_length=120, choices=MINUTES4_CHOICES, default="(NONE)", verbose_name="")
    ToggleHours = models.CharField(max_length=120, choices=TOGGLECRON_CHOICES, default="Selected", verbose_name="Hours")
    Hours1 = models.CharField(max_length=120, choices=HOURS1_CHOICES, default="(NONE)", verbose_name="")
    Hours2 = models.CharField(max_length=120, choices=HOURS2_CHOICES, default="(NONE)", verbose_name="")
    ToggleDays = models.CharField(max_length=120, choices=TOGGLECRON_CHOICES, default="Selected", verbose_name="Days")
    Days1 = models.CharField(max_length=120, choices=DAYS1_CHOICES, default="(NONE)", verbose_name="")
    Days2 = models.CharField(max_length=120, choices=DAYS2_CHOICES, default="(NONE)", verbose_name="")
    Days3 = models.CharField(max_length=120, choices=DAYS3_CHOICES, default="(NONE)", verbose_name="")
    ToggleMonths = models.CharField(max_length=120, choices=TOGGLECRON_CHOICES, default="Selected", verbose_name="Months")
    Months = models.CharField(max_length=120, choices=MONTHS_CHOICES, default="(NONE)", verbose_name="")
    ToggleWeekdays = models.CharField(max_length=120, choices=TOGGLECRON_CHOICES, default="Selected", verbose_name="")
    Weekdays = models.CharField(max_length=120, choices=WEEKDAYS_CHOICES, default="(NONE)", verbose_name="Weekdays")
    recursive = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='ON', verbose_name="Recursive",
            help_text="Recurse into directories.")
    times = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='ON', verbose_name="RSYNC",
            help_text="Preserve modification times. ")
    compress = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='ON', verbose_name="RSYNC",
            help_text="Compress file data during the transfer.")
    archive = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="RSYNC",
            help_text="Archive mode.")
    delete = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="RSYNC",
            help_text="Delete files on the receiving side that don't exist on sender.")
    quiet = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="RSYNC",
            help_text="Suppress non-error messages.")
    preserveperms = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="RSYNC",
            help_text="This option causes the receiving rsync to set the destination permissions to be the same as the source permissions.")
    extattr = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="RSYNC",
            help_text="This option causes rsync to update the remote extended attributes to be the same as the local ones.")
    options = models.CharField(max_length=120, verbose_name="Extra options",
            help_text="Extra options to rsync (usually empty).")
class servicesRSYNC(models.Model):            
    togglersync = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="RSYNC")
    clientrsync = models.ForeignKey(clientrsyncjob, verbose_name="Client RSYNC jobs") 
    localrsync = models.ForeignKey(localrsyncjob, verbose_name="Local RSYNC jobs") 

class servicesUnison(models.Model):            
    toggleUnison = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Unison")
    workingdir = models.CharField(max_length=120, verbose_name="Working directory")
    createworkingdir = models.BooleanField(max_length=120, verbose_name="",
            help_text="Create working directory if one doesn't exist. ")

"""
iSCSI Target
"""
DISCOVERYAUTHMETHOD_CHOICES = (
        ('auto', 'Auto'),
        ('chap', 'CHAP'),
        ('mchap', 'Mutual CHAP'),
        )
DISCOVERYAUTHGROUP_CHOICES = (
        ('none', 'None'),
        )

class servicesiSCSITarget(models.Model):            
    toggleiSCSITarget = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="iSCSI Target")
    basename = models.CharField(max_length=120, verbose_name="Base Name",
            help_text="The base name (e.g. iqn.2007-09.jp.ne.peach.istgt) will append the target name that is not starting with 'iqn.' ")
    discoveryauthmethod = models.CharField(max_length=120, choices=DISCOVERYAUTHMETHOD_CHOICES, default='auto', verbose_name="Discovery Auth Method")
    discoveryauthgroup = models.CharField(max_length=120, choices=DISCOVERYAUTHGROUP_CHOICES, default='none', verbose_name="Discovery Auth Group")
    io = models.CharField(max_length=120, verbose_name="I/O Timeout",
            help_text="I/O timeout in seconds (30 by default).")
    nopinint = models.CharField(max_length=120, verbose_name="NOPIN Interval",
            help_text="NOPIN sending interval in seconds (20 by default).")
    maxsesh = models.CharField(max_length=120, verbose_name="Max. sessions",
            help_text="Maximum number of sessions holding at same time (32 by default).")
    maxconnect = models.CharField(max_length=120, verbose_name="Max. connections",
            help_text="Maximum number of connections in each session (8 by default).")
    firstburst = models.CharField(max_length=120, verbose_name="First burst length",
            help_text="iSCSI initial parameter (65536 by default).")
    maxburst = models.CharField(max_length=120, verbose_name="Max burst length",
            help_text="iSCSI initial parameter (262144 by default).")
    maxrecdata = models.CharField(max_length=120, verbose_name="Max receive data segment length",
            help_text="iSCSI initial parameter (262144 by default).")
    toggleluc = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Logical Unit Controller")


"""
looks like a blocker: skipping for now
--------------------------------------

class servicesUPnP(models.Model):            
    toggleUPnP = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="UPnP")

class servicesiTunesDAAP(models.Model):            
    toggleiTunesDAAP = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="iTunes/DAAP")

"""


DYNDNSPROVIDER_CHOICES = (
        ('dyndns', 'dyndns.org'),
        ('freedns', 'freedns.afraid.org'),
        ('zoneedit', 'zoneedit.com'),
        ('no-ip', 'no-ip.com'),
        ('easydns', 'easydns.com'),
        ('3322', '3322.org'),
        ('Custom', 'Custom'),
        )
SNMP_CHOICES = (
        ('mibll', 'Mibll'),
        ('netgraph', 'Netgraph'),
        ('hostresources', 'Host resources'),
        ('UCD-SNMP-MIB ', 'UCD-SNMP-MIB'),
        )
UPS_CHOICES = (
        ('lowbatt', 'UPC reaches low battery'),
        ('batt', 'UPS goes on battery'),
        )
BTENCRYPT_CHOICES = (
        ('preferred', 'Preferred'),
        ('tolerated', 'Tolerated'),
        ('required', 'Required'),
        )

class servicesDynamicDNS(models.Model):            
    toggleDynamicDNS = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Dyanmic DNS")
    domain = models.CharField(max_length=120, verbose_name="Domain name",
            help_text="A host name alias. This option can appear multiple times, for each domain that has the same IP. Use a space to separate multiple alias names.")
    username = models.CharField(max_length=120, verbose_name="Username")
    password = models.CharField(max_length=120, verbose_name="Password") # need to make this a 'password' field, but not available in django Models 
    updateperiod = models.CharField(max_length=120, verbose_name="Update period")
    fupdateperiod = models.CharField(max_length=120, verbose_name="Forced update period")
    wildcard = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Wildcard", 
            help_text="Toggle domain wildcarding.")
    auxparams = models.TextField(verbose_name="Auxiliary parameters", help_text="These parameters will be added to global settings in inadyn.conf.") 

class servicesSNMP(models.Model):            
    toggleSNMP = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="SNMP")
    location = models.CharField(max_length=120, verbose_name="Location",
            help_text="Location information, e.g. physical location of this system: 'Floor of building, Room xyz'.")
    contact = models.CharField(max_length=120, verbose_name="Contact",
            help_text="Contact information, e.g. name or email of the person responsible for this system: 'admin@email.address'.")
    community = models.CharField(max_length=120, verbose_name="Community",
            help_text="In most cases, 'public' is used here.")
    traps = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Traps",
            help_text="Toggle traps")
    auxparams = models.TextField(verbose_name="Auxiliary parameters", help_text="These parameters will be added to global settings in inadyn.conf.") 

class servicesUPS(models.Model):            
    toggleUPS = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="UPS")
    identifier = models.CharField(max_length=120, verbose_name="Identifier",
            help_text="This name is used to uniquely identify your UPS on this system.")
    driver = models.CharField(max_length=120, verbose_name="Driver",
            help_text="The driver used to communicate with your UPS.")
    port = models.CharField(max_length=120, verbose_name="Port",
            help_text="The serial or USB port where your UPS is connected.")
    auxparams = models.TextField(verbose_name="Auxiliary parameters", help_text="These parameters will be added to global settings in inadyn.conf.") 
    description = models.CharField(max_length=120, verbose_name="Description", blank=True)
    shutdown = models.CharField(max_length=120, choices=UPS_CHOICES, default='batt', verbose_name="Shutdown mode")
    shutdowntimer = models.CharField(max_length=120, verbose_name="Shutdown timer",
            help_text="The time in seconds until shutdown is initiated. If the UPS happens to come back before the time is up the shutdown is canceled.")
    rmonitor = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Remote Monitoring")
    emailnotify = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Email notification")
    toemail = models.CharField(max_length=120, verbose_name="To email",
            help_text="Destination email address. Separate email addresses by semi-colon.")
    subject = models.CharField(max_length=120, verbose_name="To email",
            help_text="The subject of the email. You can use the following parameters for substitution:<br /><ul><li>%d - Date</li><li>%h - Hostname</li></ul>")

class servicesWebserver(models.Model):            
    toggleWebserver = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Webserver")
    protocol = models.CharField(max_length=120, choices=PROTOCOL_CHOICES, default='OFF', verbose_name="Protocol")
    port = models.CharField(max_length=120, verbose_name="Port",
            help_text="TCP port to bind the server to.")
    docroot = models.CharField(max_length=120, verbose_name="Document root",
            help_text="Document root of the webserver. Home of the web page files.")
    auth = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Authentication",
            help_text="only local users access to the web page.")
    dirlisting = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Directory listing",
            help_text="directory listing is generated if a directory is requested and no index-file (index.php, index.html, index.htm or default.htm) was found in that directory.")

class servicesBitTorrent(models.Model):            
    toggleBitTorrent = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Bit Torrent")
    peerport = models.CharField(max_length=120, verbose_name="Peer port",
            help_text="Port to listen for incoming peer connections. Default port is 51413.")
    downloaddir = models.CharField(max_length=120, verbose_name="Download directory",
            help_text="Where to save downloaded data.")
    configdir = models.CharField(max_length=120, verbose_name="Configuration directory",
            help_text="Alternative configuration directory (usually empty)", blank=True)
    portfwd = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Port Forwarding",
            help_text="port forwarding via NAT-PMP or UPnP.")
    pex = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Peer Exchange",
            help_text="peer exchange (PEX).")
    disthash = models.CharField(max_length=120, choices=TOGGLE_CHOICES, default='OFF', verbose_name="Distributed hash table",
            help_text="distributed hash table.")
    encrypt = models.CharField(max_length=120, choices=BTENCRYPT_CHOICES, default='preferred', verbose_name="Encryption",
            help_text="The peer connection encryption mode.", blank=True)
    uploadbw = models.CharField(max_length=120, verbose_name="Upload bandwidth",
            help_text="The maximum upload bandwith in KB/s. An empty field means infinity.", blank=True)
    downloadbw = models.CharField(max_length=120, verbose_name="Download bandwidth",
            help_text="The maximum download bandwith in KiB/s. An empty field means infinity.", blank=True)
    watchdir = models.CharField(max_length=120, verbose_name="Watch directory",
            help_text="Directory to watch for new .torrent files.", blank=True)
    incompletedir = models.CharField(max_length=120, verbose_name="Incomplete directory",
            help_text="Directory to incomplete files. An empty field means disable.", blank=True)
    umask = models.CharField(max_length=120, verbose_name="User mask",
            help_text="Use this option to override the default permission modes for newly created files (0002 by default).", blank=True)
    options = models.CharField(max_length=120, verbose_name="Extra Options", blank=True)
