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
import re
import errno
import gevent
from collections import defaultdict
from cache import CacheStore
from lib import geom
from lib.system import system, SubprocessException
from task import Provider, Task, TaskStatus, TaskException, VerifyException, query
from dispatcher.rpc import RpcException, accepts, returns, description
from dispatcher.rpc import SchemaHelper as h


diskinfo_cache = CacheStore()
camcontrol_cache = CacheStore()


class DiskProvider(Provider):
    @query('disk')
    def query(self, filter=None, params=None):
        def extend(disk):
            disk['online'] = self.is_online(disk['path'])
            disk['label-path'] = ''
            disk['uuid-path'] = ''
            return disk

        return self.datastore.query('disks', *(filter or []), callback=extend, **(params or {}))

    @accepts(str)
    @returns(bool)
    def is_online(self, name):
        return os.path.exists(name)

    @accepts(str)
    @returns(str)
    def partition_to_disk(self, part_name):
        part = self.get_partition_config(part_name)
        return part['disk']

    @accepts(str)
    @returns(str)
    def disk_to_data_partition(self, disk_name):
        disk = diskinfo_cache.get(disk_name)
        return disk['data-partition-path']

    @accepts(str)
    def get_disk_config(self, name):
        if not diskinfo_cache.exists(name):
            raise RpcException(errno.ENOENT, "Disk {0} not found".format(name))

        return diskinfo_cache.get(name)

    @accepts(str)
    def get_partition_config(self, part_name):
        for name, disk in diskinfo_cache.itervalid():
            for part in disk['partitions']:
                if part_name in part['paths']:
                    result = part.copy()
                    result['disk'] = name
                    return result

        raise RpcException(errno.ENOENT, "Partition {0} not found".format(part_name))


@accepts(str, str, h.object())
class DiskGPTFormatTask(Task):
    def describe(self, disk, fstype, params=None):
        return "Formatting disk {0}".format(os.path.basename(disk))

    def verify(self, disk, fstype, params=None):
        if not diskinfo_cache.exists(disk):
            raise VerifyException(errno.ENOENT, "Disk {0} not found".format(disk))

        if fstype not in ['freebsd-zfs']:
            raise VerifyException(errno.EINVAL, "Unsupported fstype {0}".format(fstype))

        return ['disk:{0}'.format(disk)]

    def run(self, disk, fstype, params=None):
        if params is None:
            params = {}

        blocksize = params.pop('blocksize', 4096)
        swapsize = params.pop('swapsize', '2048M')
        bootcode = params.pop('bootcode', '/boot/pmbr-datadisk')

        try:
            system('/sbin/gpart', 'destroy', '-F', disk)
        except SubprocessException:
            # ignore
            pass

        try:
            system('/sbin/gpart', 'create', '-s', 'gpt', disk)
            if swapsize > 0:
                system('/sbin/gpart', 'add', '-a', str(blocksize), '-b', '128', '-s', swapsize, '-t', 'freebsd-swap', disk)
                system('/sbin/gpart', 'add', '-a', str(blocksize), '-t', fstype, disk)
            else:
                system('/sbin/gpart', 'add', '-a', str(blocksize), '-b', '128', '-t', fstype, disk)

            system('/sbin/gpart', 'bootcode', '-b', bootcode, disk)
        except SubprocessException, err:
            raise TaskException(errno.EFAULT, 'Cannot format disk: {0}'.format(err.err))

        generate_disk_cache(self.dispatcher, disk)


@accepts(str, bool)
class DiskEraseTask(Task):
    def __init__(self, dispatcher):
        super(DiskEraseTask, self).__init__(dispatcher)
        self.started = False
        self.mediasize = 0
        self.remaining = 0

    def verify(self, disk, erase_data=False):
        if not diskinfo_cache.exists(disk):
            raise VerifyException(errno.ENOENT, "Disk {0} not found".format(disk))

        return ['disk:{0}'.format(disk)]

    def run(self, disk, erase_data=False):
        try:
            system('/sbin/zpool', 'labelclear', '-f', disk)
            system('/sbin/gpart', 'destroy', '-F', disk)
        except SubprocessException, err:
            raise TaskException(errno.EFAULT, 'Cannot erase disk: {0}'.format(err.err))

        if erase_data:
            diskinfo = diskinfo_cache.get(disk)
            fd = open(disk, 'w')
            zeros = b'\0' * (1024 * 1024)
            self.mediasize = diskinfo['mediasize']
            self.remaining = self.mediasize
            self.started = True

            while self.remaining > 0:
                amount = min(len(zeros), self.remaining)
                fd.write(zeros[:amount])
                fd.flush()
                self.remaining -= amount

        generate_disk_cache(self.dispatcher, disk)

    def get_status(self, disk):
        if not self.started:
            return TaskStatus(0, 'Erasing disk...')

        return TaskStatus(self.remaining / self.mediasize, 'Erasing disk...')


