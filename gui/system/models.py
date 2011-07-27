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

from django.utils.translation import ugettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.conf import settings

from freenasUI import choices
from freeadmin.models import Model, UserField, GroupField
from freenasUI.middleware.notifier import notifier
from freeadmin.models import PathField
from storage.models import Disk
import choices

class Settings(Model):
    stg_guiprotocol = models.CharField(
            max_length=120,
            choices=choices.PROTOCOL_CHOICES,
            default="http",
            verbose_name = _("Protocol")
            )
    stg_language = models.CharField(
            max_length=120,
            choices=settings.LANGUAGES,
            default="en",
            verbose_name = _("Language")
            )
    stg_timezone = models.CharField(
            max_length=120,
            choices=choices.TimeZoneChoices(),
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
    stg_syslogserver = models.CharField(
            max_length=120,
            verbose_name = _("Syslog server"),
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
            verbose_name = _("Swap size on each drive in GiB, affects new disks only. Must be non-zero"),
            default=2)
    adv_consolemsg = models.BooleanField(
            verbose_name = _("Show console messages in the footer (Requires UI reload)"),
            default=True)
    adv_traceback = models.BooleanField(
            verbose_name = _("Show tracebacks in case of fatal errors"),
            default=False)
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
            help_text = _("An email address that the system will use for the sending address for mail it sends, eg: freenas@example.com"),
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
            choices=choices.SMTPAUTH_CHOICES,
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

class CronJob(Model):
    cron_user = UserField(
            max_length=60,
            verbose_name=_("User"),
            help_text=_("The user to run the command")
            )
    cron_command = models.CharField(
            max_length=120,
            verbose_name=_("Command"),
            )
    cron_minute = models.CharField(
            max_length=100,
            verbose_name=_("Minute"),
            help_text=_("Values 0-59 allowed."),
            )
    cron_hour = models.CharField(
            max_length=100,
            verbose_name=_("Hour"),
            help_text=_("Values 0-23 allowed."),
            )
    cron_daymonth = models.CharField(
            max_length=100,
            verbose_name=_("Day of month"),
            help_text=_("Values 1-31 allowed."),
            )
    cron_month = models.CharField(
            max_length=100,
            default='1,2,3,4,5,6,7,8,9,10,a,b,c',
            verbose_name=_("Month"),
            )
    cron_dayweek = models.CharField(
            max_length=100,
            default="1,2,3,4,5,6,7",
            verbose_name=_("Day of week"),
            )
    class Meta:
        verbose_name = _("CronJob")
        verbose_name_plural = _("CronJobs")

    class FreeAdmin:
        pass

    def __unicode__(self):
        return u"%d (%s)" % (self.id, self.cron_user)

    def get_human_minute(self):
        if self.cron_minute == '*':
            return _(u'Every minute')
        elif self.cron_minute.startswith('*/'):
            return _(u'Every %s minute(s)') % self.cron_minute.split('*/')[1]
        else:
            return self.cron_minute

    def get_human_hour(self):
        if self.cron_hour == '*':
            return _(u'Every hour')
        elif self.cron_hour.startswith('*/'):
            return _(u'Every %s hour(s)') % self.cron_hour.split('*/')[1]
        else:
            return self.cron_hour

    def get_human_daymonth(self):
        if self.cron_daymonth == '*':
            return _(u'Everyday')
        elif self.cron_daymonth.startswith('*/'):
            return _(u'Every %s days') % self.cron_daymonth.split('*/')[1]
        else:
            return self.cron_daymonth

    def get_human_month(self):
        months = self.cron_month.split(",")
        if len(months) == 12:
            return _("Every month")
        mchoices = dict(choices.MONTHS_CHOICES)
        labels = []
        for m in months:
            if m in ('10', '11', '12'):
                m = chr(87 + int(m))
            labels.append(unicode(mchoices[m]))
        return ",".join(labels)

    def get_human_dayweek(self):
        weeks = eval(self.cron_dayweek)
        if len(weeks) == 7:
            return _("Everyday")
        wchoices = dict(choices.WEEKDAYS_CHOICES)
        labels = []
        for w in weeks:
            labels.append(unicode(wchoices[str(w)]))
        return ",".join(labels)

    def delete(self):
        super(CronJob, self).delete()
        try:
            notifier().restart("cron")
        except:
            pass

class Rsync(Model):
    rsync_path = PathField(
        verbose_name=_("Path"),
        )
    rsync_remotehost = models.CharField(
            max_length=120,
            verbose_name=_("Remote Host"),
            help_text=_("IP Address or hostname"),
            )
    rsync_remotemodule = models.CharField(
            max_length=120,
            verbose_name=_("Remote Module Name"),
            )
    rsync_desc = models.CharField(
            max_length=120,
            verbose_name=_("Short description"),
            blank=True,
            )
    rsync_minute = models.CharField(
            max_length=100,
            verbose_name=_("Minute"),
            help_text=_("Values 0-59 allowed."),
            )
    rsync_hour = models.CharField(
            max_length=100,
            verbose_name=_("Hour"),
            help_text=_("Values 0-23 allowed."),
            )
    rsync_daymonth = models.CharField(
            max_length=100,
            verbose_name=_("Day of month"),
            help_text=_("Values 1-31 allowed."),
            )
    rsync_month = models.CharField(
            max_length=100,
            default='1,2,3,4,5,6,7,8,9,10,a,b,c',
            verbose_name=_("Month"),
            )
    rsync_dayweek = models.CharField(
            max_length=100,
            default="1,2,3,4,5,6,7",
            verbose_name=_("Day of week"),
            )
    rsync_user = UserField(
            max_length=60,
            verbose_name=_("User"),
            help_text=_("The user to run the command"),
            )
    rsync_recursive = models.BooleanField(
            verbose_name=_("Recursive"),
            help_text=_("Recurse into directories"),
            default=True,
            )
    rsync_times = models.BooleanField(
            verbose_name=_("Times"),
            help_text=_("Preserve modification times"),
            default=True,
            )
    rsync_compress = models.BooleanField(
            verbose_name=_("Compress"),
            help_text=_("Compress data during the transfer"),
            default=True,
            )
    rsync_archive = models.BooleanField(
            verbose_name=_("Archive"),
            help_text=_("Archive mode"),
            default=False,
            )
    rsync_delete = models.BooleanField(
            verbose_name=_("Delete"),
            help_text=_("Delete files on the receiving side that don't exist on sender"),
            default=False,
            )
    rsync_quiet = models.BooleanField(
            verbose_name=_("Quiet"),
            help_text=_("Suppress non-error messages"),
            default=False,
            )
    rsync_preserveperm = models.BooleanField(
            verbose_name=_("Preserve permissions"),
            help_text=_("This option causes the receiving rsync to set the destination permissions to be the same as the source permissions"),
            default=False,
            )
    rsync_preserveattr = models.BooleanField(
            verbose_name=_("Preserve extended attributes"),
            help_text=_("This option causes rsync to update the remote extended attributes to be the same as the local ones"),
            default=False,
            )
    rsync_extra = models.CharField(
            max_length=120,
            verbose_name=_("Extra options"),
            help_text=_("Extra options to rsync command line (usually empty)"),
            blank=True
            )
    class Meta:
        verbose_name = _("Rsync")
        verbose_name_plural = _("Rsyncs")

    class FreeAdmin:
        pass

    def __unicode__(self):
        return u"%d (%s)" % (self.id, self.rsync_user)

    def get_human_minute(self):
        if self.rsync_minute == '*':
            return _(u'Every minute')
        elif self.rsync_minute.startswith('*/'):
            return _(u'Every %s minute(s)') % self.rsync_minute.split('*/')[1]
        else:
            return self.rsync_minute

    def get_human_hour(self):
        if self.rsync_hour == '*':
            return _(u'Every hour')
        elif self.rsync_hour.startswith('*/'):
            return _(u'Every %s hour(s)') % self.rsync_hour.split('*/')[1]
        else:
            return self.rsync_hour

    def get_human_daymonth(self):
        if self.rsync_daymonth == '*':
            return _(u'Everyday')
        elif self.rsync_daymonth.startswith('*/'):
            return _(u'Every %s days') % self.rsync_daymonth.split('*/')[1]
        else:
            return self.rsync_daymonth

    def get_human_month(self):
        months = self.rsync_month.split(",")
        if len(months) == 12:
            return _("Every month")
        mchoices = dict(choices.MONTHS_CHOICES)
        labels = []
        for m in months:
            if m in ('10', '11', '12'):
                m = chr(87 + int(m))
            labels.append(unicode(mchoices[m]))
        return ",".join(labels)

    def get_human_dayweek(self):
        weeks = eval(self.rsync_dayweek)
        if len(weeks) == 7:
            return _("Everyday")
        wchoices = dict(choices.WEEKDAYS_CHOICES)
        labels = []
        for w in weeks:
            labels.append(unicode(wchoices[str(w)]))
        return ",".join(labels)

    def delete(self):
        super(Rsync, self).delete()
        try:
            notifier().restart("cron")
        except:
            pass

class SMARTTest(Model):
    smarttest_disk = models.ForeignKey(
            Disk,
            unique=True,
            verbose_name=_("Disk"),
            )
    smarttest_type = models.CharField(
            choices=choices.SMART_TEST,
            max_length=2,
            verbose_name=_("Type"),
            blank=True,
            )
    smarttest_desc = models.CharField(
            max_length=120,
            verbose_name=_("Short description"),
            blank=True,
            )
    smarttest_hour = models.CharField(
            max_length=100,
            verbose_name=_("Hour"),
            help_text=_("Values 0-23 allowed."),
            )
    smarttest_daymonth = models.CharField(
            max_length=100,
            verbose_name=_("Day of month"),
            help_text=_("Values 1-31 allowed."),
            )
    smarttest_month = models.CharField(
            max_length=100,
            default='1,2,3,4,5,6,7,8,9,10,a,b,c',
            verbose_name=_("Month"),
            )
    smarttest_dayweek = models.CharField(
            max_length=100,
            default="1,2,3,4,5,6,7",
            verbose_name=_("Day of week"),
            )

    def get_human_hour(self):
        if self.smarttest_hour == '..':
            return _(u'Every hour')
        else:
            return self.smarttest_hour

    def get_human_daymonth(self):
        if self.smarttest_daymonth == '..':
            return _(u'Everyday')
        else:
            return self.smarttest_daymonth

    def get_human_month(self):
        months = self.smarttest_month.split(",")
        if len(months) == 12:
            return _("Every month")
        mchoices = dict(choices.MONTHS_CHOICES)
        labels = []
        for m in months:
            if m in ('10', '11', '12'):
                m = chr(87 + int(m))
            labels.append(unicode(mchoices[m]))
        return ",".join(labels)

    def get_human_dayweek(self):
        weeks = eval(self.smarttest_dayweek)
        if len(weeks) == 7:
            return _("Everyday")
        wchoices = dict(choices.WEEKDAYS_CHOICES)
        labels = []
        for w in weeks:
            labels.append(unicode(wchoices[str(w)]))
        return ",".join(labels)

    def __unicode__(self):
        return unicode(self.smarttest_disk)

    class Meta:
        verbose_name = _("S.M.A.R.T. Test")
        verbose_name_plural = _("S.M.A.R.T. Tests")

    class FreeAdmin:
        pass
