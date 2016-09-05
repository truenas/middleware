#!/usr/bin/env python3
import argparse
import os
import unittest

from base import CRUDTestCase, SingleItemTestCase
from client import Client
from paramiko import AutoAddPolicy
from paramiko.client import SSHClient


def filter_tests(tests, shared=None, only=None, skip=None, skip_class=None):
    if isinstance(tests, unittest.TestCase):
        # Stupid way to pass params to test case instead of env var
        suite = unittest.TestSuite()
        tests.shared = shared
        suite.addTest(tests)
        return suite
    rv = []
    for test in tests._tests:
        # Skip abstract test cases
        if test.__class__ in (CRUDTestCase, SingleItemTestCase):
            continue
        if isinstance(test, unittest.TestCase):
            if only and test.__module__ not in only:
                continue
            if skip and test.__module__ in skip:
                continue
            if skip_class and test.__class__.__name__ in skip_class:
                continue
        rv.append(filter_tests(test, shared=shared, only=only, skip=skip, skip_class=skip_class))
    tests._tests = rv
    return tests


class Shared(object):

    def __init__(self, args):
        self.args = args
        self.client = Client(
            'http://{0}{1}'.format(self.args.address, ':{0}'.format(self.args.port) if self.args.port else ''),
            '/api/v2.0/',
            username=self.args.username,
            password=self.args.password,
        )
        self.ssh_client = SSHClient()
        self.ssh_client.set_missing_host_key_policy(AutoAddPolicy())
        self.ssh_client.connect(args.address, port=args.sshport, username=args.username, password=args.password)


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--address', required=True)
    parser.add_argument('-u', '--username')
    parser.add_argument('-p', '--password')
    parser.add_argument('-P', '--port')
    parser.add_argument('-sp', '--sshport', default=22, type=int)
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-s', '--skip', action='append')
    parser.add_argument('-sc', '--skip-class', action='append')
    parser.add_argument('-t', '--test', action='append')
    args = parser.parse_args()

    loader = unittest.TestLoader()
    tests = loader.discover('resources')
    tests = filter_tests(tests, shared=Shared(args), only=args.test, skip=args.skip, skip_class=args.skip_class)

    testRunner = unittest.runner.TextTestRunner(verbosity=2 if args.verbose else 1)
    testRunner.run(tests)

if __name__ == '__main__':
    main()
