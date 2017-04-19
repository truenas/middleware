#!/usr/local/bin/python3
from middlewared.client import Client
from middlewared.service import Service, CRUDService, ConfigService

import argparse
import imp
import inspect
import json
import logging
import os
import sys
import traceback


class FakeMiddleware(object):
    """
    Implements same API from real middleware
    so jobs can run over.
    """

    def __init__(self, client):
        self.client = client
        self.logger = logging.getLogger('job_process')
        self.__services = {}
        self.__plugins_load()

    def __plugins_load(self):
        plugins_dir = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'plugins',
        )
        self.logger.debug('Loading plugins from {0}'.format(plugins_dir))
        if not os.path.exists(plugins_dir):
            raise ValueError('plugins dir not found')

        for f in os.listdir(plugins_dir):
            if not f.endswith('.py'):
                continue
            f = f[:-3]
            fp, pathname, description = imp.find_module(f, [plugins_dir])
            try:
                mod = imp.load_module(f, fp, pathname, description)
            finally:
                if fp:
                    fp.close()

            for attr in dir(mod):
                attr = getattr(mod, attr)
                if not inspect.isclass(attr):
                    continue
                if attr in (Service, CRUDService, ConfigService):
                    continue
                if issubclass(attr, Service):
                    self.add_service(attr(self))

    def add_service(self, service):
        self.__services[service._config.namespace] = service

    def _call_job(self, job_id):
        job = self.client.call('core.get_jobs', [('id', '=', job_id)], {'get': True})
        service, method = job['method'].rsplit('.', 1)
        methodobj = getattr(self.__services[service], method)
        job_options = getattr(methodobj, '_job', None)
        if job_options:
            params = list(job['arguments'])
            params.insert(0, FakeJob(job['id'], self.client))
            return methodobj(*params)
        else:
            raise NotImplementedError("Only jobs are allowed")

    def call(self, method, *params):
        """
        Calls a method using middleware client
        """
        return self.client.call(method, *params)


class FakeJob(object):

    def __init__(self, id, client):
        self.id = id
        self.client = client
        self.progress = {
            'percent': None,
            'description': None,
            'extra': None,
        }

    def set_progress(self, percent, description=None, extra=None):
        self.progress['percent'] = percent
        if description:
            self.progress['description'] = description
        if extra:
            self.progress['extra'] = extra
        self.client.call('core.job_update', self.id, {'progress': self.progress})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('job', type=int)
    args = parser.parse_args()
    with Client() as c:
        middleware = FakeMiddleware(c)
        return middleware._call_job(args.job)

if __name__ == '__main__':
    try:
        print(json.dumps(main()))
    except Exception as e:
        print(json.dumps({
            'exception': ''.join(traceback.format_exception(*sys.exc_info())),
            'error': str(e),
        }))
        sys.exit(2)
