from middlewared.schema import Bool, Dict, Str, accepts
from middlewared.service import CallError, Service, job
from middlewared.utils import Popen

import errno
import json
import requests
import simplejson
import subprocess

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
                'https://%s/%s/api/v1.0/categories' % (ADDRESS, sw_name),
                data=json.dumps({
                    'user': username,
                    'password': password,
                }),
                headers={'Content-Type': 'application/json'},
                timeout=10,
            )
            data = r.json()
        except simplejson.JSONDecodeError as e:
            self.logger.debug("Failed to decode ticket attachment response: %s", r.text)
            raise CallError('Invalid proxy server response', errno.EBADMSG)
        except requests.ConnectionError as e:
            raise CallError(f'Connection error {e}', errno.EBADF)
        except requests.Timeout as e:
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
        Str('username'),
        Str('password'),
        Str('type'),
        Str('criticality'),
        Str('environment'),
        Str('phone'),
        Str('name'),
        Str('email'),
    ))
    @job()
    async def new_ticket(self, job, data):

        sw_name = 'freenas' if await self.middleware.call('system.is_freenas') else 'truenas'

        if sw_name == 'freenas':
            required_attrs = ('type', 'username', 'password')
        else:
            required_attrs = ('phone', 'name', 'email', 'criticality', 'environment')
            data['serial'] = (await (await Popen(['/usr/local/sbin/dmidecode', '-s', 'system-serial-number'], stdout=subprocess.PIPE)).communicate())[0].decode().split('\n')[0].upper()
            data['company'] = 'Unknown'

        for i in required_attrs:
            if i not in data:
                raise CallError(f'{i} is required', errno.EINVAL)

        data['version'] = (await self.middleware.call('system.version')).split('-', 1)[-1]
        data['debug'] = data.pop('attach_debug')

        try:
            r = await self.middleware.threaded(lambda: requests.post(
                'https://%s/%s/apii/v1.0/ticket' % (ADDRESS, sw_name),
                data=json.dumps(data),
                headers={'Content-Type': 'application/json'},
                timeout=10,
            ))
            data = r.json()
        except simplejson.JSONDecodeError as e:
            self.logger.debug(f'Failed to decode ticket attachment response: {r.text}')
            raise CallError('Invalid proxy server response', errno.EBADMSG)
        except requests.ConnectionError as e:
            raise CallError(f'Connection error {e}', errno.EBADF)
        except requests.Timeout as e:
            raise CallError('Connection time out', errno.ETIMEDOUT)

        if r.status_code != 200:
            self.logger.debug(f'Support Ticket failed ({r.status_code}): {r.text}', r.status_code, r.text)
            raise CallError('Ticket creation failed, try again later.', errno.EINVAL)

        if data['error']:
            raise CallError(data['message'], errno.EINVAL)

        return data.get('ticketnum')
