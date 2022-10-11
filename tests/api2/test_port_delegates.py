#!/usr/bin/env python3

import os
import random
import sys

apifolder = os.getcwd()
sys.path.append(apifolder)
from middlewared.test.integration.utils import call, ValidationErrors


PAYLOAD = (
    ('s3.config', 's3.update', ['bindport', 'console_bindport'], {'access_key': '12345678', 'secret_key': '123456789'}),
    ('ftp.config', 'ftp.update', ['port'], {}),
    ('webdav.config', 'webdav.update', ['tcpport', 'tcpportssl'], {}),
    ('rsyncd.config', 'rsyncd.update', ['port'], {}),
)


def test_port_delegate_validation_with_invalid_ports():
    in_use_ports = []
    for entry in call('port.get_in_use'):
        in_use_ports.extend(filter(lambda i: i > 1024, entry['ports']))

    for config_method, method, keys, payload in PAYLOAD:
        validation_error = None
        for key in keys:
            payload[key] = in_use_ports[random.randint(0, len(in_use_ports) - 1)]
        try:
            call(method, payload, client_args={'py_exceptions': False})
        except ValidationErrors as ve:
            validation_error = ve

        assert validation_error is not None, 'Port validation exception expected'
        assert any(
            'The port is being used by' in error.errmsg for error in validation_error.errors
        ) is True, validation_error


def test_port_delegate_validation_with_valid_ports():
    in_use_ports = []
    for entry in call('port.get_in_use'):
        in_use_ports.extend(entry['ports'])

    for config_method, method, keys, payload in PAYLOAD:
        validation_error = None
        old_config = call(config_method)
        to_restore_config = {}
        for key in keys:
            payload[key] = next(i for i in range(random.randint(1025, 50000), 60000) if i not in in_use_ports)
            to_restore_config[key] = old_config[key]
        try:
            call(method, payload, client_args={'py_exceptions': False})
        except ValidationErrors as ve:
            validation_error = ve
        else:
            call(method, to_restore_config)

        assert validation_error is None, f'No validation exception expected: {validation_error}'
