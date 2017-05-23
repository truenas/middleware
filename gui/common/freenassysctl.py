# Copyright 2017 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################
import sysctl

#
# Magical freenas sysctl wrapper class
#
# This allows usage such as this:
#
# f = freenas_sysctl()
# print(f.directoryservice.activedirectory.timeout.start)
# f.directoryservice.activedirectory.timeout.start = 42
# print(f.directoryservice.activedirectory.timeout.start)
#
# Output of this will be:
# 0
# 42
#
class freenas_sysctl(object):
    def __init__(self, *args, **kwargs):
        for oid in sysctl.filter('freenas'):
            oid_save = oid

            parts = oid.name.split('.') 
            fixed_parts = parts[1:len(parts)]
            oid = '.'.join(fixed_parts)

            base = type(self)
            klass = base

            parts = oid.split('.')
            for i in range(0, len(parts)):
                if i == 0 and not getattr(self, parts[i], False):
                    klass = type(parts[i], (base,), { })
                    setattr(self, parts[i], klass)

                elif i == 0 and getattr(self, parts[i], False):
                    klass = getattr(self, parts[i])
                    base = klass.__bases__[0]

                elif i == len(parts) - 1:
                    setattr(klass, parts[i], oid_save.value)

                elif getattr(klass, parts[i], False):
                    tmp = getattr(klass, parts[i])
                    base = klass
                    klass = tmp

                else:
                    tmp = type(parts[i], (klass,), { })
                    setattr(klass, parts[i], tmp)
                    base = klass
                    klass = tmp
