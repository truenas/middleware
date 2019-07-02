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
######################################################################
import logging
import time

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.freeadmin.models import DictField, EncryptedDictField, ListField, Model
from freenasUI.middleware.notifier import notifier
from freenasUI.support.utils import get_license

log = logging.getLogger('system.models')


CA_TYPE_EXISTING = 0x00000001
CA_TYPE_INTERNAL = 0x00000002
CA_TYPE_INTERMEDIATE = 0x00000004
CERT_TYPE_EXISTING = 0x00000008
CERT_TYPE_INTERNAL = 0x00000010
CERT_TYPE_CSR = 0x00000020


def time_now():
    return int(time.time())


class Settings(Model):
    stg_guicertificate = models.ForeignKey(
        "Certificate",
        verbose_name=_("Certificate for HTTPS"),
        limit_choices_to={'cert_type__in': [CERT_TYPE_EXISTING, CERT_TYPE_INTERNAL]},
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    stg_guiaddress = ListField(
        blank=True,
        default=['0.0.0.0'],
        verbose_name=_("WebGUI IPv4 Address")
    )
    stg_guiv6address = ListField(
        blank=True,
        default=['::'],
        verbose_name=_("WebGUI IPv6 Address")
    )
    stg_guiport = models.IntegerField(
        verbose_name=_("WebGUI HTTP Port"),
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        default=80,
    )
    stg_guihttpsport = models.IntegerField(
        verbose_name=_("WebGUI HTTPS Port"),
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        default=443,
    )
    stg_guihttpsredirect = models.BooleanField(
        verbose_name=_('WebGUI HTTP -> HTTPS Redirect'),
        default=False,
        help_text=_(
            'Redirect all incoming HTTP requests to HTTPS and '
            'enable the HTTP Strict Transport Security (HSTS) header.'
        ),
    )
    stg_guihttpsprotocols = ListField(
        verbose_name=_('WebGUI HTTPS Protocols'),
        default=['TLSv1', 'TLSv1.1', 'TLSv1.2'],
    )
    stg_language = models.CharField(
        max_length=120,
        choices=settings.LANGUAGES,
        default="en",
        verbose_name=_("Language")
    )
    stg_kbdmap = models.CharField(
        max_length=120,
        choices=choices.KBDMAP_CHOICES(),
        verbose_name=_("Console Keyboard Map"),
        blank=True,
    )
    stg_timezone = models.CharField(
        max_length=120,
        choices=choices.TimeZoneChoices(),
        default="America/Los_Angeles",
        verbose_name=_("Timezone")
    )
    stg_sysloglevel = models.CharField(
        max_length=120,
        choices=choices.SYS_LOG_LEVEL,
        default="f_info",
        verbose_name=_("Syslog level"),
        help_text=_("Specifies which messages will be logged by "
                    "server. INFO and VERBOSE log transactions that "
                    "server performs on behalf of the client. "
                    "f_is_debug specify higher levels of debugging output. "
                    "The default is f_info."),
    )
    stg_syslogserver = models.CharField(
        default='',
        blank=True,
        max_length=120,
        verbose_name=_("Syslog server"),
        help_text=_("Specifies the server and port syslog messages "
                    "will be sent to.  The accepted format is hostname:port "
                    "or ip:port, if :port is not specified it will default to "
                    "port 514 (this field currently only takes IPv4 addresses)"),
    )
    stg_crash_reporting = models.NullBooleanField(
        verbose_name=_("Crash reporting"),
        help_text=_("Enable sending anonymous crash reports to iXsystems"),
    )
    stg_wizardshown = models.BooleanField(
        editable=False,
        default=False,
    )
    stg_pwenc_check = models.CharField(
        max_length=100,
        editable=False,
    )
    stg_usage_collection = models.NullBooleanField(
        verbose_name=_("Usage collection"),
        help_text=_("Enable sending anonymous usage collection to iXsystems"),
    )

    class Meta:
        verbose_name = _("General")


class NTPServer(Model):
    ntp_address = models.CharField(
        verbose_name=_("Address"),
        max_length=120,
    )
    ntp_burst = models.BooleanField(
        verbose_name=_("Burst"),
        default=False,
        help_text=_(
            "When the server is reachable, send a burst of eight "
            "packets instead of the usual one. This is designed to improve"
            " timekeeping quality with the server command and s addresses."
        ),
    )
    ntp_iburst = models.BooleanField(
        verbose_name=_("IBurst"),
        default=True,
        help_text=_(
            "When the server is unreachable, send a burst of eight"
            " packets instead of the usual one. This is designed to speed "
            "the initial synchronization acquisition with the server "
            "command and s addresses."
        ),
    )
    ntp_prefer = models.BooleanField(
        verbose_name=_("Prefer"),
        default=False,
        help_text=_(
            "Marks the server as preferred. All other things being"
            " equal, this host will be chosen for synchronization among a "
            "set of correctly operating hosts."
        ),
    )
    ntp_minpoll = models.IntegerField(
        verbose_name=_("Min. Poll"),
        default=6,
        validators=[MinValueValidator(4)],
        help_text=_(
            "The minimum poll interval for NTP messages, as a "
            "power of 2 in seconds. Defaults to 6 (64 s), but can be "
            "decreased to a lower limit of 4 (16 s)"
        ),
    )
    ntp_maxpoll = models.IntegerField(
        verbose_name=_("Max. Poll"),
        default=10,
        validators=[MaxValueValidator(17)],
        help_text=_(
            "The maximum poll interval for NTP messages, as a "
            "power of 2 in seconds. Defaults to 10 (1,024 s), but can be "
            "increased to an upper limit of 17 (36.4 h)"
        ),
    )

    def __str__(self):
        return self.ntp_address

    class Meta:
        verbose_name = _("NTP Server")
        verbose_name_plural = _("NTP Servers")
        ordering = ["ntp_address"]

    class FreeAdmin:
        icon_model = "NTPServerIcon"
        icon_object = "NTPServerIcon"
        icon_view = "ViewNTPServerIcon"
        icon_add = "AddNTPServerIcon"


class Advanced(Model):
    adv_consolemenu = models.BooleanField(
        verbose_name=_("Show Text Console without Password Prompt"),
        default=False,
    )
    adv_serialconsole = models.BooleanField(
        verbose_name=_("Use Serial Console"),
        default=False,
    )
    adv_serialport = models.CharField(
        max_length=120,
        default="0x2f8",
        help_text=_(
            "Set this to match your serial port address (0x3f8, 0x2f8, etc.)"
        ),
        verbose_name=_("Serial Port Address")
    )
    adv_serialspeed = models.CharField(
        max_length=120,
        choices=choices.SERIAL_SPEED,
        default="9600",
        help_text=_("Set this to match your serial port speed"),
        verbose_name=_("Serial Port Speed")
    )
    adv_powerdaemon = models.BooleanField(
        verbose_name=_("Enable powerd (Power Saving Daemon)"),
        default=False,
    )
    adv_swapondrive = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name=_(
            "Swap size on each drive in GiB, affects new disks "
            "only. Setting this to 0 disables swap creation completely "
            "(STRONGLY DISCOURAGED)."
        ),
        default=2,
    )
    adv_consolemsg = models.BooleanField(
        verbose_name=_("Show console messages in the footer"),
        default=True,
    )
    adv_traceback = models.BooleanField(
        verbose_name=_("Show tracebacks in case of fatal errors"),
        default=True,
    )
    adv_advancedmode = models.BooleanField(
        verbose_name=_("Show advanced fields by default"),
        default=False,
        help_text=_(
            "By default only essential fields are shown. Fields considered "
            "advanced can be displayed through the Advanced Mode button."
        ),
    )
    adv_autotune = models.BooleanField(
        verbose_name=_("Enable autotune"),
        default=False,
        help_text=_(
            "Attempt to automatically tune the network and ZFS system control "
            "variables based on memory available."
        ),
    )
    adv_debugkernel = models.BooleanField(
        verbose_name=_("Enable debug kernel"),
        default=False,
        help_text=_(
            "The kernel built with debug symbols will be booted instead."
        ),
    )
    adv_uploadcrash = models.BooleanField(
        verbose_name=_("Enable automatic upload of kernel crash dumps and daily telemetry"),
        default=True,
    )
    adv_anonstats = models.BooleanField(
        verbose_name=_("Enable report anonymous statistics"),
        default=True,
        editable=False,
    )
    adv_anonstats_token = models.TextField(
        blank=True,
        editable=False,
    )
    adv_motd = models.TextField(
        max_length=10240,
        verbose_name=_("MOTD banner"),
        default='Welcome',
        blank=True,
    )
    adv_boot_scrub = models.IntegerField(
        default=7,
    )
    adv_fqdn_syslog = models.BooleanField(
        verbose_name=_("Use FQDN for logging"),
        default=False,
    )
    adv_sed_user = models.CharField(
        max_length=120,
        choices=choices.SED_USER,
        default="user",
        help_text=_("User passed to camcontrol security -u "
                    "for unlocking SEDs"),
        verbose_name=_("ATA Security User")
    )
    adv_sed_passwd = models.CharField(
        max_length=120,
        blank=True,
        help_text=_("Global password to unlock SED disks."),
        verbose_name=_("SED Password"),
    )

    class Meta:
        verbose_name = _("Advanced")

    class FreeAdmin:
        deletable = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.adv_sed_passwd:
            try:
                self.adv_sed_passwd = notifier().pwenc_decrypt(self.adv_sed_passwd)
            except Exception:
                log.debug('Failed to decrypt SED password', exc_info=True)
                self.adv_sed_passwd = ''
        self._adv_sed_passwd_encrypted = False

    def save(self, *args, **kwargs):
        if self.adv_sed_passwd and not self._adv_sed_passwd_encrypted:
            self.adv_sed_passwd = notifier().pwenc_encrypt(self.adv_sed_passwd)
            self._adv_sed_passwd_encrypted = True
        return super().save(*args, **kwargs)


