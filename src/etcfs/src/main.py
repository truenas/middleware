__author__ = 'jceel'

import os
import sys
import signal
import logging
import argparse
import json
import datastore
import renderers
from fuse import FUSE
from fs import EtcFS


TEMPLATE_RENDERERS = {
    '.mako': renderers.MakoTemplateRenderer,
    '.shell': renderers.ShellTemplateRenderer,
}

class Main:
    def __init__(self):
        self.logger = logging.getLogger('EtcFS')
        self.config = None
        self.datastore = None
        self.plugin_dirs = []
        self.renderers = {}
        self.managed_files = {}

    def init_datastore(self):
        try:
            self.datastore = datastore.get_datastore(self.config['datastore']['driver'], self.config['datastore']['dsn'])
        except datastore.DatastoreException, err:
            self.logger.error('Cannot initialize datastore: %s', str(err))
            sys.exit(1)

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

        self.plugin_dirs = self.config['etcfs']['plugin-dirs']

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

    def generate_file(self, template_path):
        print 'generate file %s' % template_path
        name, ext = os.path.splitext(template_path)
        if not ext in self.renderers.keys():
            print 'no renderer for %s' % ext
            raise OSError("Cant find renderer")

        renderer = self.renderers[ext]
        print renderer.render_template(template_path)
        return renderer.render_template(template_path)

    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('-o', metavar='OVERLAY', help='Overlay directory')
        parser.add_argument('-c', metavar='CONFIG', help='Middleware config file')
        parser.add_argument('mountpoint', metavar='MOUNTPOINT', help='Mount point')
        args = parser.parse_args()
        logging.basicConfig(level=logging.DEBUG)
        self.parse_config(args.c)
        self.scan_plugins()
        self.init_datastore()
        self.init_renderers()

        FUSE(EtcFS(self, args.o), args.mountpoint, foreground=False)

if __name__ == '__main__':
    m = Main()
    m.main()

