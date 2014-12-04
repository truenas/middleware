#+
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
######################################################################

import os
import unittest
from threading import Event, Lock
from dispatcher.rpc import RpcException
from dispatcher.client import Client, ClientError


class BaseTestCase(unittest.TestCase):
    class TaskState(object):
        def __init__(self):
            self.tid = None
            self.state = None
            self.message = None
            self.result = None
            self.ended = Event()

    def __init__(self, methodName):
        super(BaseTestCase, self).__init__(methodName)
        self.tasks = {}
        self.tasks_lock = Lock()
        self.conn = None
        self.task_timeout = 20

    def setUp(self):
        try:
            self.conn = Client()
            self.conn.event_callback = self.on_event
            self.conn.connect(os.getenv('TESTHOST', '127.0.0.1'))
            self.conn.login_service('tests')
            self.conn.subscribe_events('*')
        except:
            raise

    def tearDown(self):
        self.conn.disconnect()

    def submitTask(self, name, *args):
        self.tasks_lock.acquire()
        try:
            tid = self.conn.call_sync('task.submit', name, args)
        except RpcException:
            self.tasks_lock.release()
            raise

        self.tasks[tid] = self.TaskState()
        self.tasks[tid].tid = tid
        self.tasks_lock.release()
        return tid

    def assertTaskCompletion(self, tid):
        t = self.tasks[tid]
        if not t.ended.wait(self.task_timeout):
            self.fail('Task {0} timed out'.format(tid))

        self.assertEqual(t.state, 'FINISHED', msg=t.message)

    def assertTaskFailure(self, tid):
        t = self.tasks[tid]
        if not t.ended.wait(self.task_timeout):
            self.fail('Task {0} timed out'.format(tid))

        self.assertNotEqual(t.state, 'FINISHED', msg=t.message)

    def assertSeenEvent(self, name, func=None):
        pass

    def getTaskResult(self, tid):
        t = self.tasks[tid]
        return t.result

    def on_event(self, name, args):
        self.tasks_lock.acquire()

        if name == 'task.updated':
            t = self.tasks[args['id']]
            t.state = args['state']
            if t.state in ('FINISHED', 'FAILED'):
                t.result = args['result'] if 'result' in args else None
                t.ended.set()

        elif name == 'task.progress':
            t = self.tasks[args['id']]
            t.message = args['message']

        self.tasks_lock.release()