class Email(Model):
    em_fromemail = models.CharField(
        max_length=120,
        verbose_name=_("From email"),
        help_text=_(
            "An email address that the system will use for the "
            "sending address for mail it sends, eg: freenas@example.com"
        ),
        default='',
    )
    em_fromname = models.CharField(
        max_length=120,
        verbose_name=_("From name"),
        help_text=_(
            "A name which will be displayed in the \"From\" header of e-mail message"
        ),
        default='',
        blank=True,
    )
    em_outgoingserver = models.CharField(
        max_length=120,
        verbose_name=_("Outgoing mail server"),
        help_text=_(
            "A hostname or ip that will accept our mail, for "
            "instance mail.example.org, or 192.168.1.1"
        ),
        blank=True,
    )
    em_port = models.IntegerField(
        default=25,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        help_text=_(
            "An integer from 1 - 65535, generally will be 25, "
            "465, or 587"
        ),
        verbose_name=_("Port to connect to"),
    )
    em_security = models.CharField(
        max_length=120,
        choices=choices.SMTPAUTH_CHOICES,
        default="plain",
        help_text=_("encryption of the connection"),
        verbose_name=_("TLS/SSL")
    )
    em_smtp = models.BooleanField(
        verbose_name=_("Use SMTP Authentication"),
        default=False
    )
    em_user = models.CharField(
        blank=True,
        null=True,
        max_length=120,
        verbose_name=_("Username"),
        help_text=_("A username to authenticate to the remote server"),
    )
    em_pass = models.CharField(
        blank=True,
        null=True,
        max_length=120,
        verbose_name=_("Password"),
        help_text=_("A password to authenticate to the remote server"),
    )

    class Meta:
        verbose_name = _("Email")

    class FreeAdmin:
        deletable = False

    def __init__(self, *args, **kwargs):
        super(Email, self).__init__(*args, **kwargs)
        if self.em_pass:
            try:
                self.em_pass = notifier().pwenc_decrypt(self.em_pass)
            except Exception:
                log.debug('Failed to decrypt email password', exc_info=True)
                self.em_pass = ''
        self._em_pass_encrypted = False

    def save(self, *args, **kwargs):
        if self.em_pass and not self._em_pass_encrypted:
            self.em_pass = notifier().pwenc_encrypt(self.em_pass)
            self._em_pass_encrypted = True
        return super(Email, self).save(*args, **kwargs)


