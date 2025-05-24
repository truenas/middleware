#!/usr/bin/python3
import logging
import os
import shutil
import sqlite3
import subprocess
import sys

from middlewared.utils.db import query_config_table


FIPS_MODULE_FILE = '/usr/lib/ssl/fipsmodule.cnf'
OPENSSL_CONFIG_FILE = '/etc/ssl/openssl.cnf'
BASE_OPENSSL_CONFIG_FILE = '/conf/base/etc/ssl/openssl.cnf'
OPENSSL_FIPS_FILE = '/etc/ssl/openssl_fips.cnf'


def validate_system_state() -> None:
    for path in (FIPS_MODULE_FILE, OPENSSL_CONFIG_FILE, OPENSSL_FIPS_FILE, BASE_OPENSSL_CONFIG_FILE):
        if not os.path.exists(path):
            raise Exception(f'{path!r} does not exist')


def modify_openssl_config(enable_fips: bool) -> None:
    shutil.copyfile(BASE_OPENSSL_CONFIG_FILE, OPENSSL_CONFIG_FILE)

    if enable_fips:
        with open(OPENSSL_CONFIG_FILE, 'a') as f:
            f.write(f'\n.include {OPENSSL_FIPS_FILE}\n')


def configure_fips(enable_fips: bool) -> None:
    if enable_fips:
        subprocess.check_call([
            'openssl', 'fipsinstall', '-out', FIPS_MODULE_FILE,
            '-module', '/usr/lib/x86_64-linux-gnu/ossl-modules/fips.so',
        ], timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    modify_openssl_config(enable_fips)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")

    if len(sys.argv) == 2:
        database_path = sys.argv[1]
    else:
        database_path = None

    validate_system_state()
    try:
        security_settings = query_config_table('system_security', database_path)
    except (sqlite3.OperationalError, IndexError) as e:
        # This is for the case when users are upgrading and in that case table will not exist,
        # so we should always disable fips as a default because users might not be able to ssh
        # into the system
        logging.warning("Error querying system_security table: %r. Assuming that FIPS is disabled", e)
        security_settings = {'enable_fips': False}

    configure_fips(security_settings['enable_fips'])


if __name__ == '__main__':
    main()
