#!/usr/bin/env python
import argparse

from concurrent.futures import ThreadPoolExecutor
from middlewared.client import Client


def setup(password):

    def sed_setup(client, disk_name, password):
        rv = client.call('disk.sed_initial_setup', disk_name, password)
        if rv == 'SUCCESS':
            print(f'{disk_name}\t\t[\033[92mOK\x1B[0m]')
        elif rv == 'SETUP_FAILED':
            print(f'{disk_name}\t\t[\033[91mSETUP FAILED\x1B[0m]')
        elif rv in ('ACCESS_GRANTED', 'NO_SED'):
            pass
        return disk_name, rv

    with Client() as c:
        disks = c.call('disk.query')
        action = False
        no_sed = False
        granted = False
        with ThreadPoolExecutor(max_workers=12) as e:
            for disk_name, rv in e.map(lambda x: sed_setup(*x), [[c, disk['name'], password] for disk in disks]):
                if rv == 'NO_SED':
                    no_sed = True
                if rv in ('SUCCESS', 'SETUP_FAILED'):
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
        if c.call('disk.sed_unlock_all') is False:
            print('SED disks failed to unlocked')
        else:
            print('All SED disks unlocked')


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='sub-command help', dest='action')

    parser_setup = subparsers.add_parser('setup', help='Setup new SED disks')
    parser_setup.add_argument('password', help='Password to use on new disks')

    subparsers.add_parser('unlock', help='Unlock SED disks')

    args = parser.parse_args()
    if args.action == 'setup':
        setup(args.password)
    elif args.action == 'unlock':
        unlock()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
