from middlewared.schema import Bool, Dict, Int, List, Str, accepts
from middlewared.service import CallError, ConfigService, ValidationErrors, private

from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from lockfile import LockFile, LockTimeout

import base64
import errno
import os
import pickle
import smtplib
import socket
import syslog


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


class MailService(ConfigService):

    class Config:
        datastore = 'system.email'
        datastore_prefix = 'em_'
        datastore_extend = 'mail.mail_extend'

    @private
    async def mail_extend(self, cfg):
        if cfg['security']:
            cfg['security'] = cfg['security'].upper()
        return cfg

    @accepts(Dict(
        'mail',
        Str('fromemail'),
        Str('outgoingserver'),
        Int('port'),
        Str('security', enum=['PLAIN', 'SSL', 'TLS']),
        Bool('smtp'),
        Str('user'),
        Str('pass'),
    ))
    async def do_update(self, data):
        config = await self.config()

        new = config.copy()
        new.update(data)
        new['security'] = new['security'].lower()  # Django Model compatibility

        verrors = ValidationErrors()

        if new['smtp'] and new['user'] == '':
            verrors.add('user', 'This field is required when SMTP authentication is enabled')

        if verrors:
            raise verrors

        await self.middleware.call('datastore.update', 'system.email', config['id'], new)
        return config['id']

    @accepts(Dict(
        'mail-message',
        Str('subject'),
        Str('text', required=True),
        List('to', items=[Str('email')]),
        Int('interval'),
        Str('channel'),
        Int('timeout', default=300),
        Bool('queue', default=True),
    ))
    def send(self, message):
        """
        Sends mail using configured mail settings.
        """

        syslog.openlog(logoption=syslog.LOG_PID, facility=syslog.LOG_MAIL)
        interval = message.get('interval')
        if interval is None:
            interval = timedelta()

        sw_name = self.middleware.call_sync('system.info')['version'].split('-', 1)[0]

        channel = message.get('channel')
        if not channel:
            channel = sw_name.lower()
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
                raise CallError('This message was already sent in the given interval')

        em = self.middleware.call_sync('mail.config')
        to = message.get('to')
        if not to:
            to = [
                self.middleware.call_sync(
                    'user.query', [('username', '=', 'root')], {'get': True}
                )['email']
            ]
            if not to[0]:
                raise CallError('Email address for root is not configured')

        attachments = []  # FIXME: implement attachments
        if attachments:
            msg = MIMEMultipart()
            msg.preamble = message['text']
            list(map(lambda attachment: msg.attach(attachment), attachments))
        else:
            msg = MIMEText(message['text'], _charset='utf-8')

        subject = message.get('subject')
        if subject:
            msg['Subject'] = subject

        msg['From'] = em['fromemail']
        msg['To'] = ', '.join(to)
        msg['Date'] = formatdate()

        local_hostname = socket.gethostname()

        msg['Message-ID'] = "<%s-%s.%s@%s>" % (sw_name.lower(), datetime.utcnow().strftime("%Y%m%d.%H%M%S.%f"), base64.urlsafe_b64encode(os.urandom(3)), local_hostname)

        extra_headers = message.get('extra_headers') or {}
        for key, val in list(extra_headers.items()):
            if key in msg:
                msg.replace_header(key, val)
            else:
                msg[key] = val

        try:
            server = self._get_smtp_server(message['timeout'], local_hostname=local_hostname)
            # NOTE: Don't do this.
            #
            # If smtplib.SMTP* tells you to run connect() first, it's because the
            # mailserver it tried connecting to via the outgoing server argument
            # was unreachable and it tried to connect to 'localhost' and barfed.
            # This is because FreeNAS doesn't run a full MTA.
            # else:
            #    server.connect()
            syslog.syslog("sending mail to " + ','.join(to) + msg.as_string()[0:140])
            server.sendmail(em['fromemail'], to, msg.as_string())
            server.quit()
        except ValueError as ve:
            # Don't spam syslog with these messages. They should only end up in the
            # test-email pane.
            raise CallError(str(ve))
        except Exception as e:
            self.logger.warn('Failed to send email: %s', str(e), exc_info=True)
            if message['queue']:
                with MailQueue() as mq:
                    mq.append(msg)
            raise CallError(f'Failed to send email: {e}')
        except smtplib.SMTPAuthenticationError as e:
            raise CallError(f'Authentication error ({e.smtp_code}): {e.smtp_error}', errno.EAUTH)
        return True

    def _get_smtp_server(self, timeout=300, local_hostname=None):
        if local_hostname is None:
            local_hostname = socket.gethostname()

        em = self.middleware.call_sync('mail.config')
        if not em['outgoingserver'] or not em['port']:
            # See NOTE below.
            raise ValueError('you must provide an outgoing mailserver and mail'
                             ' server port when sending mail')
        if em['security'] == 'SSL':
            server = smtplib.SMTP_SSL(
                em['outgoingserver'],
                em['port'],
                timeout=timeout,
                local_hostname=local_hostname)
        else:
            server = smtplib.SMTP(
                em['outgoingserver'],
                em['port'],
                timeout=timeout,
                local_hostname=local_hostname)
            if em['security'] == 'TLS':
                server.starttls()
        if em['smtp']:
            server.login(em['user'], em['pass'])
        return server

    @private
    def send_mail_queue(self):

        with MailQueue() as mq:
            for queue in list(mq.queue):
                try:
                    server = self._get_smtp_server()
                    server.sendmail(queue.message['From'], queue.message['To'].split(', '), queue.message.as_string())
                    server.quit()
                except:
                    self.logger.debug('Sending message from queue failed', exc_info=True)
                    queue.attempts += 1
                    if queue.attempts >= mq.MAX_ATTEMPTS:
                        mq.queue.remove(queue)
                else:
                    mq.queue.remove(queue)