@accepts({
    'allOf': [
        {'$ref': 'disk'},
        {'not': {'required': ['name', 'serial', 'description', 'mediasize']}}
    ]
})
class DiskConfigureTask(Task):
    def verify(self, name, updated_fields):
        return [os.path.basename(name)]

    def run(self, name, updated_fields):
        disk = self.datastore.query('disks', ('name', '=', name))
        diskinfo_cache.invalidate(disk)


class DiskDeleteTask(Task):
    def verify(self, name):
        pass

    def run(self, name):
        pass


def generate_camcontrol_cache():
    """
    Parse camcontrol devlist -v output to gather
    controller id, channel no and driver from a device
    Returns:
        dict(devname) = dict(drv, controller, channel)

    Hacky workaround
    It is known that at least some HPT controller have a bug in the
    camcontrol devlist output with multiple controllers, all controllers
    will be presented with the same driver with index 0
    e.g. two hpt27xx0 instead of hpt27xx0 and hpt27xx1
    What we do here is increase the controller id by its order of
    appearance in the camcontrol output
    """
    hptctlr = defaultdict(int)

    re_drv_cid = re.compile(r'.* on (?P<drv>.*?)(?P<cid>[0-9]+) bus', re.S | re.M)
    re_tgt = re.compile(r'target (?P<tgt>[0-9]+) .*?lun (?P<lun>[0-9]+) .*\((?P<dv1>[a-z]+[0-9]+),(?P<dv2>[a-z]+[0-9]+)\)', re.S | re.M)
    drv, cid, tgt, lun, dev, devtmp = (None, ) * 6

    out, err = system('camcontrol', 'devlist', '-v')
    for line in out.splitlines():
        if not line.startswith('<'):
            reg = re_drv_cid.search(line)
            if not reg:
                continue
            drv = reg.group("drv")
            if drv.startswith("hpt"):
                cid = hptctlr[drv]
                hptctlr[drv] += 1
            else:
                cid = reg.group("cid")
        else:
            reg = re_tgt.search(line)
            if not reg:
                continue
            tgt = reg.group("tgt")
            lun = reg.group("lun")
            dev = reg.group("dv1")
            devtmp = reg.group("dv2")
            if dev.startswith("pass"):
                dev = devtmp

            camcontrol_cache.put(os.path.join('/dev', dev), {
                'drv': drv,
                'controller': int(cid),
                'channel': int(tgt),
                'lun': int(lun)
            })


def get_twcli(controller):
    re_port = re.compile(r'^p(?P<port>\d+).*?\bu(?P<unit>\d+)\b', re.S | re.M)
    output, err = system("/usr/local/sbin/tw_cli", "/c{0}".format(controller), "show")

    units = {}
    for port, unit in re_port.findall(output):
        units[int(unit)] = int(port)

    return units


def device_to_identifier(doc, name, serial=None):
    if serial:
        return "serial:{0}".format(serial)

    search = doc.xpath("//class[name = 'PART']/..//*[name = '{0}']//config[type = 'freebsd-zfs']/rawuuid".format(name))
    if len(search) > 0:
        return "uuid:{0}".format(search[0].text)

    search = doc.xpath("//class[name = 'PART']/geom/..//*[name = '{0}']//config[type = 'freebsd-ufs']/rawuuid".format(name))
    if len(search) > 0:
        return "uuid:{0}".format(search[0].text)

    search = doc.xpath("//class[name = 'LABEL']/geom[name = '{0}']/provider/name".format(name))
    if len(search) > 0:
        return "label:{0}".format(search[0].text)

    search = doc.xpath("//class[name = 'DEV']/geom[name = '{0}']".format(name))
    if len(search) > 0:
        return "devicename:{0}".format(name)

    return ''


