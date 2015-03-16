#!/usr/local/bin/python2.7
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


import os
import sys
import time
import errno
import argparse
import json
import logging
import setproctitle
import numpy
import dateutil.parser
import dateutil.tz
import tables
import signal
import pandas as pd
from datetime import datetime, timedelta
import gevent
import gevent.monkey
import gevent.socket
from gevent.server import StreamServer
from dispatcher.client import Client, ClientType, thread_type
from dispatcher.rpc import RpcService, RpcException
from datastore import DatastoreException, get_datastore
from ringbuffer import MemoryRingBuffer, PersistentRingBuffer


DEFAULT_CONFIGFILE = '/usr/local/etc/middleware.conf'
DEFAULT_DBFILE = 'stats.hdf'
gevent.monkey.patch_all()
thread_type = ClientType.GEVENT


def to_timedelta(time_val):
    num = int(time_val[:-1])

    if time_val.endswith('s'):
        return timedelta(seconds=num)

    elif time_val.endswith('m'):
        return timedelta(minutes=num)

    elif time_val.endswith('h'):
        return timedelta(hours=num)

    elif time_val.endswith('d'):
        return timedelta(days=num)

    elif time_val.endswith('y'):
        return timedelta(days=(365 * num))


def round_timestamp(timestamp, frequency):
    return int(frequency * round(float(timestamp)/frequency))


def parse_datetime(s):
    return dateutil.parser.parse(s)


class DataSourceBucket(object):
    def __init__(self, index, obj):
        self.index = index
        self.interval = to_timedelta(obj['interval'])
        self.retention = to_timedelta(obj['retention'])
        self.consolidation = obj.get('consolidation')

    @property
    def covered_start(self):
        return datetime.now(dateutil.tz.tzlocal()) - self.retention

    @property
    def covered_end(self):
        return datetime.now(dateutil.tz.tzlocal())

    @property
    def intervals_count(self):
        return int(self.retention.total_seconds() / self.interval.total_seconds())


class DataSourceConfig(object):
    def __init__(self, datastore, name):
        self.logger = logging.getLogger('DataSourceConfig:{0}'.format(name))
        name = name if datastore.exists('statd.sources', ('id', '=', name)) else 'default'
        self.ds_obj = datastore.get_by_id('statd.sources', name)
        self.ds_schema = datastore.get_by_id('statd.schemas', self.ds_obj['schema'])
        self.buckets = [DataSourceBucket(idx, i) for idx, i in enumerate(self.ds_schema['buckets'])]
        self.primary_bucket = self.buckets[0]

        for i in self.buckets:
            self.logger.debug('Created bucket with interval {0} and retention {1}'.format(i.interval, i.retention))

        self.logger.debug('Created using schema {0}, {1} buckets'.format(self.ds_obj['schema'], len(self.buckets)))

    @property
    def primary_interval(self):
        return self.primary_bucket.interval

    def get_covered_buckets(self, start, end):
        for i in self.buckets:
            # Bucked should be at least partially covered
            if (start <= i.covered_start <= end) or (i.covered_start <= start <= i.covered_end):
                yield i


class DataSource(object):
    def __init__(self, context, name, config):
        self.context = context
        self.name = name
        self.config = config
        self.logger = logging.getLogger('DataSource:{0}'.format(self.name))
        self.bucket_buffers = self.create_buckets()
        self.primary_buffer = self.bucket_buffers[0]
        self.primary_interval = self.config.buckets[0].interval
        self.last_value = 0

        self.logger.debug('Created')

    def create_buckets(self):
        # Primary bucket should be hold in memory
        buckets = [MemoryRingBuffer(self.config.buckets[0].intervals_count)]

        # And others saved to HDF5 file
        for idx, b in enumerate(self.config.buckets[1:]):
            table = self.context.request_table('{0}#b{1}'.format(self.name, idx))
            buckets.append(PersistentRingBuffer(table, b.intervals_count))

        self.logger.debug('Created {0} buckets'.format(len(buckets)))
        return buckets

    def submit(self, timestamp, value):
        timestamp = round_timestamp(timestamp, self.config.primary_interval.total_seconds())
        self.primary_buffer.push(timestamp, value)

        for b in self.config.buckets:
            if timestamp % b.interval.total_seconds() == 0:
                self.persist(timestamp, self.bucket_buffers[b.index], b)

        self.context.client.emit_event('statd.{0}.pulse'.format(self.name), {
            'value': value,
            'change': self.last_value - value,
            'nolog': True
        })

        self.last_value = value

    def persist(self, timestamp, buffer, bucket):
        data = self.bucket_buffers[0].data
        df = pd.TimeSeries(index=data['timestamp'], data=data['value'])
        df = df[bucket.covered_start:bucket.covered_end]
        buffer.push(timestamp, df.mean())

    def query(self, start, end, frequency):
        self.logger.debug('Query: start={0}, end={1}, frequency={2}'.format(start, end, frequency))
        buckets = list(self.config.get_covered_buckets(start, end))
        df = pd.DataFrame()

        for b in buckets:
            new = self.bucket_buffers[b.index].df
            if new is not None:
                df = pd.concat((df, new))

        df = df.sort()[0]
        df = df[start:end]
        df = df.resample(frequency, how='mean').interpolate()
        return df


