import base64
from collections import deque
import contextlib
from datetime import datetime, timedelta
from email.header import Header
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
import errno
import html
import json
import os
import smtplib
from threading import Lock

import html2text

from middlewared.api import api_method
from middlewared.api.current import (MailEntry, MailUpdateArgs, MailUpdateResult, MailSendArgs, MailSendResult,
                                     MailLocalAdministratorEmailArgs, MailLocalAdministratorEmailResult)
from middlewared.service import (
    CallError, ConfigService, NetworkActivityDisabled, ValidationErrors, job, periodic, private,
)
import middlewared.sqlalchemy as sa
from middlewared.utils import ProductName, BRAND
from middlewared.utils.mako import get_template


class QueueItem:
    def __init__(self, message):
        self.attempts = 0
        self.message = message


class MailQueue:
    MAX_ATTEMPTS = 3
    MAX_QUEUE_LIMIT = 20

    def __init__(self):
        self.queue = deque(maxlen=self.MAX_QUEUE_LIMIT)
        self.lock = Lock()

    def append(self, message):
        self.queue.append(QueueItem(message))

    def __enter__(self):
        self.lock.acquire()
        return self

    def __exit__(self, typ, value, traceback):
        self.lock.release()
        if typ is not None:
            raise


class MailModel(sa.Model):
    __tablename__ = 'system_email'

    id = sa.Column(sa.Integer(), primary_key=True)
    em_fromemail = sa.Column(sa.String(120), default='')
    em_outgoingserver = sa.Column(sa.String(120))
    em_port = sa.Column(sa.Integer(), default=25)
    em_security = sa.Column(sa.String(120), default="plain")
    em_smtp = sa.Column(sa.Boolean())
    em_user = sa.Column(sa.String(120), nullable=True)
    em_pass = sa.Column(sa.EncryptedText(), nullable=True)
    em_fromname = sa.Column(sa.String(120), default='')
    em_oauth = sa.Column(sa.JSON(dict, encrypted=True), nullable=True)


