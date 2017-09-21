#
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
import glob
import logging
import os
import base64
import pickle
import re
import shutil
import smtplib
import sqlite3
import subprocess
import syslog
import ntplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from datetime import datetime, timedelta
from django.utils.translation import ugettext_lazy as _
from lockfile import LockFile, LockTimeout
from .log import log_traceback

RE_MOUNT = re.compile(
    r'^(?P<fs_spec>.+?) on (?P<fs_file>.+?) \((?P<fs_vfstype>\w+)', re.S
)
VERSION_FILE = '/etc/version'
_VERSION = None
log = logging.getLogger("common.system")


def get_sw_version(strip_build_num=False):
    """Return the full version string, e.g. FreeNAS-8.1-r7794-amd64."""
    try:
        from freenasOS import Configuration
    except ImportError:
        Configuration = None

    global _VERSION

    if _VERSION is None:
        # See #9113
        if Configuration:
            conf = Configuration.Configuration()
            sys_mani = conf.SystemManifest()
            if sys_mani:
                _VERSION = sys_mani.Sequence()
        if _VERSION is None:
            with open(VERSION_FILE) as fd:
                _VERSION = fd.read().strip()
    if strip_build_num:
        return _VERSION.split(' ')[0]
    return _VERSION


def get_sw_login_version():
    """Return a shortened version string, e.g. 8.0.1-RC1, 8.1, etc. """

    return '-'.join(get_sw_version(strip_build_num=True).split('-')[1:-2])


def get_sw_name():
    """Return the software name, e.g. FreeNAS"""

    return get_sw_version().split('-')[0]


def get_freenas_var_by_file(f, var):
    assert f and var

    pipe = os.popen('. "%s"; echo "${%s}"' % (f, var, ))
    try:
        val = pipe.readlines()[-1].rstrip()
    finally:
        pipe.close()

    return val


def get_freenas_var(var, default=None):
    val = get_freenas_var_by_file("/etc/rc.freenas", var)
    if not val:
        val = default
    return val

FREENAS_DATABASE = get_freenas_var("FREENAS_CONFIG", "/data/freenas-v1.db")


class QueueItem(object):

    def __init__(self, message):
        self.attempts = 0
        self.message = message


class MailQueue(object):

    QUEUE_FILE = '/tmp/mail.queue'
    MAX_ATTEMPTS = 3

    def __init__(self):
        self.queue = None

    def append(self, message):
        self.queue.append(QueueItem(message))

    @classmethod
    def is_empty(cls):
        if not os.path.exists(cls.QUEUE_FILE):
            return True
        try:
            return os.stat(cls.QUEUE_FILE).st_size == 0
        except OSError:
            return True

    def _get_queue(self):
        try:
            with open(self.QUEUE_FILE, 'rb') as f:
                self.queue = pickle.loads(f.read())
        except (pickle.PickleError, EOFError):
            self.queue = []

    def __enter__(self):
        self._lock = LockFile(self.QUEUE_FILE)
        while not self._lock.i_am_locking():
            try:
                self._lock.acquire(timeout=330)
            except LockTimeout:
                self._lock.break_lock()

        if not os.path.exists(self.QUEUE_FILE):
            open(self.QUEUE_FILE, 'a').close()

        self._get_queue()
        return self

    def __exit__(self, typ, value, traceback):

        with open(self.QUEUE_FILE, 'wb+') as f:
            if self.queue:
                f.write(pickle.dumps(self.queue))

        self._lock.release()
        if typ is not None:
            raise


def _get_local_hostname():
    from freenasUI.network.models import GlobalConfiguration
    try:
        gc = GlobalConfiguration.objects.order_by('-id')[0]
        local_hostname = "%s.%s" % (gc.get_hostname(), gc.gc_domain)
    except:
        local_hostname = "%s.local" % get_sw_name()
    return local_hostname


