#!/usr/bin/env python3

import sys
import os
import pytest
apifolder = os.getcwd()
sys.path.append(apifolder)

from functions import SSH_TEST, make_ws_request
from auto_config import ha, user, password
from pytest_dependency import depends
from auto_config import dev_test

if ha and "virtual_ip" in os.environ:
    ip = os.environ["virtual_ip"]
else:
    from auto_config import ip

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


@pytest.mark.dependency(name="CORSSL_INSTALLED")
def test_01_check_corssl_installed(request):
    rv = SSH_TEST('openssl version', user, password, ip)
    assert rv['output'].strip().lower().startswith('corssl'), rv['output']


@pytest.mark.dependency(name="SSL_CERT_PATH_IS_SET")
def test_02_check_base_ssl_module_cert_path(request):
    depends(request, ["CORSSL_INSTALLED"])
    default_dir = '/usr/lib/ssl/certs'
    cmd = "python3 -c 'import ssl; print(ssl.get_default_verify_paths().capath)'"
    rv = SSH_TEST(cmd, user, password, ip)
    assert rv['output'].strip() == default_dir, rv['output']


def test_03_check_connection_to_update_server(request):
    depends(request, ["SSL_CERT_PATH_IS_SET"])
    rv = make_ws_request(ip, {'msg': 'method', 'method': 'update.get_scale_trains_data', 'params': []})
    assert isinstance(rv['result'], dict), rv['result']
    assert 'trains' in rv['result'], rv['result']
    assert 'trains_redirection' in rv['result'], rv['result']
