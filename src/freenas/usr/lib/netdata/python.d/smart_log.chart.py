# -*- coding: utf-8 -*-
# Description: smart netdata python.d module
# Author: ilyam8, vorph1
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import re

from copy import deepcopy
from pathlib import Path
from time import time

from bases.FrameworkServices.SimpleService import SimpleService
from bases.collection import read_last_line


ABSOLUTE = 'absolute'
ATA = 'ata'
ATTR194 = '194'
ATTR_TEMPERATURE = 'temperature'
CSV = '.csv'
DEF_AGE = 30
DEF_PATH = '/var/log/smartd'
DEF_RESCAN_INTERVAL = 60
INCREMENTAL = 'incremental'
RE_ATA = re.compile(
    r'(\d+);'  # attribute
    r'(\d+);'  # normalized value
    r'(\d+)',  # raw value
    re.X
)
RE_SCSI = re.compile(
    r'([a-z-]+);'  # attribute
    r'([0-9.]+)',  # raw value
    re.X
)
SCSI = 'scsi'


# Netdata specific
CHARTS = {}
ORDER = []


def get_nvme_disks():
    nvme_disks = []
    for i in Path('/sys/class/hwmon/').glob('*'):
        try:
            if not ((i / 'name').read_text().strip() == 'nvme'):
                continue
        except FileNotFoundError:
            continue

        try:
            round(int((i / 'temp1_input').read_text()) * 0.001)
        except Exception:
            continue

        try:
            for j in filter(lambda x: x.is_dir() and x.name.startswith('nvme'), (i / 'device').iterdir()):
                nvme_disks.append((j.name, str(i)))
                break
        except FileNotFoundError:
            continue
    return nvme_disks


class BaseAtaSmartAttribute:
    def __init__(self, name, normalized_value, raw_value):
        self.name = name
        self.normalized_value = normalized_value
        self.raw_value = raw_value

    def value(self):
        raise NotImplementedError


class BaseNvmeSmartValue:
    def __init__(self, raw_value):
        self.name = 'temperature'
        self.raw_value = raw_value

    def value(self):
        raise NotImplementedError


class NvmeRaw(BaseNvmeSmartValue):
    def value(self):
        return self.raw_value


class AtaRaw(BaseAtaSmartAttribute):
    def value(self):
        return self.raw_value


class AtaNormalized(BaseAtaSmartAttribute):
    def value(self):
        return self.normalized_value


class Ata194(BaseAtaSmartAttribute):
    # https://github.com/netdata/netdata/issues/3041
    # https://github.com/netdata/netdata/issues/5919
    #
    # The low byte is the current temperature, the third lowest is the maximum, and the fifth lowest is the minimum
    def value(self):
        value = int(self.raw_value)
        if value > 1e6:
            return value & 0xFF
        return min(int(self.normalized_value), int(self.raw_value))


class BaseSCSISmartAttribute:
    def __init__(self, name, raw_value):
        self.name = name
        self.raw_value = raw_value

    def value(self):
        raise NotImplementedError


class SCSIRaw(BaseSCSISmartAttribute):
    def value(self):
        return self.raw_value


def ata_attribute_factory(value):
    name = value[0]
    if name == ATTR194:
        return Ata194(*value)


def scsi_attribute_factory(value):
    return SCSIRaw(*value)


def attribute_factory(value):
    name = value[0]
    if name.isdigit():
        return ata_attribute_factory(value)
    return scsi_attribute_factory(value)


def handle_error(*errors):
    def on_method(method):
        def on_call(*args):
            try:
                return method(*args)
            except errors:
                return None

        return on_call

    return on_method


class DiskLogFile:
    def __init__(self, full_path):
        self.path = full_path
        self.size = os.path.getsize(full_path)

    @handle_error(OSError)
    def is_changed(self):
        return self.size != os.path.getsize(self.path)

    @handle_error(OSError)
    def is_active(self, current_time, limit):
        return (current_time - os.path.getmtime(self.path)) / 60 < limit

    @handle_error(OSError)
    def read(self):
        self.size = os.path.getsize(self.path)
        return read_last_line(self.path)


class BaseDisk:
    def __init__(self, name, log_file):
        self.raw_name = name
        self.name = name.rsplit('-', 1)[-1]
        self.log_file = log_file
        self.attrs = list()
        self.alive = True
        self.charted = False

    def __eq__(self, other):
        if isinstance(other, BaseDisk):
            return self.raw_name == other.raw_name
        return self.raw_name == other

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(repr(self))

    def parser(self, data):
        raise NotImplementedError

    @handle_error(TypeError)
    def populate_attrs(self):
        self.attrs = list()
        line = self.log_file.read()
        for value in self.parser(line):
            if attr := attribute_factory(value):
                self.attrs.append(attr)

        return len(self.attrs)

    def data(self):
        data = dict()
        for attr in self.attrs:
            data[self.name] = attr.value()
        return data


