# Copyright 2014 iXsystems, Inc.
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
import logging
import json
import os
from uuid import uuid4

from django.utils.translation import ugettext as _

log = logging.getLogger('system.utils')


class CheckUpdateHandler(object):

    def __init__(self):
        self.output = ''

    def call(self, op, newpkg, oldpkg):
        if op == 'upgrade':
            self.output += '%s: %s-%s -> %s-%s\n' % (
                _('Upgrade'),
                oldpkg.Name(),
                oldpkg.Version(),
                newpkg.Name(),
                newpkg.Version(),
            )


class UpdateHandler(object):

    DUMPFILE = '/tmp/.upgradeprogress'

    def __init__(self, uuid=None):
        if uuid:
            try:
                self.load()
                if self.uuid != uuid:
                    raise
            except:
                raise ValueError("UUID not found")
        else:
            self.uuid = uuid4().hex
            self.details = ''
            self.indeterminate = False
            self.pid = None
            self.progress = 0
            self.step = 1
            self.finished = False
        self._pkgname = ''
        self._baseprogress = 0

    def get_handler(self, index, pkg, pkgList):
        self.step = 1
        self._pkgname = '%s-%s' % (
            pkg.Name(),
            pkg.Version(),
        )
        self.details = '%s %s' % (
            _('Downloading'),
            self._pkgname,
        )
        stepprogress = int((1.0 / float(len(pkgList))) * 100)
        self._baseprogress = index * stepprogress
        self.progress = (index - 1) * stepprogress
        self.dump()
        return self.get_file_handler

    def get_file_handler(self, method, filename, progress=None):
        if progress is not None and self._pkgname:
            self.progress = (progress * self._baseprogress) / 100
            self.details = '%s (%d%%)' % (self._pkgname, progress)
        self.dump()

    def install_handler(self, index, name, packages):
        raise
        self.indeterminate = data['indeterminate']
        self.step = 2
        self.indeterminate = False
        total = len(packages)
        self.progress = int((float(index) / float(total)) * 100.0)
        self.details = '%s %s (%d/%d)' % (
            _('Installing'),
            name,
            index,
            total,
        )

    def dump(self):
        with open(self.DUMPFILE, 'wb') as f:
            data = {
                'finished': self.finished,
                'indeterminate': self.indeterminate,
                'pid': self.pid,
                'percent': self.progress,
                'step': self.step,
                'uuid': self.uuid,
            }
            if self.details:
                data['details'] = self.details
            f.write(json.dumps(data))

    def load(self):
        if not os.path.exists(self.DUMPFILE):
            return None
        with open(self.DUMPFILE, 'rb') as f:
            data = json.loads(f.read())
        self.details = data.get('details', '')
        self.finished = data['finished']
        self.indeterminate = data['indeterminate']
        self.progress = data['percent']
        self.pid = data['pid']
        self.step = data['step']
        self.uuid = data['uuid']
        return data

    def exit(self):
        if os.path.exists(self.DUMPFILE):
            os.unlink(self.DUMPFILE)

