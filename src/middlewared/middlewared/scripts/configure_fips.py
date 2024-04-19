#!/usr/bin/python3
import os
import shutil
import sqlite3
import subprocess
import typing

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


def get_active_be() -> typing.Optional[str]:
    cp = subprocess.run(['zfs', 'get', '-o', 'name', '-H', 'name', '/'], capture_output=True, check=False)
    if cp.returncode or not (active_be := cp.stdout.decode().strip()):
        return None

    return active_be


def set_readonly(readonly: bool) -> None:
    active_be = get_active_be()
    if not active_be or subprocess.run(
        ['zfs', 'get', '-H', 'truenas:developer', active_be], capture_output=True, check=False
    ).stdout.decode().split()[-2] == 'on':
        # We do not want to do anything here if developer mode is enabled or if we are not able to find active be
        # because we are in chroot env in that case
        return

    subprocess.run(
        ['zfs', 'set', f'readonly={"on" if readonly else "off"}', os.path.join(active_be, 'usr')],
        capture_output=True, check=False
    )


def main() -> None:
    validate_system_state()
    try:
        security_settings = query_config_table('system_security')
    except (sqlite3.OperationalError, IndexError):
        # This is for the case when users are upgrading and in that case table will not exist
        # so we should always disable fips as a default because users might not be able to ssh
        # into the system
        security_settings = {'enable_fips': False}

    set_readonly(False)
    configure_fips(security_settings['enable_fips'])
    set_readonly(True)


if __name__ == '__main__':
    main()
