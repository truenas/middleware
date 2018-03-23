import errno
import json
import os
import requests
import shutil
import simplejson
import socket
import subprocess
import sys
import time

from middlewared.pipe import Pipes
from middlewared.schema import Bool, Dict, Int, Str, accepts
from middlewared.service import CallError, Service, job
from middlewared.utils import Popen

# FIXME: Remove when we can generate debug and move license to middleware
if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

import django
from django.apps import apps
if not apps.ready:
    django.setup()

from freenasUI.system.utils import debug_get_settings, debug_generate
from freenasUI.support.utils import get_license

ADDRESS = 'support-proxy.ixsystems.com'


class SupportService(Service):

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
        Str('title', required=True),
        Str('body', required=True),
        Str('category', required=True),
        Bool('attach_debug', default=False),
        Str('username', private=True),
        Str('password', private=True),
        Str('type', enum=['BUG', 'FEATURE']),
        Str('criticality'),
        Str('environment'),
        Str('phone'),
        Str('name'),
        Str('email'),
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
            license = get_license()[0]
            if license:
                data['company'] = license.customer_name
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
            # FIXME: generate debug from middleware
            mntpt, direc, dump = await self.middleware.run_in_thread(debug_get_settings)

            job.set_progress(60, 'Generating debug file')
            await self.middleware.run_in_thread(debug_generate)

            not_freenas = not (await self.middleware.call('system.is_freenas'))
            if not_freenas:
                not_freenas &= await self.middleware.call('notifier.failover_licensed')
            if not_freenas:
                debug_file = f'{direc}/debug.tar'
                debug_name = 'debug-{}.tar'.format(time.strftime('%Y%m%d%H%M%S'))
            else:
                debug_file = dump
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
            tjob = await self.middleware.call('support.attach_ticket', t, pipes=Pipes(input=self.middleware.pipe()))

            with open(debug_file, 'rb') as f:
                await self.middleware.run_in_io_thread(shutil.copyfileobj, f, tjob.pipes.input.w)
                await self.middleware.run_in_io_thread(tjob.pipes.input.w.close)

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
        Str('filename', required=True),
        Str('username'),
        Str('password'),
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
            r = await self.middleware.run_in_io_thread(lambda: requests.post(
                f'https://{ADDRESS}/{sw_name}/api/v1.0/ticket/attachment',
                data=data,
                timeout=10,
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