class Tunable(Model):
    tun_var = models.CharField(
        max_length=128,
        unique=True,
        verbose_name=_("Variable"),
    )
    tun_value = models.CharField(
        max_length=512,
        verbose_name=_("Value"),
    )
    tun_type = models.CharField(
        verbose_name=_('Type'),
        max_length=20,
        choices=choices.TUNABLE_TYPES,
        default='loader',
    )
    tun_comment = models.CharField(
        max_length=100,
        verbose_name=_("Comment"),
        blank=True,
    )
    tun_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Enabled"),
    )

    def __str__(self):
        return str(self.tun_var)

    class Meta:
        verbose_name = _("Tunable")
        verbose_name_plural = _("Tunables")
        ordering = ["tun_var"]

    class FreeAdmin:
        icon_model = "TunableIcon"
        icon_object = "TunableIcon"
        icon_add = "AddTunableIcon"
        icon_view = "ViewTunableIcon"


class Alert(Model):
    uuid = models.TextField()
    node = models.CharField(default='A', max_length=100)
    source = models.TextField()
    klass = models.TextField()
    args = DictField()
    key = models.TextField()
    datetime = models.DateTimeField()
    dismissed = models.BooleanField()
    text = models.TextField()

    class Meta:
        unique_together = (
            ('node', 'klass', 'key'),
        )


