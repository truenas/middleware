import errno
import os

from middlewared.client import ClientException


def test_support_fetch_categories(conn):

    username = os.environ.get('SUPPORT_USERNAME')
    password = os.environ.get('SUPPORT_PASSWORD')

    if username and password:
        req = conn.rest.post('support/fetch_categories', data=[username, password])
        assert req.status_code == 200, req.text
        assert isinstance(req.json(), dict)
    else:
        try:
            req = conn.ws.call('support.fetch_categories', 'foo', 'bar')
        except ClientException as e:
            assert e.errno == errno.EINVAL
        assert True, 'Should have raised an exception with EINVAL'
