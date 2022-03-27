import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET


@pytest.mark.parametrize('protocol,force_ssl', [('http', False), ('https', True)])
def test_protocol_reported_correctly(protocol, force_ssl):
    response = GET('', force_ssl=force_ssl)
    server_urls = response.json()['servers']
    for url_dict in filter(lambda d: 'url' in d, server_urls):
        assert url_dict['url'].startswith(protocol) is True, url_dict
