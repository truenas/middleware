"""
sysctl module functional tests

Copyright (c) 2012 Garrett Cooper, All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:
1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED.  IN NO EVENT SHALL Garrett Cooper OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
SUCH DAMAGE.
"""

import errno
import os
import platform
import pwd
import random
import socket
import subprocess
import sys
import unittest


try:
    unittest.TestCase.assertRaises
    unittest.skipIf
    unittest.skipUnless
except AttributeError:
    sys.exit('your version of unittest is too old')


import sysctl




def sysctl_set(name, value):
    command = ['sysctl', '%s=%s' % (name, value, ),]
    if SYSCTL_SET_OPT:
        command.insert(1, SYSCTL_SET_OPT)
    subprocess.check_output(command)


def sysctl_n(name):
    out = subprocess.check_output(['sysctl', '-n', name])
    if out:
        out = out[:-1]
    return out


# Legacy BSD sysctl(8) requires -w to set values. This is the status quo for
# Linux, NetBSD, and OSX, as well as others I'm sure.
p = subprocess.Popen(['sysctl', '-h'],
                     stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT)
matches = filter(lambda x: '=' in x and '-w' in x,
                 p.communicate()[0].splitlines())
if matches:
    SYSCTL_SET_OPT = '-w'
else:
    SYSCTL_SET_OPT = ''


COREFILE_PATTERN = sysctl_n('kern.corefile')
HOSTNAME = socket.gethostname()
MY_ID = os.getuid()
OS_NAME = platform.system()


def corefile_restore():
    """Try to restore the corefile pattern if it was changed"""

    name = 'kern.corefile'
    if COREFILE_PATTERN != sysctl_n(name):
        sysctl_set(name, COREFILE_PATTERN)


class TestSysctl(unittest.TestCase):
    """sysctl.sysctl testcases"""


    def test_positive_sysctl_get_integer(self):
        """Try to get kern.ostype"""

        name = 'kern.ostype'
        mib = sysctl.sysctlnametomib(name)
        assert sysctl.sysctl(mib) == OS_NAME


    def test_positive_sysctl_get_string(self):
        """Try to get kern.corefile"""

        name = 'kern.corefile'

        mib = sysctl.sysctlnametomib(name)

        corefile_pattern = sysctl.sysctl(mib)
        assert COREFILE_PATTERN == corefile_pattern, \
            "'%s' != '%s'" % (COREFILE_PATTERN, corefile_pattern, )


    def test_positive_sysctl_get_old_False(self):
        """Ensure that getting kern.corefile when old=False returns None"""

        name = 'kern.corefile'

        mib = sysctl.sysctlnametomib(name)

        corefile_pattern = sysctl.sysctl(mib, old=False)
        assert corefile_pattern is None, \
            "'%s' != '%s'" % (COREFILE_PATTERN, corefile_pattern, )


    @unittest.skipUnless(MY_ID == 0, 'Not root')
    def test_positive_sysctl_set(self):
        """Try to set kern.corefile as root"""

        name = 'kern.corefile'

        mib = sysctl.sysctlnametomib(name)
        corefile_pattern = sysctl_n('kern.corefile')
        if not corefile_pattern.startswith('/'):
            corefile_pattern = os.path.join(os.getcwd(), corefile_pattern)
        if corefile_pattern.endswith('/'):
            corefile_pattern = corefile_pattern[:-1]
        else:
            corefile_pattern = corefile_pattern + '/'

        try:
            sysctl.sysctl(mib, new=corefile_pattern)
            corefile_pattern_new = sysctl.sysctl(mib)
            assert corefile_pattern == corefile_pattern_new, \
                "'%s' != '%s'" % (corefile_pattern, corefile_pattern_new, )
        finally:
            corefile_restore()


    def test_negative_sysctl_get1(self):
        """Try to get [-1, -1]

        This should fail with ENOENT
        """

        try:
            sysctl.sysctl([-1, -1])
        except OSError as ose:
            assert ose.errno == errno.ENOENT


    def test_negative_sysctl_get2(self):
        """Try to get []

        This should fail with ValueError.

        The sysctl requirement states that this should return EINVAL, but it
        was simpler to catch the problem in the python code.
        """

        self.assertRaises(ValueError, sysctl.sysctl, [])


    def test_negative_sysctl_get3(self):
        """Try to get [0] * 1024

        This should fail with EINVAL
        """

        try:
            sysctl.sysctl([0] * 1024)
        except OSError as ose:
            assert ose.errno == errno.EINVAL


    @unittest.skipIf(MY_ID == 0, 'Is root')
    def test_negative_sysctl_set1(self):
        """Try to set kern.hostname as non-root

        This should fail with EPERM.
        """

        name = 'kern.hostname'
        mib = sysctl.sysctlnametomib(name)
        try:
            sysctl.sysctl(mib, new=HOSTNAME + '.mydomain')
        except OSError as ose:
            assert ose.errno == errno.EPERM
        assert HOSTNAME == socket.gethostname(), \
            'hostname has been modified since the start of the test'


    def test_negative_sysctl_set2(self):
        """Try to set kern.ostype to MyOS

        This should raise OSError with EPERM
        """

        name = 'kern.ostype'
        mib = sysctl.sysctlnametomib(name)
        try:
            sysctl.sysctl(mib, new='MyOS')
        except OSError as ose:
            assert ose.errno == errno.EPERM
        assert sysctl.sysctl(mib) == OS_NAME, \
            'platform has been modified since the start of the test'


