import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.utils.client import client
from truenas_api_client import ClientException


MSG_TOO_BIG_ERR = 'Max message length is 64 kB'


def test_large_message_default():
    LARGE_PAYLOAD_1 = 'x' * 65537

    with pytest.raises(ClientException) as ce:
        with client() as c:
            c.call('filesystem.mkdir', LARGE_PAYLOAD_1)

    assert MSG_TOO_BIG_ERR in ce.value.error


def test_large_message_extended():
    LARGE_PAYLOAD_1 = 'x' * 65537
    LARGE_PAYLOAD_2 = 'x' * 2097153

    # NOTE: we are intentionally passing an invalid payload here
    # to avoid writing unnecessary file to VM FS. If it fails with
    # ValidationErrors instead of a ClientException then we know that
    # the call passed through the size check.
    with pytest.raises(ValidationErrors):
        with client() as c:
            c.call('filesystem.file_receive', LARGE_PAYLOAD_1)

    with pytest.raises(ClientException) as ce:
        with client() as c:
            c.call('filesystem.file_receive', LARGE_PAYLOAD_2)

    assert MSG_TOO_BIG_ERR in ce.value.error


def test_large_message_unauthenticated():
    LARGE_PAYLOAD = 'x' * 10000

    with pytest.raises(ClientException) as ce:
        with client(auth=None) as c:
            c.call('filesystem.file_receive', LARGE_PAYLOAD)

    assert 'Anonymous connection max message length' in ce.value.error
