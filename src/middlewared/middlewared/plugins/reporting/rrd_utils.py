import os
import json
import re
import statistics
import subprocess
import textwrap


RRD_BASE_PATH = '/var/db/collectd/rrd/localhost'
RE_COLON = re.compile('(.+):(.+)$')
RE_NAME = re.compile(r'(%name_(\d+)%)')
RE_NAME_NUMBER = re.compile(r'(.+?)(\d+)$')
RE_RRDPLUGIN = re.compile(r'^(?P<name>.+)Plugin$')
RRD_PLUGINS = {}


class RRDMeta(type):

    def __new__(cls, name, bases, dct):
        klass = type.__new__(cls, name, bases, dct)
        reg = RE_RRDPLUGIN.search(name)
        if reg and not hasattr(klass, 'plugin'):
            klass.plugin = reg.group('name').lower()
        elif name != 'RRDBase' and not hasattr(klass, 'plugin'):
            raise ValueError(f'Could not determine plugin name for {name!r}')

        if reg and not hasattr(klass, 'name'):
            klass.name = reg.group('name').lower()
            RRD_PLUGINS[klass.name] = klass
        elif hasattr(klass, 'name'):
            RRD_PLUGINS[klass.name] = klass
        elif name != 'RRDBase':
            raise ValueError(f'Could not determine class name for {name!r}')
        return klass


class RRDBase(object, metaclass=RRDMeta):

    aggregations = ('min', 'mean', 'max')
    base_path = None
    title = None
    vertical_label = None
    identifier_plugin = True
    rrd_types = None
    rrd_data_extra = None
    stacked = False
    stacked_show_total = False

    AGG_MAP = {
        'min': min,
        'mean': statistics.mean,
        'max': max,
    }

    def __init__(self, middleware):
        self.middleware = middleware
        self._base_path = RRD_BASE_PATH
        self.base_path = os.path.join(self._base_path, self.plugin)

    def __repr__(self):
        return f'<RRD:{self.plugin}>'

    def get_title(self):
        return self.title

    def get_vertical_label(self):
        return self.vertical_label

    def get_rrd_types(self, identifier=None):
        return self.rrd_types

    def __getstate__(self):
        return {
            'name': self.name,
            'title': self.get_title(),
            'vertical_label': self.get_vertical_label(),
            'identifiers': self.get_identifiers(),
            'stacked': self.stacked,
            'stacked_show_total': self.stacked_show_total,
        }

    @staticmethod
    def _sort_ports(entry):
        if entry == 'ha':
            pref = '0'
            body = entry
        else:
            reg = RE_COLON.search(entry)
            if reg:
                pref = reg.group(1)
                body = reg.group(2)
            else:
                pref = ''
                body = entry
        reg = RE_NAME_NUMBER.search(body)
        if not reg:
            return (pref, body, -1)
        return (pref, reg.group(1), int(reg.group(2)))

    @staticmethod
    def _sort_disks(entry):
        reg = RE_NAME_NUMBER.search(entry)
        if not reg:
            return (entry, )
        if reg:
            return (reg.group(1), int(reg.group(2)))

    def get_identifiers(self):
        return None

    def encode(self, identifier):
        return identifier

    def has_data(self):
        if self.get_identifiers() is not None or not self.rrd_types:
            return True
        for _type, dsname, transform, in self.rrd_types:
            direc = self.plugin
            path = os.path.join(self._base_path, direc, f'{_type}.rrd')
            if os.path.exists(path):
                return True
        return False

    def get_defs(self, identifier):

        rrd_types = self.get_rrd_types(identifier)
        if not rrd_types:
            raise RuntimeError(f'rrd_types not defined for {self.name!r}')

        args = []
        defs = {}
        for i, rrd_type in enumerate(rrd_types):
            _type, dsname, transform = rrd_type
            direc = self.plugin
            if self.identifier_plugin and identifier:
                identifier = self.encode(identifier)
                direc += f'-{identifier}'
            path = os.path.join(self._base_path, direc, f'{_type}.rrd')
            path = path.replace(':', r'\:')
            name = f'{_type}_{dsname}'
            defs[i] = {
                'name': name,
                'transform': transform,
            }
            args += [
                f'DEF:{name}={path}:{dsname}:AVERAGE',
            ]

        for i, attrs in defs.items():
            if attrs['transform']:
                transform = attrs['transform']
                if '%name%' in transform:
                    transform = transform.replace('%name%', attrs['name'])
                for orig, number in RE_NAME.findall(transform):
                    transform = transform.replace(orig, defs[int(number)]['name'])
                args += [
                    f'CDEF:c{attrs["name"]}={transform}',
                    f'XPORT:c{attrs["name"]}:{attrs["name"]}',
                ]
            else:
                args += [f'XPORT:{attrs["name"]}:{attrs["name"]}']

        if self.rrd_data_extra:
            extra = textwrap.dedent(self.rrd_data_extra)
            for orig, number in RE_NAME.findall(extra):
                def_ = defs[int(number)]
                name = def_['name']
                if def_['transform']:
                    name = 'c' + name
                extra = extra.replace(orig, name)
            args += extra.split()

        return args

    def export(self, identifier, starttime, endtime, aggregate=True):
        args = [
            'rrdtool',
            'xport',
            '--daemon', 'unix:/var/run/rrdcached.sock',
            '--json',
            '--end', endtime,
            '--start', starttime,
        ]
        args.extend(self.get_defs(identifier))
        cp = subprocess.run(args, capture_output=True)
        if cp.returncode != 0:
            raise RuntimeError(f'Failed to export RRD data: {cp.stderr.decode()}')

        data = json.loads(cp.stdout)
        data = dict(
            name=self.name,
            identifier=identifier,
            data=data['data'],
            **data['meta'],
            aggregations=dict(),
        )

        if self.aggregations and aggregate:
            # Transpose the data matrix and remove null values
            transposed = [list(filter(None.__ne__, i)) for i in zip(*data['data'])]
            for agg in self.aggregations:
                if agg in self.AGG_MAP:
                    data['aggregations'][agg] = [
                        (self.AGG_MAP[agg](i) if i else None)
                        for i in transposed
                    ]
                else:
                    raise RuntimeError(f'Aggregation {agg!r} is invalid.')

        return data