def info_from_device(devname):
    args = [devname]
    info = camcontrol_cache.get(devname)
    if info is not None:
        if info.get("drv") == "rr274x_3x":
            channel = info["channel"] + 1
            if channel > 16:
                channel -= 16
            elif channel > 8:
                channel -= 8
            args = [
                "/dev/%s" % info["drv"],
                "-d",
                "hpt,%d/%d" % (info["controller"] + 1, channel)
            ]
        elif info.get("drv").startswith("arcmsr"):
            args = [
                "/dev/%s%d" % (info["drv"], info["controller"]),
                "-d",
                "areca,%d" % (info["lun"] + 1 + (info["channel"] * 8), )
            ]
        elif info.get("drv").startswith("hpt"):
            args = [
                "/dev/%s" % info["drv"],
                "-d",
                "hpt,%d/%d" % (info["controller"] + 1, info["channel"] + 1)
            ]
        elif info.get("drv") == "ciss":
            args = [
                "/dev/%s%d" % (info["drv"], info["controller"]),
                "-d",
                "cciss,%d" % (info["channel"], )
            ]
        elif info.get("drv") == "twa":
            twcli = get_twcli(info["controller"])
            args = [
                "/dev/%s%d" % (info["drv"], info["controller"]),
                "-d",
                "3ware,%d" % (twcli.get(info["channel"], -1), )
            ]

    output, err = system("/usr/local/sbin/smartctl", "-a", *args)
    search = re.finditer(r'Serial Number:\s+(?P<serial>.+)|' +
                         r'Rotation Rate:\s+(?P<rate>.+)|' +
                         r'SMART support is:\s+(?P<smartenabled>.+)|' +
                         r'SMART overall-health self-assessment test result:\s+(?P<smartstatus>.+)|'
                         + r'Model Family:\s+(?P<model>.+)|',
                         output, re.I)
    disk_info = {'serial': '', 'rate': '', 'smartenabled': '',
                 'smartstatus': '', 'model': ''}
    if search:
        for x in search:
            if x.group("serial"):
                disk_info['serial'] = x.group("serial")
                continue
            if x.group("rate"):
                disk_info['rate'] = x.group("rate")
                continue
            if x.group("smartenabled"):
                disk_info['smartenabled'] = x.group("smartenabled")
                continue
            if x.group("smartstatus"):
                disk_info['smartstatus'] = x.group("smartstatus")
                continue
            if x.group("model"):
                disk_info['model'] = x.group("model")
                continue
        # serial = search.group("serial")
        return disk_info

    return None


def generate_disk_cache(dispatcher, path):
    confxml = geom.confxml()
    name = os.path.basename(path)
    gdisk = confxml.xpath("/mesh/class[name='DISK']/geom[name='{0}']".format(name))
    gpart = confxml.xpath("/mesh/class[name='PART']/geom[name='{0}']".format(name))

    if not gdisk:
        return

    gdisk = gdisk.pop()
    gpart = gpart.pop() if gpart else None
    provider = gdisk.find('provider')
    partitions = []

    if gpart:
        for p in gpart.findall('provider'):
            paths = [os.path.join("/dev", p.find("name").text)]
            label = p.find("config/label").text
            uuid = p.find("config/rawuuid").text

            if label:
                paths.append(os.path.join("/dev/gpt", label))

            if uuid:
                paths.append(os.path.join("/dev/gptid", uuid))

            partitions.append({
                'name': p.find("name").text,
                'paths': paths,
                'mediasize': int(p.find("mediasize").text),
                'uuid': p.find("config/rawuuid").text,
                'type': p.find("config/type").text,
                'label': p.find("config/label").text if p.find("config/label") else None
            })

    disk_info = info_from_device(path)
    serial = disk_info['serial']
    rate = disk_info['rate']
    smartenabled = disk_info['smartenabled']
    smartstatus = disk_info['smartenabled']
    model = disk_info['model']
    identifier = device_to_identifier(confxml, name, serial)
    data_partitions = filter(lambda x: x['type'] == 'freebsd-zfs', partitions)
    data_uuid = data_partitions[0].get('uuid') if len(data_partitions) > 0 else None

    disk = {
        'mediasize': int(provider.find("mediasize").text),
        'sectorsize': int(provider.find("sectorsize").text),
        'description': provider.find("config/descr").text,
        'identifier': identifier,
        'serial': serial,
        'max-rotation': rate,
        'smart-enabled': smartenabled,
        'smart-status': smartstatus,
        'model': model,
        'id': identifier,
        'schema': gpart.find("config/scheme").text if gpart else None,
        'controller': camcontrol_cache.get(name),
        'partitions': partitions,
        'data-partition-uuid': data_uuid,
        'data-partition-path': os.path.join("/dev/gptid", data_uuid) if data_uuid else None
    }

    diskinfo_cache.put(path, disk)
    ds_disk = dispatcher.datastore.get_one('disks', ('path', '=', path))

    if ds_disk is None:
        dispatcher.datastore.insert('disks', {
            'id': identifier,
            'path': path,
            'mediasize': disk['mediasize'],
            'serial': disk['serial'],
            'data-partition-uuid': disk['data-partition-uuid']
        })
    else:
        if ds_disk['id'] != identifier or disk['data-partition-uuid'] != ds_disk['data-partition-uuid']:
            oldid = ds_disk['id']
            ds_disk.update({
                'id': identifier,
                'serial': disk['serial'],
                'data-partition-uuid': disk['data-partition-uuid']
            })

            dispatcher.datastore.update('disks', oldid, ds_disk)


