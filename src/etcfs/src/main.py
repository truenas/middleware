__author__ = 'jceel'

import sys
import signal
import daemon
import logging
import argparse
import json
from datastore import get_datastore, DatastoreException
from fuse import FUSE
from fs import EtcFS

class TemplateFunctions:
    def disclaimer(self, comment_style='#'):
        return "{} WARNING: This file was auto-generated".format(comment_style)


class Main:
    def __init__(self):
        self.logger = logging.getLogger('EtcFS')
        self.config = None
        self.datastore = None
        self.managed_files = {}

    def init_datastore(self):
        try:
            self.datastore = datastore.get(self.config['datastore']['driver'], self.config['datastore'])

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

    def get_template_context(self):
        return {
            "disclaimer": TemplateFunctions.disclaimer,
            "config": None,
        }

    def scan_plugins(self):
        pass

    def generate_file(self, template_path):
        pass

    def main():
        parser = argparse.ArgumentParser()
        parser.add_argument('-o', metavar='OVERLAY', help='Overlay directory')
        parser.add_argument('-c', metavar='CONFIG', help='Middleware config file')
        parser.add_argument('mountpoint', metavar='MOUNTPOINT', help='Mount point')
        args = parser.parse_args()

        with daemon.DaemonContext():
            FUSE(EtcFS(args.o), args.mountpoint, foreground=True)

if __name__ == '__main__':
    main()

