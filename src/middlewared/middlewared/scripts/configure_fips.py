#!/usr/bin/python3
import os
import re

from middlewared.utils.db import query_config_table


FIPS_MODULE_FILE = '/usr/lib/ssl/fipsmodule.cnf'
OPENSSL_CONFIG_FILE = '/etc/ssl/openssl.cnf'
OPENSSL_FIPS_FILE = '/etc/ssl/openssl_fips.cnf'


def validate_system_state():
    for path in (FIPS_MODULE_FILE, OPENSSL_CONFIG_FILE, OPENSSL_FIPS_FILE):
        if not os.path.exists(path):
            raise Exception(f'{path!r} does not exist')


def main():
    validate_system_state()
    security_settings = query_config_table('system_security')


if __name__ == '__main__':
    main()
