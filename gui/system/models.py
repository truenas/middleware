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
from django.core.validators import *
from freenasUI.choices import *
from freeadmin.models import Model

class Settings(Model):
    stg_guiprotocol = models.CharField(
            max_length=120, 
            choices=PROTOCOL_CHOICES, 
            default="http", 
            verbose_name = _("Protocol")
            )
    stg_language = models.CharField(
            max_length=120, 
            choices=LANG_CHOICES, 
            default="english", 
            verbose_name = _("Language")
            )
    stg_timezone = models.CharField(
            max_length=120, 
            choices=TimeZoneChoices(),
            default="America/Los_Angeles", 
            verbose_name = _("Timezone")
            )
    stg_ntpserver1 = models.CharField(
            max_length=120, 
            default="0.freebsd.pool.ntp.org iburst maxpoll 9",
            verbose_name = _("NTP server 1")
            )
    stg_ntpserver2 = models.CharField(
            max_length=120, 
            default="1.freebsd.pool.ntp.org iburst maxpoll 9",
            verbose_name = _("NTP server 2"),
            blank=True
            )
    stg_ntpserver3 = models.CharField(
            max_length=120, 
            default="2.freebsd.pool.ntp.org iburst maxpoll 9",
            verbose_name = _("NTP server 3"),
            blank=True
            )

    class Meta:
        verbose_name = _("Settings")

    class FreeAdmin:
        deletable = False

class Advanced(Model):
    adv_consolemenu = models.BooleanField(
            verbose_name = _("Enable Console Menu"))
    adv_serialconsole = models.BooleanField(
            verbose_name = _("Use Serial Console"))
    adv_consolescreensaver = models.BooleanField(
            verbose_name = _("Enable screen saver"))
    adv_firmwarevc = models.BooleanField(
            verbose_name = _("Automatically Check for New Firmware"))
    adv_systembeep = models.BooleanField(
            verbose_name = _("Beep on boot"))
    adv_tuning = models.BooleanField(
            verbose_name = _("Enable Special System Tuning"))
    adv_powerdaemon = models.BooleanField(
            verbose_name = _("Enable powerd (Power Saving Daemon)"))
    adv_zeroconfbonjour = models.BooleanField(
            verbose_name = _("Enable Zeroconf/Bonjour"))
    adv_swapondrive = models.IntegerField(
            validators=[MinValueValidator(1)],
            verbose_name = _("Swap size on each drive in GiB, affects new disks only.  Must be non-zero"),
            default=2)
    adv_consolemsg = models.BooleanField(
            verbose_name = _("Show console messages in the footer (Requires UI reload)"),
            default=True)
    # TODO: need geom_eli in kernel
    #adv_encswap = models.BooleanField(
    #        verbose_name = _("Encrypt swap space"),
    #        default=False)
    adv_motd = models.TextField(
            max_length=1024,
            verbose_name = _("MOTD banner"),
            )

    class Meta:
        verbose_name = _("Advanced")

    class FreeAdmin:
        deletable = False

## System|Advanced|Email
class Email(Model):
    em_fromemail = models.CharField(
            max_length=120, 
            verbose_name = _("From email"), 
            help_text = _("An email address that the system will use for the sending address for mail it sends, eg: freenas@mydomain.com"),
            blank=True
            )
    em_outgoingserver = models.CharField(
            max_length=120, 
            verbose_name = _("Outgoing mail server"), 
            help_text = _("A hostname or ip that will accept our mail, for instance mail.example.org, or 192.168.1.1"),
            blank=True
            )
    em_port = models.IntegerField(
            default=25,
            validators=[MinValueValidator(1), MaxValueValidator(65535)],
            help_text = _("An integer from 1 - 65535, generally will be 25, 465, or 587"),
            verbose_name = _("Port to connect to")
            )
    em_security = models.CharField(
            max_length=120, 
            choices=SMTPAUTH_CHOICES,
            default="plain", 
            help_text = _("encryption of the connection"),
            verbose_name = _("TLS/SSL")
            )
    em_smtp = models.BooleanField(
            verbose_name = _("Use SMTP Authentication"),
            default=False
            )
    em_user = models.CharField(
            blank=True,
            null=True,
            max_length=120, 
            verbose_name = _("Username"),
            help_text = _("A username to authenticate to the remote server"),
            )
    em_pass = models.CharField(
            blank=True,
            null=True,
            max_length=120, 
            verbose_name = _("Password"),
            help_text = _("A password to authenticate to the remote server"),
            )
    class Meta:
        verbose_name = _("Email")

    class FreeAdmin:
        deletable = False

class SSL(Model):
    ssl_org = models.CharField(
            blank=True,
            null=True,
            max_length=120, 
            verbose_name = _("Organization"),
            help_text = _("Organization Name (eg, company)"),
            )
    ssl_unit = models.CharField(
            blank=True,
            null=True,
            max_length=120, 
            verbose_name = _("Organizational Unit"),
            help_text = _("Organizational Unit Name (eg, section)"),
            )
    ssl_email = models.CharField(
            blank=True,
            null=True,
            max_length=120, 
            verbose_name = _("Email Address"),
            help_text = _("Email Address"),
            )
    ssl_city = models.CharField(
            blank=True,
            null=True,
            max_length=120, 
            verbose_name = _("Locality"),
            help_text = _("Locality Name (eg, city)"),
            )
    ssl_state = models.CharField(
            blank=True,
            null=True,
            max_length=120, 
            verbose_name = _("State"),
            help_text = _("State or Province Name (full name)"),
            )
    ssl_country = models.CharField(
            blank=True,
            null=True,
            max_length=120, 
            verbose_name = _("Country"),
            help_text = _("Country Name (2 letter code)"),
            )
    ssl_common = models.CharField(
            blank=True,
            null=True,
            max_length=120, 
            verbose_name = _("Common Name"),
            help_text = _("Common Name (eg, YOUR name)"),
            )
    ssl_certfile = models.TextField(
            blank=True,
            null=True,
            verbose_name = _("SSL Certificate"),
            help_text = _("Cut and paste the contents of your private and public certificate files here."),
            )

    class Meta:
        verbose_name = _("SSL")

    class FreeAdmin:
        deletable = False
