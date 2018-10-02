# +
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
import logging
import pipes
import subprocess

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.freeadmin.models import DictField, ListField, Model, UserField, PathField
from freenasUI.middleware.client import client
from freenasUI.middleware.notifier import notifier
from freenasUI.storage.models import Disk

log = logging.getLogger('tasks.models')


class CloudSync(Model):
    description = models.CharField(
        max_length=150,
        verbose_name=_('Description'),
    )
    direction = models.CharField(
        max_length=10,
        verbose_name=_("Direction"),
        help_text=_(
            "Push - From local to remote. Pull - From "
            "remote to local."
        ),
        default='PUSH',
        choices=(
            ('PUSH', _('Push')),
            ('PULL', _('Pull')),
        )
    )
    path = PathField(
        verbose_name=_("Path"),
        abspath=False,
    )
    credential = models.ForeignKey(
        'system.CloudCredentials',
        verbose_name=_('Credential'),
    )
    transfer_mode = models.CharField(
        verbose_name=_('Transfer Mode'),
        default='sync',
        choices=(
            ('SYNC', _('Sync')),
            ('COPY', _('Copy')),
            ('MOVE', _('Move')),
        ),
        max_length=20,
    )
    attributes = DictField(
        editable=False,
    )
    snapshot = models.BooleanField(
        verbose_name=_("Take snapshot"),
        help_text=_(
            "Take dataset snapshot before pushing data.",
        ),
    )
    pre_script = models.TextField(
        blank=True,
        verbose_name=_("Pre-script"),
        help_text=_(
            "Script to execute before running sync.",
        ),
    )
    post_script = models.TextField(
        blank=True,
        verbose_name=_("Post-script"),
        help_text=_(
            "Script to execute after running sync.",
        ),
    )
    encryption = models.BooleanField(
        verbose_name=_("Remote encryption"),
        help_text=_(
            "This option will push encrypted files and decrypt pulled files.",
        ),
    )
    filename_encryption = models.BooleanField(
        default=True,
        verbose_name=_("Filename encryption"),
        help_text=_(
            "Also encrypt filenames.",
        ),
    )
    encryption_password = models.CharField(
        blank=True,
        max_length=256,
        verbose_name=_("Encryption password"),
    )
    encryption_salt = models.CharField(
        blank=True,
        max_length=256,
        verbose_name=_("Encryption salt"),
    )
    args = models.TextField(
        blank=True,
        max_length=255,
        verbose_name=_("Auxiliary arguments"),
        help_text=_(
            "These arguments will be passed to rclone."
            "<br>See <a href=\"https://rclone.org/docs/\">https://rclone.org/docs/</a> for help"),
    )
    minute = models.CharField(
        max_length=100,
        default="00",
        verbose_name=_("Minute"),
        help_text=_(
            "Values allowed:"
            "<br>Slider: 0-30 (as it is every Nth minute)."
            "<br>Specific Minute: 0-59."),
    )
    hour = models.CharField(
        max_length=100,
        default="*",
        verbose_name=_("Hour"),
        help_text=_("Values allowed:"
                    "<br>Slider: 0-12 (as it is every Nth hour)."
                    "<br>Specific Hour: 0-23."),
    )
    daymonth = models.CharField(
        max_length=100,
        default="*",
        verbose_name=_("Day of month"),
        help_text=_("Values allowed:"
                    "<br>Slider: 0-15 (as its is every Nth day)."
                    "<br>Specific Day: 1-31."),
    )
    month = models.CharField(
        max_length=100,
        default='*',
        verbose_name=_("Month"),
    )
    dayweek = models.CharField(
        max_length=100,
        default="*",
        verbose_name=_("Day of week"),
    )
    bwlimit = ListField(
        editable=False,
    )
    exclude = ListField(
        editable=False,
    )
    enabled = models.BooleanField(
        default=True,
        verbose_name=_("Enabled"),
        help_text=_(
            'Disabling will not stop any syncs which are in progress.'
        ),
    )

    class Meta:
        verbose_name = _("Cloud Sync")
        verbose_name_plural = _("Cloud Syncs")
        ordering = ["description"]

    def __str__(self):
        return self.description

    def run(self):
        with client as c:
            jid = c.call('cloudsync.sync', self.id)
        return jid