class InputServer(object):
    def __init__(self, context):
        super(InputServer, self).__init__()
        self.context = context
        self.server = StreamServer(('127.0.0.1', 2003), handle=self.handle)

    def start(self):
        gevent.spawn(self.server.serve_forever())

    def handle(self, socket, address):
        fd = socket.makefile()
        while True:
            line = fd.readline()
            if not line:
                break

            name, value, timestamp = line.split()
            ds = self.context.get_data_source(name)
            ds.submit(int(timestamp), float(value))

        socket.shutdown(gevent.socket.SHUT_RDWR)
        socket.close()


class OutputService(RpcService):
    def __init__(self, context):
        super(OutputService, self).__init__()
        self.context = context

    def enable(self, event):
        pass

    def disable(self, event):
        pass

    def get_data_sources(self):
        return self.context.data_sources.keys()

    def query(self, data_source, params):
        start = parse_datetime(params.pop('start'))
        end = parse_datetime(params.pop('end'))
        frequency = params.pop('frequency')

        if type(data_source) is unicode:
            if data_source not in self.context.data_sources:
                raise RpcException(errno.ENOENT, 'Data source {0} not found'.format(data_source))

            ds = self.context.data_sources[data_source]
            df = ds.query(start, end, frequency)
            return {
                'data': [
                    [df.index[i].value // 10 ** 9, str(df[i])] for i in range(len(df))
                ]
            }

        if type(data_source) is list:
            final = pd.DataFrame()
            for ds_name in data_source:
                if ds_name not in self.context.data_sources:
                    raise RpcException(errno.ENOENT, 'Data source {0} not found'.format(ds_name))

                ds = self.context.data_sources[ds_name]
                final[ds_name] = ds.query(start, end, frequency)

            return {
                'data': [
                    [final.index[i].value // 10 ** 9] + [str(final[col][i]) for col in data_source] for i in range(len(final))
                ]
            }


class DataPoint(tables.IsDescription):
    timestamp = tables.Time32Col()
    value = tables.FloatCol()


class Main(object):
    def __init__(self):
        self.client = None
        self.server = None
        self.datastore = None
        self.hdf = None
        self.hdf_group = None
        self.config = None
        self.logger = logging.getLogger('statd')
        self.data_sources = {}

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

    def init_database(self):
        directory = self.client.call_sync('system-dataset.request_directory', 'statd')
        self.hdf = tables.open_file(os.path.join(directory, DEFAULT_DBFILE), mode='a')
        if not hasattr(self.hdf.root, 'stats'):
            self.hdf.create_group('/', 'stats')

        self.hdf_group = self.hdf.root.stats

    def request_table(self, name):
        try:
            if hasattr(self.hdf_group, name):
                return getattr(self.hdf_group, name)

            return self.hdf.create_table(self.hdf_group, name, DataPoint, name)
        except Exception, e:
            self.logger.error(str(e))

    def get_data_source(self, name):
        if name not in self.data_sources.keys():
            config = DataSourceConfig(self.datastore, name)
            ds = DataSource(self, name, config)
            self.data_sources[name] = ds

        return self.data_sources[name]

    def init_dispatcher(self):
        self.client = Client()
        self.client.connect('127.0.0.1')
        self.client.on_error(self.dispatcher_error)
        self.client.login_service('statd')
        self.client.enable_server()

    def die(self):
        self.client.disconnect()
        sys.exit(0)

    def dispatcher_error(self, error):
        self.die()

    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', metavar='CONFIG', default=DEFAULT_CONFIGFILE, help='Middleware config file')
        args = parser.parse_args()
        logging.basicConfig(level=logging.DEBUG)
        setproctitle.setproctitle('fnstatd')

        # Signal handlers
        gevent.signal(signal.SIGQUIT, self.die)
        gevent.signal(signal.SIGQUIT, self.die)
        gevent.signal(signal.SIGINT, self.die)

        self.server = InputServer(self)
        self.parse_config(args.c)
        self.init_datastore()
        self.init_dispatcher()
        self.init_database()
        self.client.enable_server()
        self.client.register_service('statd.output', OutputService(self))
        self.server.start()
        self.client.call_sync('service.ensure_started', 'collectd')
        self.logger.info('Started')
        self.client.wait_forever()


if __name__ == '__main__':
    m = Main()
    m.main()