class AlertClasses(Model):
    classes = DictField(
        blank=True,
    )

    class Meta:
        verbose_name = _("Alerts")

    class FreeAdmin:
        deletable = False
        icon_model = "AlertServiceIcon"
        icon_object = "AlertServiceIcon"
        icon_view = "AlertServiceIcon"
        icon_add = "AlertServiceIcon"


class AlertService(Model):
    name = models.CharField(
        max_length=120,
        verbose_name=_("Name"),
        help_text=_("Name to identify this alert service"),
    )
    type = models.CharField(
        verbose_name=_("Type"),
        max_length=20,
        default='Mail',
    )
    attributes = DictField(
        blank=True,
        editable=False,
        verbose_name=_("Attributes"),
    )
    level = models.CharField(
        verbose_name=_("Level"),
        max_length=20,
        default='WARNING',
    )
    enabled = models.BooleanField(
        verbose_name=_("Enabled"),
        default=True,
    )

    class Meta:
        verbose_name = _("Alert Service")
        verbose_name_plural = _("Alert Services")
        ordering = ["type"]

    class FreeAdmin:
        icon_model = "AlertServiceIcon"
        icon_object = "AlertServiceIcon"
        icon_add = "AddAlertServiceIcon"
        icon_view = "ViewAlertServiceIcon"

        exclude_fields = (
            'attributes',
            'settings',
            'id',
        )

    def __str__(self):
        return self.name