class CronJob(Model):
    cron_user = UserField(
        max_length=60,
        verbose_name=_("User"),
        help_text=_("The user to run the command")
    )
    cron_command = models.TextField(
        verbose_name=_("Command"),
    )
    cron_description = models.CharField(
        max_length=200,
        verbose_name=_("Short description"),
        blank=True,
    )
    cron_minute = models.CharField(
        max_length=100,
        default="00",
        verbose_name=_("Minute"),
        help_text=_("Values 0-59 allowed."),
    )
    cron_hour = models.CharField(
        max_length=100,
        default="*",
        verbose_name=_("Hour"),
        help_text=_("Values 0-23 allowed."),
    )
    cron_daymonth = models.CharField(
        max_length=100,
        default="*",
        verbose_name=_("Day of month"),
        help_text=_("Values 1-31 allowed."),
    )
    cron_month = models.CharField(
        max_length=100,
        default='*',
        verbose_name=_("Month"),
    )
    cron_dayweek = models.CharField(
        max_length=100,
        default="*",
        verbose_name=_("Day of week"),
    )
    cron_stdout = models.BooleanField(
        default=True,
        verbose_name=_("Redirect Stdout"),
        help_text=_(
            "Redirect the standard output to /dev/null. In other "
            "words, disable output."
        ),
    )
    cron_stderr = models.BooleanField(
        default=False,
        verbose_name=_("Redirect Stderr"),
        help_text=_(
            "Redirect the standard error output to /dev/null. In "
            "other words, disable error output."
        ),
    )
    cron_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Enabled"),
    )

    class Meta:
        verbose_name = _("Cron Job")
        verbose_name_plural = _("Cron Jobs")
        ordering = ["cron_description", "cron_user"]

    def __str__(self):
        if self.cron_description:
            return self.cron_description
        return "%d (%s)" % (self.id, self.cron_user)

    def commandline(self):
        line = self.cron_command
        if self.cron_stdout:
            line += ' > /dev/null'
        if self.cron_stderr:
            line += ' 2> /dev/null'
        else:
            line += ' 2>&1'
        return line

    def run(self):
        proc = subprocess.Popen([
            "/usr/local/www/freenasUI/tools/runnow.py",
            "-t", "cronjob",
            "-i", str(self.id),
        ])
        proc.communicate()


class InitShutdown(Model):
    ini_type = models.CharField(
        choices=(
            ('command', _('Command')),
            ('script', _('Script')),
        ),
        default='command',
        max_length=15,
        verbose_name=_("Type"),
    )
    ini_command = models.CharField(
        max_length=300,
        verbose_name=_("Command"),
        blank=True,
    )
    ini_script = PathField(
        verbose_name=_("Script"),
        filesonly=True,
        dirsonly=False,
        blank=True,
    )
    ini_when = models.CharField(
        choices=(
            ('preinit', _('Pre Init')),
            ('postinit', _('Post Init')),
            ('shutdown', _('Shutdown')),
        ),
        max_length=15,
        verbose_name=_("When"),
    )
    ini_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Enabled"),
    )

    def __str__(self):
        if self.ini_type == 'command':
            name = self.ini_command
        else:
            name = self.ini_script
        return "%s - %s" % (
            self.get_ini_when_display(),
            name,
        )

    class Meta:
        verbose_name = _("Init/Shutdown Script")
        verbose_name_plural = _("Init/Shutdown Scripts")

    class FreeAdmin:
        # FIXME
        icon_model = "TunableIcon"
        icon_object = "TunableIcon"
        icon_add = "AddTunableIcon"
        icon_view = "ViewTunableIcon"
        menu_child_of = 'tasks'


