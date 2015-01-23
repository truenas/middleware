#!/usr/local/bin/python2.7
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
#####################################################################


import sys
import argparse
import json
import logging
import datetime
import setproctitle
import numpy as np
import pandas as pd
from gevent import monkey
from dispatcher.client import Client, ClientType, thread_type
from dispatcher.rpc import RpcService, RpcException
from datastore import DatastoreException, get_datastore


DEFAULT_CONFIGFILE = '/usr/local/etc/middleware.conf'
monkey.patch_all()
thread_type = ClientType.GEVENT


class DataSource(object):
    def __init__(self, context, config):
        self.context = context
        self.config = config
        self.series = None
        self.ptr = 0

    def submit(self, timestamp, value):
        self.series

    def persist(self):
        pass


class InputService(RpcService):
    def __init__(self, context):
        super(InputService, self).__init__()
        self.context = context

    def submit(self, name, timestamp, value):
        self.context.logger.debug('Submitted value: name={0}, timestamp={1}, value={2}'.format(name, timestamp, value))


class OutputService(RpcService):
    def __init__(self, context):
        super(OutputService, self).__init__()
        self.context = context

    def enable(self, event):
        pass

    def disable(self, event):
        pass

    def get_datapoints(self):
        pass

    def query(self):
        pass


class Context(object):
    def __init__(self):
        self.connection = None
        self.datastore = None
        self.data_sources = {}


class Main(object):
    def __init__(self):
        self.client = None
        self.config = None
        self.logger = logging.getLogger('statd')

    def parse_config(self, filename):
        try:
            f = open(filename, 'r')
            self.config = json.load(f)
            f.close()
        except IOError, err:
            self.logger.error('Cannot read config file: %s', err.message)
            sys.exit(1)
        except ValueError:
            self.logger.error('Config file has unreadable format (not valid JSON)')
            sys.exit(1)

    def init_datastore(self):
        try:
            self.datastore = get_datastore(self.config['datastore']['driver'], self.config['datastore']['dsn'])
        except DatastoreException, err:
            self.logger.error('Cannot initialize datastore: %s', str(err))
            sys.exit(1)

    def init_dispatcher(self):
        self.client = Client()
        self.client.connect('127.0.0.1')
        self.client.login_service('statd')
        self.client.enable_server()

    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', metavar='CONFIG', default=DEFAULT_CONFIGFILE, help='Middleware config file')
        args = parser.parse_args()
        logging.basicConfig(level=logging.DEBUG)
        setproctitle.setproctitle('statd')
        self.parse_config(args.c)
        self.init_datastore()
        self.init_dispatcher()
        self.client.enable_server()
        self.client.register_service('statd.input', InputService(self))
        self.client.register_service('statd.output', OutputService(self))
        self.logger.info('Started')
        self.client.wait_forever()


if __name__ == '__main__':
    m = Main()
    m.main()
