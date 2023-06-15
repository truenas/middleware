#!/usr/bin/python3
import os
import re
import sqlite3
import subprocess

from middlewared.utils.db import query_config_table


FIPS_MODULE_FILE = '/usr/lib/ssl/fipsmodule.cnf'
OPENSSL_CONFIG_FILE = '/etc/ssl/openssl.cnf'
OPENSSL_FIPS_FILE = '/etc/ssl/openssl_fips.cnf'
RE_INCLUDE_FIPS = re.compile(fr'\s*\.include {re.escape(OPENSSL_FIPS_FILE)}\s*$')


def validate_system_state() -> None:
    for path in (FIPS_MODULE_FILE, OPENSSL_CONFIG_FILE, OPENSSL_FIPS_FILE):
        if not os.path.exists(path):
            raise Exception(f'{path!r} does not exist')


def modify_openssl_config(enable_fips: bool) -> None:
    with open(OPENSSL_CONFIG_FILE, 'r') as f:
        config = f.read()

    if enable_fips and not RE_INCLUDE_FIPS.search(config):
        config += f'\n.include {OPENSSL_FIPS_FILE}\n'
    elif not enable_fips and RE_INCLUDE_FIPS.search(config):
        config = RE_INCLUDE_FIPS.sub('\n', config)

    with open(OPENSSL_CONFIG_FILE, 'w') as f:
        f.write(config)


def configure_fips(enable_fips: bool) -> None:
    if enable_fips:
        subprocess.check_call([
            'openssl', 'fipsinstall', '-out', FIPS_MODULE_FILE,
            '-module', '/usr/lib/x86_64-linux-gnu/ossl-modules/fips.so',
        ], timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    modify_openssl_config(enable_fips)


def main() -> None:
    validate_system_state()
    try:
        security_settings = query_config_table('system_security')
    except sqlite3.OperationalError:
        # This is for the case when users are upgrading and in that case table will not exist
        # so we should always enable fips as a good default then
        security_settings = {'enable_fips': True}

    configure_fips(security_settings['enable_fips'])


if __name__ == '__main__':
    main()