class MailService(ConfigService):
    mail_queue = MailQueue()

    class Config:
        datastore = 'system.email'
        datastore_prefix = 'em_'
        datastore_extend = 'mail.mail_extend'
        cli_namespace = 'system.mail'
        role_prefix = 'ALERT'
        entry = MailEntry

    @private
    async def mail_extend(self, cfg):
        if cfg['security']:
            cfg['security'] = cfg['security'].upper()

        return cfg

    @api_method(MailUpdateArgs, MailUpdateResult)
    async def do_update(self, data):
        """Update Mail Service Configuration."""
        config = await self.config()

        new = config.copy()
        new.update(data)
        new['security'] = new['security'].lower()  # Django Model compatibility

        verrors = ValidationErrors()

        if new['smtp'] and new['user'] == '':
            verrors.add(
                'mail_update.user',
                'This field is required when SMTP authentication is enabled',
            )

        if not new['oauth'] or new['oauth']['provider'] == 'outlook':
            if not new['fromemail']:
                verrors.add('mail_update.fromemail', 'This field is required')

        self.__password_verify(new['pass'], 'mail_update.pass', verrors)

        verrors.check()

        await self.middleware.call('datastore.update', 'system.email', config['id'], new, {'prefix': 'em_'})

        await self.middleware.call('mail.gmail_initialize')
        await self.middleware.call('alert.oneshot_delete', 'GMailConfigurationDiscarded', None)

        return await self.config()

    def __password_verify(self, password, schema, verrors=None):
        if verrors is None:
            verrors = ValidationErrors()
        if not password:
            return verrors
        # FIXME: smtplib does not support non-ascii password yet
        # https://github.com/python/cpython/pull/8938
        try:
            password.encode('ascii')
        except UnicodeEncodeError:
            verrors.add(
                schema,
                'Only plain text characters (7-bit ASCII) are allowed in passwords. '
                'UTF or composed characters are not allowed.'
            )
        return verrors

    @api_method(MailSendArgs, MailSendResult, roles=['MAIL_WRITE'])
    @job(pipes=['input'], check_pipes=False)
    def send(self, job, message, config):
        """Sends mail using configured mail settings."""

        gc = self.middleware.call_sync('datastore.config', 'network.globalconfiguration')
        hostname = f'{gc["gc_hostname"]}.{gc["gc_domain"]}'
        message['subject'] = f'{ProductName.PRODUCT_NAME} {hostname}: {message["subject"]}'
        add_html = True
        if 'html' in message and message['html'] is None:
            message.pop('html')
            add_html = False

        if 'text' not in message:
            if 'html' not in message:
                verrors = ValidationErrors()
                verrors.add('mail_message.text', 'Text is required when HTML is not set')
                verrors.check()

            message['text'] = html2text.html2text(message['html'])

        if add_html and 'html' not in message:
            template = get_template('assets/templates/mail.html')
            message['html'] = template.render(body=html.escape(message['text']).replace('\n', '<br>\n'))

        return self.send_raw(job, message, config)

    @job(pipes=['input'], check_pipes=False)
    @private
    def send_raw(self, job, message, config):
        config = dict(self.middleware.call_sync('mail.config'), **config)

        from_addr = self._from_addr(config)

        interval = message.get('interval')
        if interval is None:
            interval = timedelta()
        else:
            interval = timedelta(seconds=interval)

        if interval > timedelta():
            channelfile = f'/tmp/.msg.{message.get("channel") or BRAND.lower()}'
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

        verrors = self.__password_verify(config['pass'], 'mail_update.pass')
        verrors.check()
        to = message.get('to')
        if not to:
            to = self.middleware.call_sync('mail.local_administrators_emails')
            if not to:
                raise CallError('None of the local administrators has an e-mail address configured')

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
            msg.preamble = 'This is a multi-part message in MIME format.'
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

        msg['From'] = from_addr
        msg['To'] = ', '.join(to)
        if message.get('cc'):
            msg['Cc'] = ', '.join(message.get('cc'))
        msg['Date'] = formatdate()

        local_hostname = self.middleware.call_sync('system.hostname')

        msg['Message-ID'] = make_msgid(base64.urlsafe_b64encode(os.urandom(3)).decode("ascii"))

        extra_headers = message.get('extra_headers') or {}
        for key, val in list(extra_headers.items()):
            # We already have "Content-Type: multipart/mixed" and setting "Content-Type: text/plain" like some scripts
            # do will break python e-mail module.
            if key.lower() == "content-type":
                continue

            if key in msg:
                msg.replace_header(key, val)
            else:
                msg[key] = val

        try:
            if config['oauth'] and config['oauth']['provider'] == 'gmail':
                self.middleware.call_sync('mail.gmail_send', msg, config)
            else:
                with self._get_smtp_server(config, message['timeout'], local_hostname=local_hostname) as server:
                    # NOTE: Don't do this.
                    #
                    # If smtplib.SMTP* tells you to run connect() first, it's because the
                    # mailserver it tried connecting to via the outgoing server argument
                    # was unreachable, and it tried to connect to 'localhost' and barfed.
                    # This is because FreeNAS doesn't run a full MTA.
                    # else:
                    #    server.connect()
                    server.sendmail(
                        # `from_addr` is a `Header` instance, not `str`, so `encode` is not `str.encode`, it's a
                        # different method.
                        # Then we do `decode` because `sendmail` crashes on certain invalid byte sequences
                        # (like b'"TrueNAS SCALE<user@domaincom>" <user@domain.com>')
                        # Same byte sequences passed as strings work fine and result in invalid from address being
                        # sanitized properly.
                        from_addr if isinstance(from_addr, str) else from_addr.encode().decode(),
                        to,
                        msg.as_string(),
                    )
        except NetworkActivityDisabled:
            self.logger.warning('Sending email denied')
            return False
        except Exception as e:
            # We are only interested in ValueError, not subclasses.
            if e.__class__ is ValueError:
                raise CallError(str(e))
            if isinstance(e, smtplib.SMTPAuthenticationError):
                raise CallError(
                    f'Authentication error ({e.smtp_code}): {e.smtp_error}', errno.EPERM
                )
            # NAS-137666: Email addresses are considered Personally Identifiable
            # Information (PII) under GDPR. Prevent displaying them in logs.
            if isinstance(e, smtplib.SMTPSenderRefused):
                e.sender = '[sender redacted]'
                e.args = (e.smtp_code, e.smtp_error, e.sender)
            elif isinstance(e, smtplib.SMTPRecipientsRefused):
                e.recipients = '[recipient info redacted]'
                e.args = (e.recipients,)

            self.logger.warning('Failed to send email', exc_info=e)
            if message['queue']:
                with self.mail_queue as mq:
                    mq.append(msg)
            raise CallError(f'Failed to send email: {e}')
        return True

    @contextlib.contextmanager
    def _get_smtp_server(self, config, timeout=300, local_hostname=None):
        self.middleware.call_sync('network.general.will_perform_activity', 'mail')

        if local_hostname is None:
            local_hostname = self.middleware.call_sync('system.hostname')

        if not config['outgoingserver'] or not config['port']:
            raise ValueError('You must provide an outgoing mailserver and mail server port when sending mail')

        if config['security'] == 'SSL':
            factory = smtplib.SMTP_SSL
        else:
            factory = smtplib.SMTP

        with factory(
            config['outgoingserver'],
            config['port'],
            timeout=timeout,
            local_hostname=local_hostname,
        ) as server:
            if config['security'] == 'TLS':
                server.starttls()

            if config['oauth'] and config['oauth']['provider'] == 'outlook':
                self.middleware.call_sync('mail.outlook_xoauth2', server, config)
            elif config['smtp']:
                server.login(config['user'], config['pass'])

            yield server

    @periodic(600, run_on_start=False)
    @private
    def send_mail_queue(self):
        with self.mail_queue as mq:
            for queue in list(mq.queue):
                try:
                    config = self.middleware.call_sync('mail.config')
                    if config['oauth'] and config['oauth']['provider'] == 'gmail':
                        self.middleware.call_sync('mail.gmail_send', queue.message, config)
                    else:
                        with self._get_smtp_server(config) as server:
                            # Update `From` address from currently used config because if the SMTP user changes,
                            # already queued messages might not be sent due to (553, b'Relaying disallowed as xxx')
                            # error
                            queue.message['From'] = self._from_addr(config)
                            server.sendmail(queue.message['From'].encode(),
                                            queue.message['To'].split(', '),
                                            queue.message.as_string())
                except NetworkActivityDisabled:
                    # no reason to queue up email since network activity was
                    # explicitly denied by end-user
                    mq.queue.remove(queue)
                except Exception:
                    self.logger.debug('Sending message from queue failed', exc_info=True)
                    queue.attempts += 1
                    if queue.attempts >= mq.MAX_ATTEMPTS:
                        mq.queue.remove(queue)
                else:
                    mq.queue.remove(queue)

    def _from_addr(self, config):
        if config['fromname']:
            pair = (config['fromname'], config['fromemail'])
            try:
                return formataddr(pair, 'ascii')
            except UnicodeEncodeError:
                return formataddr(pair, 'utf-8')
        else:
            try:
                config['fromemail'].encode('ascii')
            except UnicodeEncodeError:
                from_addr = Header(config['fromemail'], 'utf-8')
            else:
                from_addr = Header(config['fromemail'], 'ascii')

            return from_addr

    @private
    async def local_administrators_emails(self):
        return list(set(user["email"] for user in await self.middleware.call("user.query", [
            ["roles", "rin", "FULL_ADMIN"],
            ["local", "=", True],
            ["email", "!=", None]
        ])))

    @api_method(
        MailLocalAdministratorEmailArgs,
        MailLocalAdministratorEmailResult,
        roles=["ALERT_READ"],
    )
    async def local_administrator_email(self):
        emails = await self.local_administrators_emails()
        if emails:
            return sorted(emails)[0]
        else:
            return None


async def setup(middleware):
    await middleware.call('network.general.register_activity', 'mail', 'Mail')
