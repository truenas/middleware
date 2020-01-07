import errno
import json
import requests
import simplejson
import socket
import subprocess
import time

from middlewared.pipe import Pipes
from middlewared.schema import Bool, Dict, Int, List, Str, accepts
from middlewared.service import CallError, ConfigService, job, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import Popen
from middlewared.validators import Email

ADDRESS = 'support-proxy.ixsystems.com'


class SupportModel(sa.Model):
    __tablename__ = 'system_support'

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean(), nullable=True, default=True)
    name = sa.Column(sa.String(200))
    title = sa.Column(sa.String(200))
    email = sa.Column(sa.String(200))
    phone = sa.Column(sa.String(200))
    secondary_name = sa.Column(sa.String(200))
    secondary_title = sa.Column(sa.String(200))
    secondary_email = sa.Column(sa.String(200))
    secondary_phone = sa.Column(sa.String(200))


class SupportService(ConfigService):

    class Config:
        datastore = 'system.support'

    @accepts(Dict(
        'support_update',
        Bool('enabled', null=True),
        Str('name'),
        Str('title'),
        Str('email'),
        Str('phone'),
        Str('secondary_name'),
        Str('secondary_title'),
        Str('secondary_email'),
        Str('secondary_phone'),
        update=True
    ))
    async def do_update(self, data):
        """
        Update Proactive Support settings.
        """

        config_data = await self.config()
        config_data.update(data)

        verrors = ValidationErrors()
        if config_data['enabled']:
            for key in ['name', 'title', 'email', 'phone']:
                for prefix in ['', 'secondary_']:
                    field = prefix + key
                    if not config_data[field]:
                        verrors.add(f'support_update.{field}', 'This field is required')
        if verrors:
            raise verrors

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            config_data['id'],
            config_data,
        )

        return await self.config()

    @accepts()
    async def is_available(self):
        """
        Returns whether Proactive Support is available for this product type and current license.
        """

        if await self.middleware.call('system.is_freenas'):
            return False

        license = (await self.middleware.call('system.info'))['license']
        if license is None:
            return False

        return license['contract_type'] in ['SILVER', 'GOLD']

    @accepts()
    async def is_available_and_enabled(self):
        """
        Returns whether Proactive Support is available and enabled.
        """

        return await self.is_available() and (await self.config())['enabled']

    @accepts()
    async def fields(self):
        """
        Returns list of pairs of field names and field titles for Proactive Support.
        """

        return (
            ("name", "Contact Name"),
            ("title", "Contact Title"),
            ("email", "Contact E-mail"),
            ("phone", "Contact Phone"),
            ("secondary_name", "Secondary Contact Name"),
            ("secondary_title", "Secondary Contact Title"),
            ("secondary_email", "Secondary Contact E-mail"),
            ("secondary_phone", "Secondary Contact Phone"),
        )

    @accepts(
        Str('username'),
        Str('password'),
    )
    def fetch_categories(self, username, password):
        """
        Fetch all the categories available for `username` using `password`.
        Returns a dict with the category name as a key and id as value.
        """

        sw_name = 'freenas' if self.middleware.call_sync('system.is_freenas') else 'truenas'
        try:
            r = requests.post(
                f'https://{ADDRESS}/{sw_name}/api/v1.0/categories',
                data=json.dumps({
                    'user': username,
                    'password': password,
                }),
                headers={'Content-Type': 'application/json'},
                timeout=10,
            )
            data = r.json()
        except simplejson.JSONDecodeError:
            self.logger.debug(f'Failed to decode ticket attachment response: {r.text}')
            raise CallError('Invalid proxy server response', errno.EBADMSG)
        except requests.ConnectionError as e:
            raise CallError(f'Connection error {e}', errno.EBADF)
        except requests.Timeout:
            raise CallError('Connection time out', errno.ETIMEDOUT)

        if 'error' in data:
            raise CallError(data['message'], errno.EINVAL)

        return data

    @accepts(Dict(
        'new_ticket',
        Str('title', required=True, max_length=None),
        Str('body', required=True, max_length=None),
        Str('category', required=True),
        Bool('attach_debug', default=False),
        Str('username', private=True),
        Str('password', private=True),
        Str('type', enum=['BUG', 'FEATURE']),
        Str('criticality'),
        Str('environment', max_length=None),
        Str('phone'),
        Str('name'),
        Str('email', validators=[Email()]),
        List('cc', items=[Str('email', validators=[Email()])])
    ))
    @job()
    async def new_ticket(self, job, data):
        """
        Creates a new ticket for support.
        This is done using the support proxy API.
        For FreeNAS it will be created on Redmine and for TrueNAS on SupportSuite.

        For FreeNAS `criticality`, `environment`, `phone`, `name` and `email` attributes are not required.
        For TrueNAS `username`, `password` and `type` attributes are not required.
        """

        job.set_progress(1, 'Gathering data')

        sw_name = 'freenas' if await self.middleware.call('system.is_freenas') else 'truenas'

        if sw_name == 'freenas':
            required_attrs = ('type', 'username', 'password')
        else:
            required_attrs = ('phone', 'name', 'email', 'criticality', 'environment')
            data['serial'] = (await (await Popen(['/usr/local/sbin/dmidecode', '-s', 'system-serial-number'], stdout=subprocess.PIPE)).communicate())[0].decode().split('\n')[0].upper()
            license = (await self.middleware.call('system.info'))['license']
            if license:
                data['company'] = license['customer_name']
            else:
                data['company'] = 'Unknown'

        for i in required_attrs:
            if i not in data:
                raise CallError(f'{i} is required', errno.EINVAL)

        data['version'] = (await self.middleware.call('system.version')).split('-', 1)[-1]
        if 'username' in data:
            data['user'] = data.pop('username')
        debug = data.pop('attach_debug')

        type_ = data.get('type')
        if type_:
            data['type'] = type_.lower()

        job.set_progress(20, 'Submitting ticket')

        try:
            r = await self.middleware.run_in_thread(lambda: requests.post(
                f'https://{ADDRESS}/{sw_name}/api/v1.0/ticket',
                data=json.dumps(data),
                headers={'Content-Type': 'application/json'},
                timeout=10,
            ))
            result = r.json()
        except simplejson.JSONDecodeError:
            self.logger.debug(f'Failed to decode ticket attachment response: {r.text}')
            raise CallError('Invalid proxy server response', errno.EBADMSG)
        except requests.ConnectionError as e:
            raise CallError(f'Connection error {e}', errno.EBADF)
        except requests.Timeout:
            raise CallError('Connection time out', errno.ETIMEDOUT)

        if r.status_code != 200:
            self.logger.debug(f'Support Ticket failed ({r.status_code}): {r.text}', r.status_code, r.text)
            raise CallError('Ticket creation failed, try again later.', errno.EINVAL)

        if result['error']:
            raise CallError(result['message'], errno.EINVAL)

        ticket = result.get('ticketnum')
        url = result.get('message')
        if not ticket:
            raise CallError('New ticket number was not informed', errno.EINVAL)
        job.set_progress(50, f'Ticket created: {ticket}', extra={'ticket': ticket})

        if debug:
            job.set_progress(60, 'Generating debug file')

            debug_job = await self.middleware.call(
                'system.debug', pipes=Pipes(output=self.middleware.pipe()),
            )

            not_freenas = not (await self.middleware.call('system.is_freenas'))
            if not_freenas:
                not_freenas &= await self.middleware.call('failover.licensed')
            if not_freenas:
                debug_name = 'debug-{}.tar'.format(time.strftime('%Y%m%d%H%M%S'))
            else:
                debug_name = 'debug-{}-{}.txz'.format(
                    socket.gethostname().split('.')[0],
                    time.strftime('%Y%m%d%H%M%S'),
                )

            job.set_progress(80, 'Attaching debug file')

            t = {
                'ticket': ticket,
                'filename': debug_name,
            }
            if 'user' in data:
                t['username'] = data['user']
            if 'password' in data:
                t['password'] = data['password']
            tjob = await self.middleware.call(
                'support.attach_ticket', t, pipes=Pipes(input=self.middleware.pipe()),
            )

            def copy():
                try:
                    rbytes = 0
                    while True:
                        r = debug_job.pipes.output.r.read(1048576)
                        if r == b'':
                            break
                        rbytes += len(r)
                        if rbytes > 20971520:
                            raise CallError('Debug too large to attach', errno.EFBIG)
                        tjob.pipes.input.w.write(r)
                finally:
                    tjob.pipes.input.w.close()

            await self.middleware.run_in_thread(copy)

            await debug_job.wait()
            await tjob.wait()
        else:
            job.set_progress(100)

        return {
            'ticket': ticket,
            'url': url,
        }

    @accepts(Dict(
        'attach_ticket',
        Int('ticket', required=True),
        Str('filename', required=True, max_length=None),
        Str('username', private=True),
        Str('password', private=True),
    ))
    @job(pipes=["input"])
    async def attach_ticket(self, job, data):
        """
        Method to attach a file to a existing ticket.
        """

        sw_name = 'freenas' if await self.middleware.call('system.is_freenas') else 'truenas'

        if 'username' in data:
            data['user'] = data.pop('username')
        data['ticketnum'] = data.pop('ticket')
        filename = data.pop('filename')

        try:
            r = await self.middleware.run_in_thread(lambda: requests.post(
                f'https://{ADDRESS}/{sw_name}/api/v1.0/ticket/attachment',
                data=data,
                timeout=300,
                files={'file': (filename, job.pipes.input.r)},
            ))
            data = r.json()
        except simplejson.JSONDecodeError:
            self.logger.debug(f'Failed to decode ticket attachment response: {r.text}')
            raise CallError('Invalid proxy server response', errno.EBADMSG)
        except requests.ConnectionError as e:
            raise CallError(f'Connection error {e}', errno.EBADF)
        except requests.Timeout:
            raise CallError('Connection time out', errno.ETIMEDOUT)

        if data['error']:
            raise CallError(data['message'], errno.EINVAL)
