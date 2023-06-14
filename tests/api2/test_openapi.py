import pytest

from functions import GET
from auto_config import dev_test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


@pytest.mark.parametrize('protocol,force_ssl', [('http', False), ('https', True)])
def test_protocol_reported_correctly(protocol, force_ssl):
    response = GET('', force_ssl=force_ssl)
    server_urls = response.json()['servers']
    for url_dict in filter(lambda d: 'url' in d, server_urls):
        assert url_dict['url'].startswith(protocol) is True, url_dict