def _get_smtp_server(timeout=300, local_hostname=None):
    from freenasUI.system.models import Email

    if local_hostname is None:
        local_hostname = _get_local_hostname()

    em = Email.objects.all().order_by('-id')[0]
    if not em.em_outgoingserver or not em.em_port:
        # See NOTE below.
        raise ValueError('you must provide an outgoing mailserver and mail'
                         ' server port when sending mail')
    if em.em_security == 'ssl':
        server = smtplib.SMTP_SSL(
            em.em_outgoingserver,
            em.em_port,
            timeout=timeout,
            local_hostname=local_hostname)
    else:
        server = smtplib.SMTP(
            em.em_outgoingserver,
            em.em_port,
            timeout=timeout,
            local_hostname=local_hostname)
        if em.em_security == 'tls':
            server.starttls()
    if em.em_smtp:
        server.login(em.em_user, em.em_pass)
    return server


def send_mail(
    subject=None, text=None, interval=None, channel=None,
    to=None, extra_headers=None, attachments=None, timeout=300,
    queue=True,
):
    from freenasUI.account.models import bsdUsers
    from freenasUI.system.models import Email

    syslog.openlog(logoption=syslog.LOG_PID, facility=syslog.LOG_MAIL)
    if interval is None:
        interval = timedelta()

    if not channel:
        channel = get_sw_name().lower()
    if interval > timedelta():
        channelfile = '/tmp/.msg.%s' % (channel)
        last_update = datetime.now() - interval
        try:
            last_update = datetime.fromtimestamp(os.stat(channelfile).st_mtime)
        except OSError:
            pass
        timediff = datetime.now() - last_update
        if (timediff >= interval) or (timediff < timedelta()):
            # Make sure mtime is modified
            # We could use os.utime but this is simpler!
            with open(channelfile, 'w') as f:
                f.write('!')
        else:
            return True, 'This message was already sent in the given interval'

    error = False
    errmsg = ''
    em = Email.objects.all().order_by('-id')[0]
    if not to:
        to = [bsdUsers.objects.get(bsdusr_username='root').bsdusr_email]
        if not to[0]:
            return True, 'Email address for root is not configured'
    if attachments:
        msg = MIMEMultipart()
        msg.preamble = text
        list(map(lambda attachment: msg.attach(attachment), attachments))
    else:
        msg = MIMEText(text, _charset='utf-8')
    if subject:
        msg['Subject'] = subject

    msg['From'] = em.em_fromemail
    msg['To'] = ', '.join(to)
    msg['Date'] = formatdate()

    local_hostname = _get_local_hostname()

    msg['Message-ID'] = "<%s-%s.%s@%s>" % (get_sw_name().lower(), datetime.utcnow().strftime("%Y%m%d.%H%M%S.%f"), base64.urlsafe_b64encode(os.urandom(3)), local_hostname)

    if not extra_headers:
        extra_headers = {}
    for key, val in list(extra_headers.items()):
        if key in msg:
            msg.replace_header(key, val)
        else:
            msg[key] = val

    try:
        server = _get_smtp_server(timeout, local_hostname=local_hostname)
        # NOTE: Don't do this.
        #
        # If smtplib.SMTP* tells you to run connect() first, it's because the
        # mailserver it tried connecting to via the outgoing server argument
        # was unreachable and it tried to connect to 'localhost' and barfed.
        # This is because FreeNAS doesn't run a full MTA.
        # else:
        #    server.connect()
        syslog.syslog("sending mail to " + ','.join(to) + msg.as_string()[0:140])
        server.sendmail(em.em_fromemail, to, msg.as_string())
        server.quit()
    except ValueError as ve:
        # Don't spam syslog with these messages. They should only end up in the
        # test-email pane.
        errmsg = str(ve)
        error = True
    except Exception as e:
        errmsg = str(e)
        log.warn('Failed to send email: %s', errmsg, exc_info=True)
        error = True
        if queue:
            with MailQueue() as mq:
                mq.append(msg)
    except smtplib.SMTPAuthenticationError as e:
        errmsg = "%d %s" % (e.smtp_code, e.smtp_error)
        error = True
    except:
        errmsg = "Unexpected error."
        error = True
    return error, errmsg