class TestSysctlByName(unittest.TestCase):
    """sysctl.sysctlbyname testcases"""


    def test_positive_sysctl_get_integer(self):
        """Try to get kern.ostype"""

        name = 'kern.ostype'
        assert sysctl.sysctlbyname(name) == OS_NAME


    def test_positive_sysctl_get_string(self):
        """Try to get kern.corefile"""

        name = 'kern.corefile'

        corefile_pattern = sysctl.sysctlbyname(name)
        assert COREFILE_PATTERN == corefile_pattern, \
            "'%s' != '%s'" % (COREFILE_PATTERN, corefile_pattern, )


    def test_positive_sysctl_get_old_False(self):
        """Ensure that getting kern.corefile when old=False returns None"""

        name = 'kern.corefile'

        corefile_pattern = sysctl.sysctlbyname(name, old=False)
        assert corefile_pattern is None


    @unittest.skipUnless(MY_ID == 0, 'Not root')
    def test_positive_sysctl_set(self):
        """Try to set kern.corefile as root"""

        name = 'kern.corefile'

        corefile_pattern = sysctl_n('kern.corefile')
        if not corefile_pattern.startswith('/'):
            corefile_pattern = os.path.join(os.getcwd(), corefile_pattern)
        if corefile_pattern.endswith('/'):
            corefile_pattern = corefile_pattern[:-1]
        else:
            corefile_pattern = corefile_pattern + '/'

        try:
            sysctl.sysctlbyname(name, new=corefile_pattern)
            corefile_pattern_new = sysctl.sysctlbyname(name)
            assert corefile_pattern == corefile_pattern_new, \
                "'%s' != '%s'" % (corefile_pattern, corefile_pattern_new, )
        finally:
            corefile_restore()


    def test_negative_sysctl_get1(self):
        """Try to get 'i.do.not.exist.

        This should fail with ENOENT
        """

        try:
            sysctl.sysctlbyname('i.do.not.exist')
        except OSError as ose:
            assert ose.errno == errno.ENOENT


    def test_negative_sysctl_get2(self):
        """Try to get []

        This should fail with ValueError.
        
        The sysctl requirement states that this should return EINVAL, but it
        was simpler to catch the problem in the python code.
        """

        self.assertRaises(ValueError, sysctl.sysctl, '')


    @unittest.skipIf(MY_ID == 0, 'Is root')
    def test_negative_sysctl_set1(self):
        """Try to set kern.hostname as non-root

        This should fail with EPERM.
        """

        name = 'kern.hostname'
        try:
            sysctl.sysctlbyname(name, new=HOSTNAME + '.mydomain')
        except OSError as ose:
            assert ose.errno == errno.EPERM
        assert HOSTNAME == socket.gethostname(), \
            '"%s" != "%s"' % (HOSTNAME, socket.gethostname(), )


    def test_negative_sysctl_set2(self):
        """Try to set kern.ostype to MyOS

        This should raise OSError with EPERM
        """

        name = 'kern.ostype'
        try:
            sysctl.sysctlbyname(name, new='MyOS')
        except OSError as ose:
            assert ose.errno == errno.EPERM
        assert sysctl.sysctlbyname(name) == OS_NAME, \
            'platform has been modified since the start of the test'


class TestSysctlNameToMib(unittest.TestCase):
    """sysctl.sysctlnametomib testcases"""


    def test_positive_validate_subset_no_clamp(self):
        """Validate that kern.ostype lookup matches for the first element"""

        mib1 = sysctl.sysctlnametomib('kern')
        mib2 = sysctl.sysctlnametomib('kern.ostype')
        assert len(mib1) == 1
        assert len(mib2) == 2
        assert mib1[0] == mib2[0]


    @unittest.skip('Fails asserts on OSX & returns ENOMEM on FreeBSD')
    def test_positive_validate_subset_clamp(self):
        """Validate that kern.ostype matches kern if clamped to 1 element"""

        mib1 = sysctl.sysctlnametomib('kern')
        mib2 = sysctl.sysctlnametomib('kern.ostype', size=1)
        assert len(mib1) == 1
        assert len(mib2) == 1
        assert mib1[0] == mib2[0]


    def test_negative_sysctl_get1(self):
        """Try to get 'i.do.not.exist'

        This should raise OSError with ENOENT
        """

        try:
            sysctl.sysctlnametomib('i.do.not.exist')
        except OSError as ose:
            assert ose.errno == errno.ENOENT


    def test_negative_sysctl_get2(self):
        """Try to get ''

        This should fail with ValueError.

        The sysctl requirement states that this should return EINVAL, but it
        was simpler to catch the problem in the python code.
        """

        self.assertRaises(ValueError, sysctl.sysctlnametomib, '')


    def test_negative_sysctl_get3(self):
        """Try to get 0 elements of kern.ostype

        This should fail with ValueError.
        """

        self.assertRaises(ValueError, sysctl.sysctlnametomib,
                                      'kern.ostype', size=0)


