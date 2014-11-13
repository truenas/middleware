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

import os
import sys
import signal
import logging
import argparse
import json
import errno
import datastore
import renderers
from dispatcher.client import Client
from dispatcher.rpc import RpcService, RpcException


TEMPLATE_RENDERERS = {
    '.mako': renderers.MakoTemplateRenderer,
    '.shell': renderers.ShellTemplateRenderer,
}


class ManagementService(RpcService):
    def __init__(self, ctx):
        self.context = ctx

    def rescan_plugins(self):
        self.context.scan_plugins()

    def die(self):
        pass


class FileGenerationService(RpcService):
    def __init__(self, ctx):
        self.context = ctx
        self.datastore = ctx.datastore

    def generate_all(self):
        for f in self.get_managed_files():
            self.generate_file(f)

    def generate_file(self, filename):
        if filename not in self.context.managed_files.keys():
            return

        text = self.context.generate_file(filename)
        fd = open(os.path.join(self.context.root, filename), 'w')
        fd.write(text)
        fd.close()

        self.context.emit_event('etcd.file_generated', {
            'filename': filename
        })

    def generate_group(self, name):
        group = self.datastore.get_one('etcd_groups', ('name', '=', name))
        if not group:
            raise RpcException(errno.ENOENT, 'Group {0} not found'.format(name))

        for f in group['files']:
            self.generate_file(f)

    def get_managed_files(self):
        return self.context.managed_files


class Main:
    def __init__(self):
        self.logger = logging.getLogger('etcd')
        self.root = None
        self.config = None
        self.datastore = None
        self.client = None
        self.plugin_dirs = []
        self.renderers = {}
        self.managed_files = {}

    def init_datastore(self):
        try:
            self.datastore = datastore.get_datastore(self.config['datastore']['driver'], self.config['datastore']['dsn'])
        except datastore.DatastoreException, err:
            self.logger.error('Cannot initialize datastore: %s', str(err))
            sys.exit(1)

    def init_dispatcher(self):
        self.client = Client()
        self.client.connect('127.0.0.1')
        self.client.login_service('etcd')
        self.client.enable_server()
        self.client.register_service('etcd.generation', FileGenerationService(self))
        self.client.register_service('etcd.management', ManagementService(self))

    def init_renderers(self):
        for name, impl in TEMPLATE_RENDERERS.items():
            self.renderers[name] = impl(self)

    def parse_config(self, filename):
        try:
            f = open(filename, 'r')
            self.config = json.load(f)
            f.close()
        except IOError, err:
            self.logger.error('Cannot read config file: %s', err.message)
            sys.exit(1)
        except ValueError, err:
            self.logger.error('Config file has unreadable format (not valid JSON)')
            sys.exit(1)

        self.plugin_dirs = self.config['etcd']['plugin-dirs']

    def scan_plugins(self):
        for i in self.plugin_dirs:
            self.scan_plugin_dir(i)

    def scan_plugin_dir(self, dir):
        self.logger.debug('Scanning plugin directory %s', dir)
        for root, dirs, files in os.walk(dir):
            for name in files:
                abspath = os.path.join(root, name)
                path = os.path.relpath(abspath, dir)
                name, ext = os.path.splitext(path)

                if name in self.managed_files.keys():
                    continue

                if ext in TEMPLATE_RENDERERS.keys():
                    self.managed_files[name] = abspath
                    self.logger.info('Adding managed file %s [%s]', name, ext)

    def generate_file(self, file_path):
        if file_path not in self.managed_files.keys():
            raise RpcException(errno.ENOENT, 'No such file')

        template_path = self.managed_files[file_path]
        name, ext = os.path.splitext(template_path)
        if not ext in self.renderers.keys():
            print 'no renderer for %s' % ext
            raise OSError("Cant find renderer")

        renderer = self.renderers[ext]
        return renderer.render_template(template_path)

    def emit_event(self, name, params):
        pass

    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', metavar='CONFIG', help='Middleware config file')
        parser.add_argument('-f', action='store_true', default=False, help='Run in foreground')
        parser.add_argument('mountpoint', metavar='MOUNTPOINT', default='/etc', help='/etc mount point')
        args = parser.parse_args()
        logging.basicConfig(level=logging.DEBUG)
        self.root = args.mountpoint
        self.parse_config(args.c)
        self.scan_plugins()
        self.init_datastore()
        self.init_dispatcher()
        self.init_renderers()
        self.client.wait_forever()

if __name__ == '__main__':
    m = Main()
    m.main()