def send_mail_queue():

    with MailQueue() as mq:
        for queue in list(mq.queue):
            try:
                server = _get_smtp_server()
                server.sendmail(queue.message['From'], queue.message['To'].split(', '), queue.message.as_string())
                server.quit()
            except:
                log.debug('Sending message from queue failed', exc_info=True)
                queue.attempts += 1
                if queue.attempts >= mq.MAX_ATTEMPTS:
                    mq.queue.remove(queue)
            else:
                mq.queue.remove(queue)


def get_fstype(path):
    assert path

    if not os.access(path, os.F_OK):
        return None

    lines = subprocess.check_output(['/bin/df', '-T', path], encoding='utf8').splitlines()

    out = (lines[len(lines) - 1]).split()

    return (out[1].upper())


def get_mounted_filesystems():
    """Return a list of dict with info of mounted file systems

    Each dict is composed of:
        - fs_spec (src)
        - fs_file (dest)
        - fs_vfstype
    """
    mounted = []

    lines = subprocess.check_output(['/sbin/mount'], encoding='utf8').splitlines()

    for line in lines:
        reg = RE_MOUNT.search(line)
        if not reg:
            continue
        mounted.append(reg.groupdict())

    return mounted


def is_mounted(**kwargs):

    mounted = get_mounted_filesystems()
    for mountpt in mounted:
        ret = False
        if 'device' in kwargs:
            ret = True if mountpt['fs_spec'] == kwargs['device'] else False
        if 'path' in kwargs:
            ret = True if mountpt['fs_file'] == kwargs['path'] else False
        if ret:
            break

    return ret


