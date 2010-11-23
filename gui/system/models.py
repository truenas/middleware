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
import datetime
import time
#from django.utils.text import capfirst
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext_lazy as _
from freenasUI.choices import *

class Settings(models.Model):
    stg_username = models.CharField(
            max_length=120, 
            default="admin", 
            verbose_name="Username"
            )
    stg_guiprotocol = models.CharField(
            max_length=120, 
            choices=PROTOCOL_CHOICES, 
            default="http", 
            verbose_name="Protocol"
            )
    stg_language = models.CharField(
            max_length=120, 
            choices=LANG_CHOICES, 
            default="english", 
            verbose_name="Language"
            )
    stg_timezone = models.CharField(
            max_length=120, 
            choices=TimeZoneChoices(),
            default="America/Los_Angeles", 
            verbose_name="Timezone"
            )
    stg_ntpserver1 = models.CharField(
            max_length=120, 
            default="0.freebsd.pool.ntp.org iburst maxpoll 9",
            verbose_name="NTP server 1"
            )
    stg_ntpserver2 = models.CharField(
            max_length=120, 
            default="1.freebsd.pool.ntp.org iburst maxpoll 9",
            verbose_name="NTP server 2",
            blank=True
            )
    stg_ntpserver3 = models.CharField(
            max_length=120, 
            default="2.freebsd.pool.ntp.org iburst maxpoll 9",
            verbose_name="NTP server 3",
            blank=True
            )

## System|General|Password
class Password(models.Model):
    pw_currentpw = models.CharField(max_length=120)
    pw_newpw = models.CharField(max_length=120)
    pw_newpw2 = models.CharField(max_length=120)

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
class Advanced(models.Model):
    adv_consolemenu = models.BooleanField(
            verbose_name="Enable Console Menu")
    adv_serialconsole = models.BooleanField(
            verbose_name="Use Serial Console")
    adv_consolescreensaver = models.BooleanField(
            verbose_name="Enable screen saver")
    adv_firmwarevc = models.BooleanField(
            verbose_name="Automatically Check for New Firmware")
    adv_systembeep = models.BooleanField(
            verbose_name="Beep on boot")
    adv_tuning = models.BooleanField(
            verbose_name="Enable Special System Tuning")
    adv_powerdaemon = models.BooleanField(
            verbose_name="Enable powerd (Power Saving Daemon)")
    adv_zeroconfbonjour = models.BooleanField(
            verbose_name="Enable Zeroconf/Bonjour")
    adv_motd = models.TextField(
            max_length=1024,
            verbose_name="MOTD banner",
            ) 

## System|Advanced|Email
class Email(models.Model):
    em_fromemail = models.CharField(
            max_length=120, 
            verbose_name="From email", 
            blank=True
            )
    em_outgoingserver = models.CharField(
            max_length=120, 
            verbose_name="Outgoing mail server", 
            blank=True
            )
    em_port = models.CharField(
            max_length=120, 
            verbose_name="Port to connect to"
            )
    em_security = models.CharField(
            max_length=120, 
            choices=EMAILSECURITY_CHOICES, 
            default="none", 
            verbose_name="Security"
            )
    em_smtp = models.BooleanField(
            verbose_name="Use SMTP")

## System|Advanced|Proxy

#### If the server is behind a proxy set this parameters 
#### to give local services access to the internet via proxy. 

class Proxy(models.Model):
    pxy_httpproxy = models.BooleanField(
            verbose_name="HTTP Proxy Host")
    pxy_httpproxyaddress = models.CharField(
            max_length=120, 
            verbose_name="Address"
            )
    pxy_httpproxyport = models.CharField(
            max_length=120, 
            verbose_name="Port"
            )
    pxy_httpproxyauth = models.BooleanField(
            verbose_name="HTTP Proxy Authorization")
    pxy_ftpproxy = models.BooleanField(
            verbose_name="FTP Proxy Host")
    pxy_ftpproxyaddress = models.CharField(
            max_length=120, 
            verbose_name="Address"
            )
    pxy_ftpproxyport = models.CharField(
            max_length=120, 
            verbose_name="Port"
            )
    pxy_ftpproxyauth = models.BooleanField(
            verbose_name="FTP Proxy Authorization")

## System|Advanced|Swap
class Swap(models.Model):
    swap_memory = models.BooleanField(
            verbose_name="Swap File Size")
    # mountpoint info goes here
    swap_type = models.CharField(
            max_length=120, 
            verbose_name="Swap type"
            )
    swap_mountpoint = models.CharField(
            max_length=120, 
            choices=MOUNTPOINT_CHOICES, 
            verbose_name="Mount point"
            )
    swap_size = models.CharField(
            max_length=120, 
            verbose_name="Size"
            )

## Command Scripts
class CommandScripts(models.Model):
    cmds_command = models.CharField(
            max_length=120, 
            verbose_name="Command"
            )
    cmds_commandtype = models.CharField(
            max_length=120, 
            choices=COMMANDSCRIPT_CHOICES, 
            verbose_name="Type"
            )

## System|Advanced|Cron
class CronJob(models.Model):
    cron_enable = models.BooleanField(
            verbose_name="Enable Cron")
    cron_command = models.CharField(
            max_length=120, 
            verbose_name="Command"
            )
    cron_who = models.CharField(
            max_length=120, 
            choices=whoChoices(), 
            default="root", 
            verbose_name="Who"
            )
    cron_description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True
            )
    cron_ToggleMinutes = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Minutes"
            )
    cron_Minutes1 = models.CharField(
            max_length=120, 
            choices=MINUTES1_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    cron_Minutes2 = models.CharField(
            max_length=120, 
            choices=MINUTES2_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    cron_Minutes3 = models.CharField(
            max_length=120, 
            choices=MINUTES3_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    cron_Minutes4 = models.CharField(
            max_length=120, 
            choices=MINUTES4_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    cron_ToggleHours = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Hours"
            )
    cron_Hours1 = models.CharField(
            max_length=120, 
            choices=HOURS1_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    cron_Hours2 = models.CharField(
            max_length=120, 
            choices=HOURS2_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    cron_ToggleDays = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Days"
            )
    cron_Days1 = models.CharField(
            max_length=120, 
            choices=DAYS1_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    cron_Days2 = models.CharField(
            max_length=120, 
            choices=DAYS2_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    cron_Days3 = models.CharField(
            max_length=120, 
            choices=DAYS3_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    cron_ToggleMonths = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Months"
            )
    cron_Months = models.CharField(
            max_length=120, 
            choices=MONTHS_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    cron_ToggleWeekdays = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name=""
            )
    cron_Weekdays = models.CharField(
            max_length=120, 
            choices=WEEKDAYS_CHOICES, 
            default="(NONE)", 
            verbose_name="Weekdays"
            )

## System|Advanced|rc.conf
class rcconf(models.Model):
    rcc_varname = models.CharField(
            max_length=120, 
            verbose_name="Name"
            )
    rcc_varvalue = models.CharField(
            max_length=120, 
            verbose_name="Value"
            )
    rcc_varcomment = models.CharField(
            max_length=120, 
            verbose_name="Comment"
            )

## System|Advanced|sysctl.conf
class sysctl(models.Model):
    sctl_MIBname = models.CharField(
            max_length=120, 
            verbose_name="Name"
            )
    sctl_MIBvalue = models.CharField(
            max_length=120, 
            verbose_name="Value"
            )
    sctl_MIBcomment = models.CharField(
            max_length=120, 
            verbose_name="Comment"
            )
   