class Rsync(Model):
    rsync_path = PathField(
        verbose_name=_("Path"),
        abspath=False,
    )
    rsync_remotehost = models.CharField(
        max_length=120,
        verbose_name=_("Remote Host"),
        help_text=_("IP Address or hostname. "
                    "Specify user@hostname or user@ip-address "
                    "if your remote machine user and above rsync "
                    "task user are different."
                    ),
    )
    rsync_remoteport = models.SmallIntegerField(
        default=22,
        verbose_name=_("Remote SSH Port"),
        help_text=_("SSH Port"),
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
    )
    rsync_mode = models.CharField(
        max_length=20,
        choices=choices.RSYNC_MODE_CHOICES,
        default='module',
    )
    rsync_remotemodule = models.CharField(
        max_length=120,
        verbose_name=_("Remote Module Name"),
        blank=True,
        help_text=_("Name of the module defined in the remote rsync daemon"),
    )
    rsync_remotepath = models.CharField(
        max_length=255,
        verbose_name=_("Remote Path"),
        blank=True,
        help_text=_("Path on remote host to rsync to, e.g. /mnt/tank"),
    )
    rsync_direction = models.CharField(
        max_length=10,
        verbose_name=_("Direction"),
        help_text=_(
            "Push - From local to remote machine. Pull - From "
            "remote to local machine."
        ),
        default='push',
        choices=choices.RSYNC_DIRECTION,
    )
    rsync_desc = models.CharField(
        max_length=120,
        verbose_name=_("Short description"),
        blank=True,
    )
    rsync_minute = models.CharField(
        max_length=100,
        default="00",
        verbose_name=_("Minute"),
        help_text=_(
            "Values allowed:"
            "<br>Slider: 0-30 (as it is every Nth minute)."
            "<br>Specific Minute: 0-59."),
    )
    rsync_hour = models.CharField(
        max_length=100,
        default="*",
        verbose_name=_("Hour"),
        help_text=_("Values allowed:"
                    "<br>Slider: 0-12 (as it is every Nth hour)."
                    "<br>Specific Hour: 0-23."),
    )
    rsync_daymonth = models.CharField(
        max_length=100,
        default="*",
        verbose_name=_("Day of month"),
        help_text=_("Values allowed:"
                    "<br>Slider: 0-15 (as its is every Nth day)."
                    "<br>Specific Day: 1-31."),
    )
    rsync_month = models.CharField(
        max_length=100,
        default='*',
        verbose_name=_("Month"),
    )
    rsync_dayweek = models.CharField(
        max_length=100,
        default="*",
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
        help_text=_(
            "Delete files on the receiving side that don't exist on sender"
        ),
        default=False,
    )
    rsync_quiet = models.BooleanField(
        verbose_name=_("Quiet"),
        help_text=_("Suppress non-error messages"),
        default=False,
    )
    rsync_preserveperm = models.BooleanField(
        verbose_name=_("Preserve permissions"),
        help_text=_(
            "This option causes the receiving rsync to set the "
            "destination permissions to be the same as the source "
            "permissions"
        ),
        default=False,
    )
    rsync_preserveattr = models.BooleanField(
        verbose_name=_("Preserve extended attributes"),
        help_text=_(
            "This option causes rsync to update the remote "
            "extended attributes to be the same as the local ones"
        ),
        default=False,
    )
    rsync_delayupdates = models.BooleanField(
        verbose_name=_("Delay Updates"),
        help_text=_("Put all updated files into place at the end"),
        default=True,
    )
    rsync_extra = models.TextField(
        verbose_name=_("Extra options"),
        help_text=_("Extra options to rsync command line (usually empty)"),
        blank=True
    )
    rsync_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Enabled"),
    )

    class Meta:
        verbose_name = _("Rsync Task")
        verbose_name_plural = _("Rsync Tasks")
        ordering = ["rsync_path", "rsync_desc"]

    def __str__(self):
        if self.rsync_desc:
            return self.rsync_desc
        elif self.rsync_mode == 'module':
            return self.rsync_remotemodule
        else:
            return self.rsync_remotepath

    def commandline(self):
        line = '/usr/bin/lockf -s -t 0 -k "%s" /usr/local/bin/rsync' % (
            self.rsync_path
        )
        if self.rsync_recursive:
            line += ' -r'
        if self.rsync_times:
            line += ' -t'
        if self.rsync_compress:
            line += ' -z'
        if self.rsync_archive:
            line += ' -a'
        if self.rsync_preserveperm:
            line += ' -p'
        if self.rsync_preserveattr:
            line += ' -X'
        if self.rsync_delete:
            line += ' --delete-delay'
        if self.rsync_delayupdates:
            line += ' --delay-updates'
        if self.rsync_extra:
            line += ' %s' % self.rsync_extra

        # Do not use username if one is specified in host field
        # See #5096 for more details
        if '@' in self.rsync_remotehost:
            remote = self.rsync_remotehost
        else:
            remote = '"%s"@%s' % (
                self.rsync_user,
                self.rsync_remotehost,
            )

        if self.rsync_mode == 'module':
            if self.rsync_direction == 'push':
                line += ' "%s" %s::"%s"' % (
                    self.rsync_path,
                    remote,
                    self.rsync_remotemodule,
                )
            else:
                line += ' %s::"%s" "%s"' % (
                    remote,
                    self.rsync_remotemodule,
                    self.rsync_path,
                )
        else:
            line += (
                ' -e "ssh -p %d -o BatchMode=yes '
                '-o StrictHostKeyChecking=yes"'
            ) % (
                self.rsync_remoteport
            )
            if pipes.quote(self.rsync_remotepath) == self.rsync_remotepath:
                rsync_remotepath = self.rsync_remotepath
            else:
                rsync_remotepath = '\\""%s"\\"' % self.rsync_remotepath
            if self.rsync_direction == 'push':
                line += ' "%s" %s:%s' % (
                    self.rsync_path,
                    remote,
                    rsync_remotepath,
                )
            else:
                line += ' %s:%s "%s"' % (
                    remote,
                    rsync_remotepath,
                    self.rsync_path,
                )
        if self.rsync_quiet:
            line += ' > /dev/null 2>&1'
        return line

    def run(self):
        proc = subprocess.Popen([
            "/usr/local/www/freenasUI/tools/runnow.py",
            "-t", "rsync",
            "-i", str(self.id),
        ])
        proc.communicate()


