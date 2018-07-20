from middlewared.schema import Bool, Dict, Int, List, Ref, Str, accepts
from middlewared.service import CallError, ConfigService, ValidationErrors, job, periodic, private

from datetime import datetime, timedelta
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from lockfile import LockFile, LockTimeout
from mako.lookup import TemplateLookup
import markdown2

import base64
import errno
import json
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
        'mail_update',
        Str('fromemail'),
        Str('outgoingserver'),
        Int('port'),
        Str('security', enum=['PLAIN', 'SSL', 'TLS']),
        Bool('smtp'),
        Str('user'),
        Str('pass'),
        update=True
    ))
    async def do_update(self, data):
        config = await self.config()

        new = config.copy()
        new.update(data)
        new['security'] = new['security'].lower()  # Django Model compatibility

        verrors = ValidationErrors()

        if new['smtp'] and new['user'] == '':
            verrors.add('mail_update.user', 'This field is required when SMTP authentication is enabled')

        if verrors:
            raise verrors

        await self.middleware.call('datastore.update', 'system.email', config['id'], new, {'prefix': 'em_'})
        return config

    @accepts(Dict(
        'mail-message',
        Str('subject', required=True),
        Str('text', required=True),
        Str('html'),
        List('to', items=[Str('email')]),
        List('cc', items=[Str('email')]),
        Int('interval'),
        Str('channel'),
        Int('timeout', default=300),
        Bool('attachments', default=False),
        Bool('queue', default=True),
        Dict('extra_headers', additional_attrs=True),
        register=True
    ), Dict(
        'mail-config',
        additional_attrs=True,
        register=True
    ))
    @job(pipes=['input'], check_pipes=False)
    def send(self, job, message, config=None):
        """
        Sends mail using configured mail settings.

        If `attachments` is true, a list compromised of the following dict is required
        via HTTP upload:
          - headers(list)
            - name(str)
            - value(str)
            - params(dict)
          - content (str)

        [
         {
          "headers": [
           {
            "name": "Content-Transfer-Encoding",
            "value": "base64"
           },
           {
            "name": "Content-Type",
            "value": "application/octet-stream",
            "params": {
             "name": "test.txt"
            }
           }
          ],
          "content": "dGVzdAo="
         }
        ]
        """

        gc = self.middleware.call_sync('datastore.config', 'network.globalconfiguration')

        hostname = f'{gc["gc_hostname"]}.{gc["gc_domain"]}'

        message['subject'] = f'{hostname}: {message["subject"]}'

        if 'html' not in message:
            lookup = TemplateLookup(
                directories=[os.path.join(os.path.dirname(os.path.realpath(__file__)), '../assets/templates')],
                module_directory="/tmp/mako/templates")

            tmpl = lookup.get_template('mail.html')

            message['html'] = tmpl.render(body=markdown2.markdown(message['text']))

        return self.send_raw(job, message, config)

    @accepts(Ref('mail-message'), Ref('mail-config'))
    @job(pipes=['input'], check_pipes=False)
    @private
    def send_raw(self, job, message, config=None):
        interval = message.get('interval')
        if interval is None:
            interval = timedelta()
        else:
            interval = timedelta(seconds=interval)

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

        if not config:
            config = self.middleware.call_sync('mail.config')
        to = message.get('to')
        if not to:
            to = [
                self.middleware.call_sync(
                    'user.query', [('username', '=', 'root')], {'get': True}
                )['email']
            ]
            if not to[0]:
                raise CallError('Email address for root is not configured')

        if message.get('attachments'):
            job.check_pipe("input")

            def read_json():
                f = job.pipes.input.r
                data = b''
                i = 0
                while True:
                    read = f.read(1048576)  # 1MiB
                    if read == b'':
                        break
                    data += read
                    i += 1
                    if i > 50:
                        raise ValueError('Attachments bigger than 50MB not allowed yet')
                if data == b'':
                    return None
                return json.loads(data)

            attachments = read_json()
        else:
            attachments = None

        if 'html' in message or attachments:
            msg = MIMEMultipart()
            msg.preamble = message['text']
            if 'html' in message:
                msg2 = MIMEMultipart('alternative')
                msg2.attach(MIMEText(message['text'], 'plain', _charset='utf-8'))
                msg2.attach(MIMEText(message['html'], 'html', _charset='utf-8'))
                msg.attach(msg2)
            if attachments:
                for attachment in attachments:
                    m = Message()
                    m.set_payload(attachment['content'])
                    for header in attachment.get('headers'):
                        m.add_header(header['name'], header['value'], **(header.get('params') or {}))
                    msg.attach(m)
        else:
            msg = MIMEText(message['text'], _charset='utf-8')

        msg['Subject'] = message['subject']

        msg['From'] = config['fromemail']
        msg['To'] = ', '.join(to)
        if message.get('cc'):
            msg['Cc'] = ', '.join(message.get('cc'))
        msg['Date'] = formatdate()

        local_hostname = socket.gethostname()

        msg['Message-ID'] = "<%s-%s.%s@%s>" % (sw_name.lower(), datetime.utcnow().strftime("%Y%m%d.%H%M%S.%f"), base64.urlsafe_b64encode(os.urandom(3)), local_hostname)

        extra_headers = message.get('extra_headers') or {}
        for key, val in list(extra_headers.items()):
            if key in msg:
                msg.replace_header(key, val)
            else:
                msg[key] = val

        syslog.openlog(logoption=syslog.LOG_PID, facility=syslog.LOG_MAIL)
        try:
            server = self._get_smtp_server(config, message['timeout'], local_hostname=local_hostname)
            # NOTE: Don't do this.
            #
            # If smtplib.SMTP* tells you to run connect() first, it's because the
            # mailserver it tried connecting to via the outgoing server argument
            # was unreachable and it tried to connect to 'localhost' and barfed.
            # This is because FreeNAS doesn't run a full MTA.
            # else:
            #    server.connect()
            headers = '\n'.join([f'{k}: {v}' for k, v in msg._headers])
            syslog.syslog(f"sending mail to {', '.join(to)}\n{headers}")
            server.sendmail(config['fromemail'], to, msg.as_string())
            server.quit()
        except ValueError as ve:
            # Don't spam syslog with these messages. They should only end up in the
            # test-email pane.
            raise CallError(str(ve))
        except Exception as e:
            syslog.syslog(f'Failed to send email to {", ".join(to)}: {str(e)}')
            if isinstance(e, smtplib.SMTPAuthenticationError):
                raise CallError(f'Authentication error ({e.smtp_code}): {e.smtp_error}', errno.EAUTH)
            self.logger.warn('Failed to send email: %s', str(e), exc_info=True)
            if message['queue']:
                with MailQueue() as mq:
                    mq.append(msg)
            raise CallError(f'Failed to send email: {e}')
        return True

    def _get_smtp_server(self, config, timeout=300, local_hostname=None):
        if local_hostname is None:
            local_hostname = socket.gethostname()

        if not config['outgoingserver'] or not config['port']:
            # See NOTE below.
            raise ValueError('you must provide an outgoing mailserver and mail'
                             ' server port when sending mail')
        if config['security'] == 'SSL':
            server = smtplib.SMTP_SSL(
                config['outgoingserver'],
                config['port'],
                timeout=timeout,
                local_hostname=local_hostname)
        else:
            server = smtplib.SMTP(
                config['outgoingserver'],
                config['port'],
                timeout=timeout,
                local_hostname=local_hostname)
            if config['security'] == 'TLS':
                server.starttls()
        if config['smtp']:
            server.login(config['user'], config['pass'])
        return server

    @periodic(600, run_on_start=False)
    @private
    def send_mail_queue(self):

        with MailQueue() as mq:
            for queue in list(mq.queue):
                try:
                    config = self.middleware.call_sync('mail.config')
                    server = self._get_smtp_server(config)
                    server.sendmail(queue.message['From'], queue.message['To'].split(', '), queue.message.as_string())
                    server.quit()
                except Exception:
                    self.logger.debug('Sending message from queue failed', exc_info=True)
                    queue.attempts += 1
                    if queue.attempts >= mq.MAX_ATTEMPTS:
                        mq.queue.remove(queue)
                else:
                    mq.queue.remove(queue)
