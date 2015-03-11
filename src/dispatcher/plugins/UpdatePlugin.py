# +
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

import errno
import os
import sys
from task import (Provider, Task, ProgressTask, TaskException,
                  VerifyException, query)
from dispatcher.rpc import (RpcException, description, accepts,
                            returns)
from lib.system import system

sys.path.append('/usr/local/lib')
from freenasOS import Configuration
from freenasOS.Update import (
    ActivateClone,
    CheckForUpdates,
    DeleteClone,
)


# The handler(s) below is/are taken from the freenas 9.3 code
# specifically from gui/system/utils.py
@description("A handler for the CheckUpdate call")
class CheckUpdateHandler(object):

    def __init__(self):
        self.changes = []

    def call(self, op, newpkg, oldpkg):
        self.changes.append({
            'operation': op,
            'old': oldpkg,
            'new': newpkg,
        })

    @property
    def output(self):
        output = ''
        for c in self.changes:
            if c['operation'] == 'upgrade':
                output += '%s: %s-%s -> %s-%s\n' % (
                    'Upgrade',
                    c['old'].Name(),
                    c['old'].Version(),
                    c['new'].Name(),
                    c['new'].Version(),
                )
        return output


@description("Provides information of Available Updates and Trains")
class UpdateProvider(Provider):

    def get_current_train(self):
        conf = Configuration.Configuration()
        conf.LoadTrainsConfig()
        return conf.LoadTrainsConfig()

    def check_now_for_updates(self):
        handler = CheckUpdateHandler()
        update = CheckForUpdates(
            handler=handler.call,
            train=self.get_current_train(),
        )
        # Fix get_current_train() with datastore object of user specified train
        if update:
            return handler.output()


# Fix this when the fn10 freenas-pkg tools is updated by sef
@description("Runs a ghetto `freenas-update update`")
class UpdateTask(Task):
    def describe(self):
        return "FreeNAS Update"

    def verify(self):
        return ['root']

    def run(self):
        try:
            self.dispatcher.dispatch_event('update.changed', {
                'operation': 'started',
            })
            system('/usr/local/bin/freenas-update', 'update')
            self.run_subtask('system.reboot')
        except Exception as e:
            raise TaskException(errno.EAGAIN,
                                'Update Process Failed! Reason: %s' % e)


def _init(dispatcher):
    # Register providers
    dispatcher.register_provider("update", UpdateProvider)

    # Register task handlers
    dispatcher.register_task_handler("update.update", UpdateTask)