class SMARTTest(Model):
    smarttest_disks = models.ManyToManyField(
        Disk,
        limit_choices_to={'disk_expiretime': None},
        verbose_name=_("Disks"),
    )
    smarttest_type = models.CharField(
        choices=choices.SMART_TEST,
        max_length=2,
        verbose_name=_("Type"),
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
        default='*',
    )
    smarttest_daymonth = models.CharField(
        max_length=100,
        verbose_name=_("Day of month"),
        help_text=_("Values 1-31 allowed."),
        default='*',
    )
    smarttest_month = models.CharField(
        max_length=100,
        default='*',
        verbose_name=_("Month"),
    )
    smarttest_dayweek = models.CharField(
        max_length=100,
        default='*',
        verbose_name=_("Day of week"),
    )

    def __str__(self):
        if self.smarttest_disks.count() > 3:
            disks = [d.disk_name for d in self.smarttest_disks.all()[:3]]
            disks = ', '.join(disks) + '...'
        else:
            disks = [d.disk_name for d in self.smarttest_disks.all()]
            disks = ', '.join(disks)

        return "%s (%s) " % (
            self.get_smarttest_type_display(),
            disks
        )

    class Meta:
        verbose_name = _("S.M.A.R.T. Test")
        verbose_name_plural = _("S.M.A.R.T. Tests")
        ordering = ["smarttest_type"]