def mount(dev, path, mntopts=None, fstype=None):
    mount_cmd = ['/sbin/mount']

    if isinstance(dev, str):
        dev = dev.encode('utf-8')

    if isinstance(path, str):
        path = path.encode('utf-8')

    if mntopts:
        opts = ['-o', mntopts]
    else:
        opts = []

    if fstype == 'ntfs':
        mount_cmd = ['/usr/local/bin/ntfs-3g']
        fstype = []
    else:
        fstype = ['-t', fstype] if fstype else []

    proc = subprocess.Popen(
        mount_cmd + opts + fstype + [dev, path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf8',
    )
    output = proc.communicate()

    if proc.returncode != 0:
        log.debug("Mount failed (%s): %s", proc.returncode, output)
        raise ValueError(_("Mount failed {0} -> {1}, {2}" .format(
            proc.returncode,
            output[0],
            output[1]
        )))
    else:
        return True


def umount(path, force=False):

    if force:
        cmdlst = ['/sbin/umount', '-f', path]
    else:
        cmdlst = ['/sbin/umount', path]
    proc = subprocess.Popen(
        cmdlst,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf8',
    )
    output = proc.communicate()

    if proc.returncode != 0:
        log.debug("Umount failed (%s): %s", proc.returncode, output)
        raise ValueError(_("Unmount Failed {0} -> {1} {2}".format(
            proc.returncode,
            output[0],
            output[1]
        )))
    else:
        return True


def service_enabled(name):
    h = sqlite3.connect(FREENAS_DATABASE)
    c = h.cursor()

    enabled = False
    sql = "select srv_enable from services_services " \
        "where srv_service = '%s' order by -id limit 1" % name
    c.execute(sql)
    row = c.fetchone()
    if row and row[0] != 0:
        enabled = True

    c.close()
    h.close()

    return enabled


def ldap_enabled():
    from freenasUI.directoryservice.models import LDAP

    enabled = False
    try:
        ldap = LDAP.objects.all()[0]
        enabled = ldap.ldap_enable

    except:
        enabled = False

    return enabled


def ldap_sudo_configured():
    from freenasUI.directoryservice.models import LDAP

    enabled = False
    try:
        ldap = LDAP.objects.all()[0]
        if ldap.ldap_sudosuffix:
            enabled = True

    except:
        enabled = False

    return enabled


def ldap_has_samba_schema():
    from freenasUI.directoryservice.models import LDAP

    has_samba_schema = False
    try:
        ldap = LDAP.objects.all()[0]
        if ldap.ldap_has_samba_schema:
            has_samba_schema = True

    except:
        has_samba_schema = False

    return has_samba_schema


def ldap_anonymous_bind():
    from freenasUI.directoryservice.models import LDAP

    anonymous_bind = False
    try:
        ldap = LDAP.objects.all()[0]
        if ldap.ldap_anonbind:
            anonymous_bind = True

    except:
        anonymous_bind = False

    return anonymous_bind


def ldap_objects():
    from freenasUI.directoryservice.models import LDAP

    return LDAP.objects.all()


def activedirectory_enabled():
    from freenasUI.directoryservice.models import ActiveDirectory

    enabled = False
    try:
        ad = ActiveDirectory.objects.all()[0]
        enabled = ad.ad_enable

    except:
        log_traceback(log=log)
        enabled = False

    return enabled


def activedirectory_has_unix_extensions():
    from freenasUI.directoryservice.models import ActiveDirectory

    ad_unix_extensions = False
    try:
        ad = ActiveDirectory.objects.all()[0]
        ad_unix_extensions = ad.ad_unix_extensions

    except:
        ad_unix_extensions = False

    return ad_unix_extensions


def activedirectory_has_principal():
    from freenasUI.directoryservice.models import ActiveDirectory

    ad_has_principal = False
    try:
        ad = ActiveDirectory.objects.all()[0]
        if ad.ad_kerberos_principal:
            ad_has_principal = True

    except Exception:
        ad_has_principal = False

    return ad_has_principal


def activedirectory_objects():
    from freenasUI.directoryservice.models import ActiveDirectory

    return ActiveDirectory.objects.all()


def domaincontroller_enabled():
    return service_enabled('domaincontroller')


def domaincontroller_objects():
    h = sqlite3.connect(FREENAS_DATABASE)
    h.row_factory = sqlite3.Row
    c = h.cursor()

    results = c.execute("SELECT * FROM services_domaincontroller ORDER BY -id")

    objects = []
    for row in results:
        obj = {}
        for key in list(row.keys()):
            obj[key] = row[key]
        objects.append(obj)

    c.close()
    h.close()
    return objects


def nis_enabled():
    from freenasUI.directoryservice.models import NIS

    enabled = False
    try:
        nis = NIS.objects.all()[0]
        enabled = nis.nis_enable

    except:
        enabled = False

    return enabled


def nis_objects():
    from freenasUI.directoryservice.models import NIS

    return NIS.objects.all()


def kerberosrealm_objects():
    from freenasUI.directoryservice.models import KerberosRealm

    return KerberosRealm.objects.all()


def kerberoskeytab_objects():
    from freenasUI.directoryservice.models import KerberosKeytab

    return KerberosKeytab.objects.all()


def exclude_path(path, exclude):

    if isinstance(path, bytes):
        path = path.decode('utf8')

    exclude = [y.decode('utf8') if isinstance(y, bytes) else y for y in exclude]

    fine_grained = []
    for e in exclude:
        if not e.startswith(path):
            continue
        fine_grained.append(e)

    if fine_grained:
        apply_paths = []
        check_paths = [os.path.join(path, f) for f in os.listdir(path)]
        while check_paths:
            fpath = check_paths.pop()
            if not os.path.isdir(fpath):
                apply_paths.append(fpath)
                continue
            for fg in fine_grained:
                if fg.startswith(fpath):
                    if fg != fpath:
                        check_paths.extend([
                            os.path.join(fpath, f)
                            for f in os.listdir(fpath)
                        ])
                else:
                    apply_paths.append(fpath)
        return apply_paths
    else:
        return [path]


def backup_database():
    from freenasUI.middleware.client import client
    from freenasUI.middleware.notifier import notifier

    with client as c:
        systemdataset = c.call('systemdataset.config')
    systempath = notifier().system_dataset_path()
    if not systempath or not systemdataset:
        return

    # Legacy format
    files = glob.glob('%s/*.db' % systempath)
    reg = re.compile(r'.*(\d{4}-\d{2}-\d{2})-(\d+)\.db$')
    files = [y for y in files if reg.match(y)]
    for f in files:
        try:
            os.unlink(f)
        except OSError:
            pass

    today = datetime.now().strftime("%Y%m%d")

    newfile = os.path.join(
        systempath,
        'configs-%s' % systemdataset['uuid'],
        get_sw_version(),
        '%s.db' % today,
    )

    dirname = os.path.dirname(newfile)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    shutil.copy('/data/freenas-v1.db', newfile)


def get_dc_hostname():
    from freenasUI.network.models import GlobalConfiguration
    from freenasUI.common.pipesubr import pipeopen

    gc_hostname = gc_domain = hostname = None
    try:
        gc = GlobalConfiguration.objects.all()[0]
        gc_hostname = gc.get_hostname()
        gc_domain = gc.gc_domain

    except:
        pass

    if gc_hostname and gc_domain:
        hostname = "%s.%s" % (gc_hostname, gc_domain)
    elif gc_hostname:
        hostname = gc_hostname
    else:
        p = pipeopen("/bin/hostname", allowfork=True)
        out = p.communicate()
        if p.returncode == 0:
            hostname = out[0].strip()

    return hostname


def get_hostname():
    from freenasUI.network.models import GlobalConfiguration
    from freenasUI.common.pipesubr import pipeopen

    hostname = None
    try:
        gc = GlobalConfiguration.objects.all()[0]
        hostname = gc.get_hostname()

    except:
        pass

    if not hostname:
        p = pipeopen("/bin/hostname", allowfork=True)
        out = p.communicate()
        if p.returncode == 0:
            buf = out[0].strip()
            parts = buf.split('.')
            hostname = parts[0]

    return hostname


def validate_netbios_name(netbiosname):
    regex = re.compile(r"^[a-zA-Z0-9\.\-_!@#\$%^&\(\)'\{\}~]{1,15}$")

    if not regex.match(netbiosname):
        raise Exception("Invalid NetBIOS name")


def compare_netbios_names(netbiosname1, netbiosname2, validate_func=validate_netbios_name):
    if not netbiosname1 or not netbiosname2:
        return False

    netbiosname1_parts = []
    if ',' in netbiosname1:
        netbiosname1_parts = netbiosname1.split(',')
    elif ' ' in netbiosname1:
        netbiosname1_parts = netbiosname1.split()
    else:
        netbiosname1_parts = [netbiosname1]

    netbiosname2_parts = []
    if ',' in netbiosname2:
        netbiosname2_parts = netbiosname2.split(',')
    elif ' ' in netbiosname1:
        netbiosname2_parts = netbiosname2.split()
    else:
        netbiosname2_parts = [netbiosname2]

    if not netbiosname1_parts or not netbiosname2_parts:
        return False

    for n1 in netbiosname1_parts:
        if validate_func:
            validate_func(n1)

        for n2 in netbiosname2_parts:
            if validate_func:
                validate_func(n2)

            if n1.lower() == n2.lower():
                return True

    return False


def test_ntp_server(addr):
    client = ntplib.NTPClient()
    server_alive = False
    try:
        response = client.request(addr)
        if response.version:
            server_alive = True
    except:
        pass

    return server_alive
