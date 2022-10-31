#!/usr/bin/env python3

import os
import pytest
import sys

apifolder = os.getcwd()
sys.path.append(apifolder)

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.utils import call


PAYLOAD = (
    ('s3.config', 's3.update', ['bindport', 'console_bindport'], {'access_key': '12345678', 'secret_key': '123456789'}),
    ('ftp.config', 'ftp.update', ['port'], {}),
    ('webdav.config', 'webdav.update', ['tcpport', 'tcpportssl'], {}),
    ('rsyncd.config', 'rsyncd.update', ['port'], {}),
)


@pytest.mark.parametrize('config_method,method,keys,payload', PAYLOAD)
def test_port_delegate_validation_with_invalid_ports(config_method, method, keys, payload):
    in_use_ports = []
    namespace = config_method.rsplit('.', 1)[0]
    for entry in call('port.get_in_use'):
        in_use_ports.extend(filter(lambda i: i > 1024 and entry['namespace'] != namespace, entry['ports']))

    assert in_use_ports != [], 'No in use ports retrieved'

    for index, key in enumerate(keys):
        payload[key] = in_use_ports[index] if len(in_use_ports) > index else in_use_ports[0]

    with pytest.raises(ValidationErrors) as ve:
        call(method, payload)

    assert any('The port is being used by' in error.errmsg for error in ve.value.errors) is True, ve


@pytest.mark.parametrize('config_method,method,keys,payload', PAYLOAD)
def test_port_delegate_validation_with_valid_ports(config_method, method, keys, payload):
    in_use_ports = []
    for entry in call('port.get_in_use'):
        in_use_ports.extend(entry['ports'])

    assert in_use_ports != [], 'No in use ports retrieved'

    validation_error = None
    old_config = call(config_method)
    to_restore_config = {}
    used_ports = []
    for key in keys:
        port = next(i for i in range(20000, 60000) if i not in in_use_ports and i not in used_ports)
        payload[key] = port
        used_ports.append(port)
        to_restore_config[key] = old_config[key]

    try:
        call(method, payload)
    except ValidationErrors as ve:
        validation_error = ve
    else:
        call(method, to_restore_config)

    assert validation_error is None, f'No validation exception expected: {validation_error}'
