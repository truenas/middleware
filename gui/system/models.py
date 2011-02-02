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