def purge_disk_cache(path):
    diskinfo_cache.remove(path)


def _depends():
    return ['DevdPlugin']


def _init(dispatcher, plugin):
    def on_device_attached(args):
        path = args['path']
        if not re.match(r'^/dev/(da|ad|ada)[0-9]+$', path):
            return

        # Regenerate camcontrol and disk cache
        generate_camcontrol_cache()
        generate_disk_cache(dispatcher, path)

        # Push higher tier event
        disk = diskinfo_cache.get(path)
        dispatcher.dispatch_event('disks.changed', {
            'operation': 'created',
            'ids': [disk['id']]
        })

    def on_device_detached(args):
        path = args['path']

        if re.match(r'^/dev/(da|ad|ada)[0-9]+$', path):
            purge_disk_cache(path)
            disk = dispatcher.datastore.get_one('disks', ('path', '=', path))
            dispatcher.datastore.delete('disks', disk['id'])
            dispatcher.dispatch_event('disks.changed', {
                'operation': 'delete',
                'ids': [disk['id']]
            })

        if re.match(r'^/dev/gptid/[a-f0-9-]+$', path):
            pass

    def on_device_mediachange(args):
        # Regenerate caches
        generate_camcontrol_cache()
        generate_disk_cache(dispatcher, args['path'])

        # Disk may be detached in the meantime
        disk = diskinfo_cache.get(args['path'])
        if not disk:
            return

        dispatcher.dispatch_event('disks.changed', {
            'operation': 'update',
            'ids': [disk['id']]
        })

    plugin.register_schema_definition('disk', {
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'description': {'type': 'string'},
            'serial': {'type': 'string'},
            'max-rotation': {'type': 'string'},
            'smart-enabled': {'type': 'string'},
            'smart-status': {'type': 'string'},
            'model': {'type': 'string'},
            'mediasize': {'type': 'integer'},
            'smart': {'type': 'boolean'},
            'smart-options': {'type': 'string'},
            'standby-mode': {
                'type': 'string'
            },
            'acoustic-level': {
                'type': 'string'
            },
            'apm-mode': {
                'type': 'string'
            }
        }
    })

    dispatcher.require_collection('disks')
    plugin.register_provider('disks', DiskProvider)
    plugin.register_event_handler('system.device.attached', on_device_attached)
    plugin.register_event_handler('system.device.detached', on_device_detached)
    plugin.register_event_handler('system.device.mediachange', on_device_mediachange)
    plugin.register_task_handler('disk.erase', DiskEraseTask)
    plugin.register_task_handler('disk.format.gpt', DiskGPTFormatTask)
    plugin.register_task_handler('disk.configure', DiskConfigureTask)
    plugin.register_task_handler('disk.delete', DiskDeleteTask)

    plugin.register_event_type('disks.changed')

    for i in dispatcher.rpc.call_sync('system.device.get_devices', 'disk'):
        on_device_attached({'path': i['path']})