class SystemDataset(Model):
    sys_pool = models.CharField(
        max_length=1024,
        blank=True,
        verbose_name=_("Pool"),
        choices=()
    )
    sys_syslog_usedataset = models.BooleanField(
        default=False,
        verbose_name=_("Syslog")
    )
    sys_uuid = models.CharField(
        editable=False,
        max_length=32,
    )
    sys_uuid_b = models.CharField(
        editable=False,
        max_length=32,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = _("System Dataset")

    class FreeAdmin:
        deletable = False
        icon_model = "SystemDatasetIcon"
        icon_object = "SystemDatasetIcon"
        icon_view = "SystemDatasetIcon"
        icon_add = "SystemDatasetIcon"


class Update(Model):
    upd_autocheck = models.BooleanField(
        verbose_name=_('Check Automatically For Updates'),
        default=True,
    )
    upd_train = models.CharField(
        max_length=50,
        blank=True,
    )

    class Meta:
        verbose_name = _('Update')

    def get_train(self):
        # FIXME: lazy import, why?
        from freenasOS import Configuration
        conf = Configuration.Configuration()
        conf.LoadTrainsConfig()
        trains = conf.AvailableTrains() or []
        if trains:
            trains = list(trains.keys())
        if not self.upd_train or self.upd_train not in trains:
            return conf.CurrentTrain()
        return self.upd_train

    def get_system_train(self):
        from freenasOS import Configuration
        conf = Configuration.Configuration()
        conf.LoadTrainsConfig()
        return conf.CurrentTrain()


class CertificateBase(Model):

    cert_type = models.IntegerField()
    cert_name = models.CharField(
        max_length=120,
        verbose_name=_("Identifier"),
        help_text=_('Internal identifier of the certificate. Only alphanumeric, "_" and "-" are allowed.'),
        unique=True,
    )
    cert_certificate = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Certificate"),
        help_text=_("Cut and paste the contents of your certificate here"),
    )
    cert_privatekey = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Private Key"),
        help_text=_("Cut and paste the contents of your private key here"),
    )
    cert_CSR = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Signing Request"),
        help_text=_("Cut and paste the contents of your CSR here"),
    )
    cert_signedby = models.ForeignKey(
        "CertificateAuthority",
        blank=True,
        null=True,
        verbose_name=_("Signing Certificate Authority"),
        on_delete=models.CASCADE
    )
    cert_revoked_date = models.DateTimeField(
        verbose_name=_('Revoked Date'),
        null=True
    )

    def __str__(self):
        return self.cert_name

    class Meta:
        abstract = True


class CertificateAuthority(CertificateBase):

    class Meta:
        verbose_name = _("CA")
        verbose_name_plural = _("CAs")


