from middlewared.schema import Str, accepts
from middlewared.service import CallError, Service

import errno
import json
import requests
import simplejson

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