class ATADisk(BaseDisk):
    def parser(self, data):
        return RE_ATA.findall(data)


class SCSIDisk(BaseDisk):
    def parser(self, data):
        return RE_SCSI.findall(data)


class NVMEDisk(BaseDisk):
    def __init__(self, name, hwmon_path):
        super().__init__(name, None)
        self.hwmon_path = hwmon_path

    def parser(self, data):
        return

    def read_nvme_temp(self):
        try:
            return round(int((Path(self.hwmon_path) / 'temp1_input').read_text()) * 0.001)
        except Exception:
            return 0

    @handle_error(TypeError)
    def populate_attrs(self):
        self.attrs = list()
        temp = str(self.read_nvme_temp())
        self.attrs.append(NvmeRaw(temp))
        return len(self.attrs)

    def data(self):
        data = {}
        for attr in self.attrs:
            data[self.name] = attr.value()
        return data


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.order = ORDER
        self.definitions = deepcopy(CHARTS)
        self.log_path = configuration.get('log_path', DEF_PATH)
        self.age = configuration.get('age', DEF_AGE)
        self.exclude = configuration.get('exclude_disks', str()).split()
        self.disks = list()
        self.runs = 0
        self.do_force_rescan = False

    def check(self):
        return self.scan() > 0

    def get_chart_name(self, disk):
        return f'disktemp.{disk.name}'

    def get_data(self):
        self.runs += 1

        if self.do_force_rescan or self.runs % DEF_RESCAN_INTERVAL == 0:
            self.cleanup()
            self.scan()
            self.do_force_rescan = False

        data = dict()

        for disk in self.disks:
            if not disk.alive:
                continue

            self.add_disk_to_charts(disk)

            changed = disk.log_file.is_changed() if disk.log_file else False

            if changed is None and disk.log_file is not None:
                disk.alive = False
                self.do_force_rescan = True
                continue

            if disk.populate_attrs() is None and changed:
                disk.alive = False
                self.do_force_rescan = True
                continue
            data.update(disk.data())

        return data

    def cleanup(self):
        current_time = time()
        for disk in self.disks[:]:
            if any(
                [
                    not disk.alive,
                    not disk.log_file.is_active(current_time, self.age),
                ]
            ):
                self.disks.remove(disk.raw_name)
                self.remove_disk_from_charts(disk)

    def scan(self):
        self.debug('scanning {0}'.format(self.log_path))
        current_time = time()

        for full_name in os.listdir(self.log_path):
            disk = self.create_disk_from_file(full_name, current_time)
            if not disk:
                continue
            self.disks.append(disk)
        for nvme_name, nvme_path in get_nvme_disks():
            self.disks.append(NVMEDisk(nvme_name, nvme_path))
        return len(self.disks)

    def create_disk_from_file(self, full_name, current_time):
        if not full_name.endswith(CSV):
            self.debug('skipping {0}: not a csv file'.format(full_name))
            return None

        name = os.path.basename(full_name).split('.')[-3]
        path = os.path.join(self.log_path, full_name)

        if name in self.disks:
            self.debug('skipping {0}: already in disks'.format(full_name))
            return None

        if [p for p in self.exclude if p in name]:
            self.debug('skipping {0}: filtered by `exclude` option'.format(full_name))
            return None

        if not os.access(path, os.R_OK):
            self.debug('skipping {0}: not readable'.format(full_name))
            return None

        if os.path.getsize(path) == 0:
            self.debug('skipping {0}: zero size'.format(full_name))
            return None

        if (current_time - os.path.getmtime(path)) / 60 > self.age:
            self.debug('skipping {0}: haven\'t been updated for last {1} minutes'.format(full_name, self.age))
            return None

        if ATA in full_name:
            disk = ATADisk(name, DiskLogFile(path))
        elif SCSI in full_name:
            disk = SCSIDisk(name, DiskLogFile(path))
        else:
            self.debug('skipping {0}: unknown type'.format(full_name))
            return None

        disk.populate_attrs()
        if not disk.attrs:
            self.error('skipping {0}: parsing failed'.format(full_name))
            return None

        self.debug('added {0}'.format(full_name))
        return disk

    def add_disk_to_charts(self, disk):
        chart_name = self.get_chart_name(disk)
        if chart_name in self.charts:
            return

        disk.charted = True
        self.charts.add_chart([
            chart_name, chart_name, 'Temperature', 'celsius', 'temperature', 'smartd_log.temperature_celsius', 'line',
        ])
        self.charts[chart_name].add_dimension([disk.name])

    def remove_disk_from_charts(self, disk):
        if len(self.charts) == 0 or not disk.charted:
            return

        chart_name = self.get_chart_name(disk)
        if not disk.name or chart_name not in self.charts:
            self.charts[chart_name].del_dimension(disk.name)
