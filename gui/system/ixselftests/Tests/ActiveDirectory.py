#!/usr/bin/env python
# Copyright (c) 2011, 2015-2017 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

import os
import sys
from ldap import LDAPError

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

from django.db.models.loading import cache
cache.get_apps()

from freenasUI.common.system import (
    activedirectory_enabled,
)

from freenasUI.common.freenasldap import (
    FreeNAS_ActiveDirectory,
    FLAGS_DBINIT
)

from system.ixselftests import TestObject


def List():
    return ["ActiveDirectory"]


class ActiveDirectory(TestObject):
    def __init__(self, handler=None):
        super(self.__class__, self).__init__(handler)
        self._name = "ActiveDirectory"
        self.freenas_ad = None

    def Enabled(self):
        return activedirectory_enabled()

    def Test(self):
        try:
            self.freenas_ad = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)
            if self.freenas_ad.connected():
                return self._handler.Pass("ActiveDirectory")
            else:
                return self._handler.Fail("ActiveDirectory", "Unable to login to the Domain Controller.")
        except LDAPError as e:
            # LDAPError is dumb, it returns a list with one element for goodness knows what reason
            e = e[0]
            error = []
            desc = e.get('desc')
            info = e.get('info')
            if desc:
                error.append(desc)
            if info:
                error.append(info)

            if error:
                error = ', '.join(error)
            else:
                error = str(e)

            return self._handler.Fail("ActiveDirectory", error)
        except Exception as e:
            return self._handler.Fail("ActiveDirectory", str(e))

