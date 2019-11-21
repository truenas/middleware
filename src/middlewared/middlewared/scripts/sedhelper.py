#!/usr/bin/env python
import argparse
import errno

from concurrent.futures import ThreadPoolExecutor
from middlewared.client import Client, ClientException


def setup(password, disk=None):

    def sed_setup(client, disk_name, password):
        rv = client.call('disk.sed_initial_setup', disk_name, password)
        if rv == 'SUCCESS':
            print(f'{disk_name}\t\t[\033[92mOK\x1B[0m]')
        elif rv == 'SETUP_FAILED':
            print(f'{disk_name}\t\t[\033[91mSETUP FAILED\x1B[0m]')
        elif rv == 'LOCKING_DISABLED':
            print(f'{disk_name}\t\t[\033[91mLOCKING DISABLED\x1B[0m]')
        elif rv in ('ACCESS_GRANTED', 'NO_SED'):
            pass
        return disk_name, rv

    with Client() as c:

        disk_filter = []
        if disk:
            disk_filter.append(('name', '=', disk))

        disks = c.call('disk.query_passwords', disk_filter)
        boot_disks = c.call('boot.get_disks')
        disks = list(filter(lambda d: d['name'] not in boot_disks, disks))

        if not disks:
            print(f'Disk {disk} not found')
            return

        global_sed_password = c.call('system.advanced.sed_global_password')
        if global_sed_password != password and not (disk and disks[0]['passwd'] == password):
            print('Given password does not match saved one')
            return

        action = False
        no_sed = False
        granted = False
        with ThreadPoolExecutor(max_workers=12) as e:
            for disk_name, rv in e.map(lambda disk: sed_setup(c, disk['name'], password), disks):
                if rv == 'NO_SED':
                    no_sed = True
                if rv in ('SUCCESS', 'SETUP_FAILED', 'LOCKING_DISABLED'):
                    action = True
                if rv == 'ACCESS_GRANTED':
                    granted = True

        if not action:
            if no_sed and not granted:
                print('No SED disks were found in the system')
            else:
                print('No new SED disks detected')


def unlock():
    with Client() as c:
        try:
            c.call('disk.sed_unlock_all')
        except ClientException as e:
            if e.errno == errno.EACCES:
                print('SED disks failed to unlocked')
            else:
                raise
        else:
            print('All SED disks unlocked')


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='sub-command help', dest='action')

    parser_setup = subparsers.add_parser('setup', help='Setup new SED disks')
    parser_setup.add_argument('--disk', help='Perform action only on specified disk')
    parser_setup.add_argument('password', help='Password to use on new disks')

    subparsers.add_parser('unlock', help='Unlock SED disks')

    args = parser.parse_args()
    if args.action == 'setup':
        setup(args.password, disk=args.disk)
    elif args.action == 'unlock':
        unlock()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