class Certificate(CertificateBase):

    cert_acme = models.ForeignKey(
        'ACMERegistration',
        on_delete=models.CASCADE,
        blank=True,
        null=True
    )
    cert_acme_uri = models.URLField(
        null=True,
        blank=True
    )
    cert_domains_authenticators = EncryptedDictField(
        null=True,
        blank=True
    )
    cert_renew_days = models.IntegerField(
        default=10,
        verbose_name=_("Renew certificate day"),  # Should we change the name ?
        help_text=_('Number of days to renew certificate before expiring'),
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = _("Certificate")
        verbose_name_plural = _("Certificates")


class CloudCredentials(Model):
    name = models.CharField(
        verbose_name=_('Account Name'),
        max_length=100,
    )
    provider = models.CharField(
        verbose_name=_('Provider'),
        max_length=50,
        choices=(),
    )
    attributes = EncryptedDictField()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Cloud Credential")


class Backup(Model):
    bak_finished = models.BooleanField(
        default=False,
        verbose_name=_("Finished")
    )

    bak_failed = models.BooleanField(
        default=False,
        verbose_name=_("Failed")
    )

    bak_acknowledged = models.BooleanField(
        default=False,
        verbose_name=_("Acknowledged")
    )

    bak_worker_pid = models.IntegerField(
        verbose_name=_("Backup worker PID"),
        null=True
    )

    bak_started_at = models.DateTimeField(
        verbose_name=_("Started at")
    )

    bak_finished_at = models.DateTimeField(
        verbose_name=_("Finished at"),
        null=True
    )

    bak_destination = models.CharField(
        max_length=1024,
        blank=True,
        verbose_name=_("Destination")
    )

    bak_status = models.CharField(
        max_length=1024,
        blank=True,
        verbose_name=_("Status")
    )

    class FreeAdmin:
        deletable = False

    class Meta:
        verbose_name = _("System Backup")


class Support(Model):
    enabled = models.NullBooleanField(
        verbose_name=_("Enable automatic support alerts to iXsystems"),
        default=False,
        null=True,
    )
    name = models.CharField(
        verbose_name=_('Name of Primary Contact'),
        max_length=200,
        blank=True,
    )
    title = models.CharField(
        verbose_name=_('Title'),
        max_length=200,
        blank=True,
    )
    email = models.EmailField(
        verbose_name=_('E-mail'),
        max_length=200,
        blank=True,
    )
    phone = models.CharField(
        verbose_name=_('Phone'),
        max_length=200,
        blank=True,
    )
    secondary_name = models.CharField(
        verbose_name=_('Name of Secondary Contact'),
        max_length=200,
        blank=True,
    )
    secondary_title = models.CharField(
        verbose_name=_('Secondary Title'),
        max_length=200,
        blank=True,
    )
    secondary_email = models.EmailField(
        verbose_name=_('Secondary E-mail'),
        max_length=200,
        blank=True,
    )
    secondary_phone = models.CharField(
        verbose_name=_('Secondary Phone'),
        max_length=200,
        blank=True,
    )

    class Meta:
        verbose_name = _("Proactive Support")

    class FreeAdmin:
        deletable = False

    @classmethod
    def is_available(cls, support=None):
        """
        Checks whether the Proactive Support tab should be shown.
        It should only be for TrueNAS and Siver/Gold Customers.

        Returns:
            tuple(bool, Support instance)
        """
        if notifier().is_freenas():
            return False, support
        if support is None:
            try:
                support = cls.objects.order_by('-id')[0]
            except IndexError:
                support = cls.objects.create()

        license = get_license()[0]
        if license is None:
            return False, support
        if license['contract_type'] in ('SILVER', 'GOLD'):
            return True, support
        return False, support

    def is_enabled(self):
        """
        Returns if the proactive support is enabled.
        This means if certain failures should be reported to iXsystems.
        Returns:
            bool
        """
        return self.is_available(support=self)[0] and self.enabled


class ACMERegistrationBody(Model):
    contact = models.EmailField(
        verbose_name=_('Contact Email')
    )
    status = models.CharField(
        verbose_name=_('Status'),
        max_length=10
    )
    key = models.TextField(
        verbose_name=_('JWKRSAKey')
    )
    acme = models.ForeignKey(
        'ACMERegistration',
        on_delete=models.CASCADE,
    )


class ACMERegistration(Model):
    uri = models.URLField(
        verbose_name=_('URI')
    )
    directory = models.URLField(
        verbose_name=_('Directory URI'),
        unique=True
    )
    tos = models.URLField(
        verbose_name=_('Terms of Service')
    )
    new_account_uri = models.URLField(
        verbose_name=_('New Account Uri')
    )
    new_nonce_uri = models.URLField(
        verbose_name=_('New Nonce Uri')
    )
    new_order_uri = models.URLField(
        verbose_name=_('New Order Uri')
    )
    revoke_cert_uri = models.URLField(
        verbose_name=_('Revoke Certificate Uri')
    )


class ACMEDNSAuthenticator(Model):
    authenticator = models.CharField(
        max_length=64,
        verbose_name=_('Authenticator')
    )
    name = models.CharField(
        max_length=64,
        unique=True,
        verbose_name=_('Name')
    )
    attributes = EncryptedDictField()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('ACME DNS Authenticator')


class Filesystem(Model):
    identifier = models.CharField(max_length=255, unique=True)


class KeyValue(Model):
    key = models.CharField(max_length=255, unique=True)
    value = models.TextField()


class KeychainCredential(Model):
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    attributes = EncryptedDictField()

    class Meta:
        verbose_name = _("Keychain Credential")
        verbose_name_plural = _("Keychain Credentials")
        ordering = ["name"]

    def __str__(self):
        return self.name


class KeychainCredentialManager(models.Manager):
    def __init__(self, type):
        self.type = type
        super().__init__()

    def get_queryset(self):
        return super().get_queryset().filter(type=self.type)


class SSHKeyPairKeychainCredential(KeychainCredential):
    objects = KeychainCredentialManager("SSH_KEY_PAIR")

    class Meta:
        proxy = True
        verbose_name = _("SSH Keypair")
        verbose_name_plural = _("SSH Keypairs")

    class FreeAdmin:
        icon_model = "SSHKeyPairKeychainCredentialIcon"
        icon_object = "SSHKeyPairKeychainCredentialIcon"
        icon_add = "SSHKeyPairKeychainCredentialIcon"
        icon_view = "SSHKeyPairKeychainCredentialIcon"

        exclude_fields = (
            "id",
            "type",
            "attributes",
        )


class SSHCredentialsKeychainCredential(KeychainCredential):
    objects = KeychainCredentialManager("SSH_CREDENTIALS")

    class Meta:
        proxy = True
        verbose_name = _("SSH Connection")
        verbose_name_plural = _("SSH Connections")

    class FreeAdmin:
        icon_model = "SSHCredentialsKeychainCredentialIcon"
        icon_object = "SSHCredentialsKeychainCredentialIcon"
        icon_add = "SSHCredentialsKeychainCredentialIcon"
        icon_view = "SSHCredentialsKeychainCredentialIcon"

        exclude_fields = (
            "id",
            "type",
            "attributes",
        )


class Reporting(Model):
    class Meta:
        verbose_name = _("Reporting")

    class FreeAdmin:
        deletable = False
        icon_model = "SystemDatasetIcon"
        icon_object = "SystemDatasetIcon"
        icon_view = "SystemDatasetIcon"
        icon_add = "SystemDatasetIcon"

    cpu_in_percentage = models.BooleanField(
        default=False,
        verbose_name=_("Report CPU usage in percent"),
        help_text=_("When set, report CPU usage in percent instead of jiffies."),
    )
    graphite = models.CharField(
        max_length=120,
        default="",
        blank=True,
        verbose_name=_("Graphite Server"),
        help_text=_("Destination hostname or IP for collectd data sent by the Graphite plugin.")
    )
    graphite_separateinstances = models.BooleanField(
        default=False,
        verbose_name=_("Graphite SeparateInstances"),
        help_text=_("If checked, when sending to Graphite, the plugin instance and type instance will be in their own "
                    "path component, for example host.cpu.0.cpu.idle. If unchecked (the default), the plugin and "
                    "plugin instance  (and likewise the type and type instance) are put into one component, "
                    "for example host.cpu-0.cpu-idle."),
    )
    graph_age = models.IntegerField(
        default=12,
        verbose_name=_("Graph Age"),
        help_text=_("Maximum age of graph stored, in months."),
    )
    graph_points = models.IntegerField(
        default=1200,
        verbose_name=_("Graph Points Count"),
        help_text=_("Number of points for each hourly, daily, weekly, monthly, yearly graph. Set this to no less than "
                    "the width of your graphs in pixels."),
    )


class Migration(Model):
    name = models.CharField(max_length=255, unique=True)


class TwoFactorAuthentication(Model):
    class Meta:
        verbose_name = _('Two Factor Authentication')

    class FreeAdmin:
        deletable = False

    otp_digits = models.IntegerField(
        default=6,
        verbose_name=_('OTP Digits')
    )

    secret = models.CharField(
        max_length=16,
        default=None,
        null=True
    )

    window = models.IntegerField(
        default=0,
        verbose_name=_('Counter Value Window')
    )

    interval = models.IntegerField(
        default=30,
        verbose_name=_('TOTP Valid Interval')
    )

    services = DictField(
        verbose_name=_('Services'),
        default={}
    )

    enabled = models.BooleanField(
        verbose_name=_('Enabled'),
        default=False
    )
