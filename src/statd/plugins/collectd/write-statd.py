#+
# Copyright 2015 iXsystems, Inc.
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


import collectd
import threading
from dispatcher.client import Client


class Context(object):
    def __init__(self):
        self.client = Client()
        self.hostname = '127.0.0.1'

    def start(self):
        self.client.connect(self.hostname)
        self.client.login_service('collectd')

    def config(self, c):
        for child in c.children:
            if child.key == 'Host':
                self.hostname = child.values[0]

    def write(self, v):
        value_name = [v.plugin]

        if v.plugin_instance:
            value_name.append(v.plugin_instance)

        value_name.append(v.type)

        if v.type_instance:
            value_name.append(v.type_instance)

        for idx, i in enumerate(v.values):
            self.client.call_sync('statd.input.submit', '.'.join(value_name), int(v.time), i)

    def init(self):
        self.start()
        collectd.register_write(self.write)


context = Context()
collectd.register_config(context.config)
collectd.register_init(context.init)