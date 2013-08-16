#!/usr/bin/env python
#-
# Copyright (c) 2011 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
from decimal import Decimal
import logging
import os
import re
import subprocess

from django.utils.datastructures import SortedDict
from django.utils.translation import ugettext_lazy as _

from freenasUI.common import humanize_size

log = logging.getLogger('middleware.zfs')

ZPOOL_NAME_RE = r'[a-z][a-z0-9_\-\.]+'


def _is_vdev(name):
    """
    Find out if a given name is a reserved word in zfs
    """
    if (
        name in ('stripe', 'mirror', 'raidz', 'raidz1', 'raidz2', 'raidz3')
        or
        re.search(r'^(mirror|raidz|raidz1|raidz2|raidz3)(-\d+)?$', name)
    ):
        return True
    return False


def _vdev_type(name):
    # raidz needs to appear after other raidz types
    supported_types = ('stripe', 'mirror', 'raidz3', 'raidz2', 'raidz')
    for _type in supported_types:
        if name.startswith(_type):
            return _type
    return False


def zfs_size_to_bytes(size):
    if 'K' in size:
        return Decimal(size.replace('K', '')) * 1024
    elif 'M' in size:
        return Decimal(size.replace('M', '')) * 1048576
    elif 'G' in size:
        return Decimal(size.replace('G', '')) * 1073741824
    elif 'T' in size:
        return Decimal(size.replace('T', '')) * 1099511627776
    else:
        return size


class Pool(object):
    """
    Class representing a Zpool
    """
    id = None
    name = None
    scrub = None

    data = None
    cache = None
    spares = None
    logs = None

    def __init__(self, pid, name, scrub):
        self.id = pid
        self.name = name
        self.scrub = scrub

    def __getitem__(self, name):
        if hasattr(self, name):
            return getattr(self, name)
        elif name == self.name:
            return self.data
        else:
            raise KeyError

    def add_root(self, root):
        """
        Add a Root to Zpool
        Generally speaking a root can be the data vdevs,
            cache, spares or logs
        """
        if root.name == self.name:
            self.data = root
        else:
            setattr(self, root.name, root)
        root.parent = self

    def find_not_online(self):
        """
        Get disks used within this pool
        """
        unavails = []
        for key in ('data', 'cache', 'spares', 'logs'):
            if getattr(self, key):
                unavails.extend(getattr(self, key).find_not_online())
        return unavails

    def get_devs(self):
        """
        Get disks used within this pool
        """
        devs = []
        for key in ('data', 'cache', 'spares', 'logs'):
            klass = getattr(self, key)
            if klass is None:
                continue
            for vdev in klass:
                for dev in vdev:
                    devs.append(dev)
        return devs

    def get_disks(self):
        """
        Get disks used within this pool
        """
        disks = []
        for key in ('data', 'cache', 'spares', 'logs'):
            if getattr(self, key):
                disks.extend(getattr(self, key).get_disks())
        return disks

    def validate(self):
        """
        Validate the current tree
        by calling specialized methods
        """
        for key in ('data', 'cache', 'spares', 'logs'):
            if getattr(self, key):
                getattr(self, key).validate()

    def dump(self):
        data = []
        for key in ('data', 'cache', 'spares', 'logs'):
            if getattr(self, key):
                data.append(
                    getattr(self, key).dump()
                )
        return data

    def __repr__(self):
        return repr({
            'data': self.data,
            'cache': self.cache,
            'spare': self.spares,
            'logs': self.logs,
        })


class Tnode(object):
    """
    Abstract class for Root, Vdev and Dev
    """
    name = None
    children = None
    parent = None
    type = None
    status = None

    def __init__(self, name, doc, **kwargs):
        self._doc = doc
        self.name = name
        self.children = []
        self.status = kwargs.pop('status', None)
        self.read = kwargs.pop('read', 0)
        self.write = kwargs.pop('write', 0)
        self.cksum = kwargs.pop('cksum', 0)

    def find_by_name(self, name):
        """
        Find children by a given name
        """
        for child in self.children:
            if child.name == name:
                return child
        return None

    def find_not_online(self):
        """
        Find nodes of status UNAVAIL
        """
        if len(self.children) == 0 and self.status not in ('ONLINE', 'AVAIL'):
            return [self]
        unavails = []
        for child in self.children:
            unavails.extend(child.find_not_online())
        return unavails

    def append(self, tnode):
        """
        Each specialized class should implement this method
        to append children
        """
        raise NotImplementedError

    @staticmethod
    def pprint(node, level=0):
        """
        Print the tree similar to zpool status
        """
        print '   ' * level + node.name
        for child in node.children:
            node.pprint(child, level + 1)

    def __iter__(self):
        for child in list(self.children):
            yield child

    def validate(self):
        """
        Each specialized method must validate its own instance
        """
        raise NotImplementedError

    def dump(self):
        """
        Each specialized method must dump its own instance
        """
        raise NotImplementedError


class Root(Tnode):
    """
    A Root represents data, cache, spares or logs
    Each Root may contain several Vdevs
    """

    def __repr__(self):
        return "<Root: %s>" % self.name

    def append(self, node):
        """
        Append a Vdev
        """
        if not isinstance(node, Vdev):
            raise Exception("Not a vdev: %s" % node)
        self.children.append(node)
        node.parent = self

    def dump(self):
        vdevs = []
        for vdev in self:
            vdevs.append(vdev.dump())
        return {
            'name': self.name,
            'vdevs': vdevs,
            'numVdevs': len(vdevs),
            'status': self.status if self.status else '',
        }

    def get_disks(self):
        """
        Get disks used within this root
        """
        disks = []
        for vdev in self:
            for disk in vdev:
                if disk.disk:
                    disks.append(disk.disk)
        return disks

    def validate(self):
        for vdev in self:
            vdev.validate()


class Vdev(Tnode):
    """
    A Vdev represents a ZFS Virtual Device
    May contain several Devs
    """

    def __repr__(self):
        return "<Section: %s>" % self.name

    def append(self, node):
        """
        Append a Dev
        """
        if not isinstance(node, Dev):
            raise Exception("Not a device: %s" % node)
        self.children.append(node)
        node.parent = self

    def dump(self):
        disks = []
        for dev in self:
            disks.append(dev.dump())
        return {
            'name': self.name,
            'disks': disks,
            'type': self.type,
            'numDisks': len(disks),
            'status': self.status,
        }

    def validate(self):
        """
        Validate the current Vdev and children (Devs)
        """
        for dev in self:
            dev.validate()
        if len(self.children) == 0:
            stripe = self.parent.find_by_name("stripe")
            if not stripe:
                stripe = Tnode("stripe", self._doc)
                stripe.type = 'stripe'
                self.parent.append(stripe)
            self.parent.children.remove(self)
            stripe.append(self)
            #stripe.validate(level)
        else:
            self.type = _vdev_type(self.name)


class Dev(Tnode):
    """
    Dev is the leaf in the tree
    """

    disk = None
    devname = None
    path = None

    def __init__(self, *args, **kwargs):
        self.replacing = kwargs.pop('replacing', False)
        super(Dev, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<Dev: %s>" % self.name

    def dump(self):
        return {
            'name': self.devname,
            'status': self.status,
        }

    def validate(self):
        # The parent of a leaf should be a vdev
        if not _is_vdev(self.parent.name) and self.parent.parent is not None:
            raise Exception(
                "Oh noes! This damn thing should be a vdev! %s" % self.parent
            )

        name = self.name
        search = self._doc.xpathEval("//class[name = 'ELI']"
                                     "//provider[name = '%s']/../consumer"
                                     "/provider/@ref" % name)
        if len(search) > 0:
            search = self._doc.xpathEval("//provider[@id = '%s']"
                                         "/name" % search[0].content)
            name = search[0].content

        search = self._doc.xpathEval("//class[name = 'LABEL']"
                                     "//provider[name = '%s']/../consumer"
                                     "/provider/@ref" % name)

        provider = None
        if len(search) > 0:
            self.devname = search[0].xpathEval("../../../name")[0].content
            provider = search[0].content
        else:

            # Treat .nop as a regular dev (w/o .nop)
            if self.name.endswith(".nop"):
                self.devname = self.name[:-4]
            else:
                self.devname = self.name
            search = self._doc.xpathEval("//class[name = 'DEV']"
                                         "/geom[name = '%s']"
                                         "//provider/@ref" % self.devname)
            if len(search) > 0:
                provider = search[0].content
            elif self.status == 'ONLINE':
                log.warn("It should be a valid device: %s", self.name)
                self.disk = self.name
            elif self.name.isdigit():
                # Lets check whether it is a guid
                p1 = subprocess.Popen(
                    ["/usr/sbin/zdb", "-C", self.parent.parent.name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
                zdb = p1.communicate()[0]
                if p1.returncode == 0:
                    reg = re.search(
                        r'\bguid[:=]\s?%s.*?path[:=]\s?\'(?P<path>.*?)\'$' % (
                            self.name,
                        ),
                        zdb, re.M | re.S)
                    if reg:
                        self.path = reg.group("path")

        if provider:
            search = self._doc.xpathEval("//provider[@id = '%s']"
                                         "/../name" % provider)
            self.disk = search[0].content


class ZFSList(SortedDict):

    pools = None

    def __init__(self, *args, **kwargs):
        self.pools = {}
        super(ZFSList, self).__init__(*args, **kwargs)

    def append(self, new):
        if new.pool in self.pools:
            self.pools.get(new.pool).append(new)
        else:
            self.pools[new.pool] = [new]
        self[new.name] = new

    def __getitem__(self, item):
        if isinstance(item, slice):
            zlist = []
            for datasets in self.pools.values():
                zlist.extend(datasets)
            return zlist.__getitem__(item)
        else:
            return super(ZFSList, self).__getitem__(item)

    def __delitem__(self, item):
        self.pools[item.pool].remove(item)
        super(ZFSList, self).__delitem__(item)


class ZFSDataset(object):

    name = None
    path = None
    pool = None
    used = None
    avail = None
    refer = None
    mountpoint = None
    parent = None
    children = None

    def __init__(self, path=None, used=None, avail=None, refer=None, mountpoint=None):
        self.path = path
        if path:
            if '/' in path:
                self.pool, self.name = path.split('/', 1)
            else:
                self.pool = ''
                self.name = path
        self.used = used
        self.avail = avail
        self.refer = refer
        self.mountpoint = mountpoint
        self.parent = None
        self.children = []

    def __repr__(self):
        return "<Dataset: %s>" % self.path

    @property
    def full_name(self):
        if self.pool:
            return "%s/%s" % (self.pool, self.name)
        return self.name

    def append(self, child):
        child.parent = self
        self.children.append(child)

    #TODO copied from MountPoint
    #Move this to a common place
    def _get__vfs(self):
        if not hasattr(self, '__vfs'):
            try:
                self.__vfs = os.statvfs(self.mountpoint)
            except:
                self.__vfs = None
        return self.__vfs

    def _get_total_si(self):
        try:
            totalbytes = self._vfs.f_blocks * self._vfs.f_frsize
            return u"%s" % (humanize_size(totalbytes))
        except:
            return _(u"Error getting total space")

    def _get_avail_si(self):
        try:
            availbytes = self._vfs.f_bavail * self._vfs.f_frsize
            return u"%s" % (humanize_size(availbytes))
        except:
            return _(u"Error getting available space")

    def _get_used_bytes(self):
        try:
            return (self._vfs.f_blocks - self._vfs.f_bfree) * \
                self._vfs.f_frsize
        except:
            return 0

    def _get_used_si(self):
        try:
            usedbytes = self._get_used_bytes()
            return u"%s" % (humanize_size(usedbytes))
        except:
            return _(u"Error getting used space")

    def _get_used_pct(self):
        try:
            availpct = 100 * (
                self._vfs.f_blocks - self._vfs.f_bavail
            ) / self._vfs.f_blocks
            return u"%d%%" % (availpct)
        except:
            return _(u"Error")

    _vfs = property(_get__vfs)
    total_si = property(_get_total_si)
    avail_si = property(_get_avail_si)
    used_pct = property(_get_used_pct)
    used_si = property(_get_used_si)


class Snapshot(object):

    name = None
    filesystem = None
    used = None
    refer = None
    mostrecent = False
    parent_type = None

    def __init__(
        self,
        name,
        filesystem,
        used,
        refer,
        mostrecent=False,
        parent_type=None
    ):
        self.name = name
        self.filesystem = filesystem
        self.used = used
        self.refer = refer
        self.mostrecent = mostrecent
        self.parent_type = parent_type

    def __repr__(self):
        return u"<Snapshot: %s>" % self.fullname

    @property
    def fullname(self):
        return "%s@%s" % (self.filesystem, self.name)

    @property
    def used_bytes(self):
        return zfs_size_to_bytes(self.used)

    @property
    def refer_bytes(self):
        return zfs_size_to_bytes(self.refer)


def parse_status(name, doc, data):

    scrub = re.search(r'scrub: (.+)$', data, re.M)
    if scrub:
        scrub = scrub.group(1)
        if scrub.find('in progress') != -1:
            scrub = 'IN_PROGRESS'
        elif scrub.find('completed') != -1:
            scrub = 'COMPLETED'
        else:
            scrub = 'UNKNOWN'
    else:
        scrub = None

    status = data.split('config:')[1]
    pid = re.search(r'id: (?P<id>\d+)', data)
    if pid:
        pid = pid.group("id")
    else:
        pid = None
    pool = Pool(pid=pid, name=name, scrub=scrub)
    lastident = None
    pnode = None
    for line in status.split('\n'):
        if not line.startswith('\t'):
            continue

        try:
            spaces, word, status, read, write, cksum = re.search(
                r'''^(?P<spaces>[ ]*)  # Group spaces to know identation
                    (?P<word>\S+)\s+
                    (?P<status>\S+)\s+
                    (?P<read>\S+)\s+(?P<write>\S+)\s+(?P<cksum>\S+)''',
                line[1:],
                re.X
            ).groups()
        except Exception:
            spaces, word = re.search(
                r'^(?P<spaces>[ ]*)(?P<word>\S+)',
                line[1:]
            ).groups()
            status = None
            read, write, cksum = 0, 0, 0
        ident = len(spaces) / 2
        if ident < 2 and ident < lastident:
            for x in range(lastident - ident):
                pnode = pnode.parent

        if ident == 0:
            if word != 'NAME':
                tree = Root(
                    word,
                    doc,
                    read=read,
                    write=write,
                    cksum=cksum,
                )
                tree.status = status
                pnode = tree
                pool.add_root(tree)

        elif ident == 1:
            if _is_vdev(word):
                node = Vdev(
                    word,
                    doc,
                    status=status,
                    read=read,
                    write=write,
                    cksum=cksum,
                )
                tree.append(node)
                pnode = node
            else:
                if lastident != ident:
                    node = Vdev(
                        "stripe",
                        doc,
                        read=read,
                        write=write,
                        cksum=cksum,
                    )
                    node.status = status
                    pnode.append(node)
                else:
                    node = pnode
                    pnode = node.parent

                node2 = Dev(
                    word,
                    doc,
                    status=status,
                    read=read,
                    write=write,
                    cksum=cksum,
                )
                node.append(node2)
                pnode = node
        elif ident >= 2:
            if not word.startswith('replacing'):
                if ident == 3:
                    replacing = True
                else:
                    replacing = False
                node = Dev(
                    word,
                    doc,
                    status=status,
                    replacing=replacing,
                    read=read,
                    write=write,
                    cksum=cksum,
                )
                pnode.append(node)
            ident = 2

        lastident = ident
    pool.validate()
    return pool


def list_datasets(path="", recursive=False, hierarchical=False,
                  include_root=False):
    """
    Return a dictionary that contains all ZFS dataset list and their
    mountpoints
    """
    args = [
        "/sbin/zfs",
        "list",
        "-H",
        "-t",
        "filesystem"
    ]
    if recursive:
        args.insert(3, "-r")
    if path:
        args.append(path)

    zfsproc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    zfs_output, zfs_err = zfsproc.communicate()
    zfs_output = zfs_output.split('\n')
    zfslist = ZFSList()
    last_dataset = None
    last_depth = 2
    for line in zfs_output:
        if not line:
            continue
        data = line.split('\t')
        depth = len(data[0].split('/'))
        # root filesystem is not treated as dataset by us
        if depth == 1 and not include_root:
            continue
        dataset = ZFSDataset(
            path=data[0],
            used=data[1],
            avail=data[2],
            refer=data[3],
            mountpoint=data[4],
        )
        if not hierarchical:
            zfslist.append(dataset)
            continue

        if depth == last_depth + 1:
            last_dataset.append(dataset)
        elif depth == 2:
            zfslist.append(dataset)
        elif depth > 2 and last_depth >= depth:
            tmp = last_dataset
            for i in range(last_depth - depth + 1):
                tmp = tmp.parent
            tmp.append(dataset)
        else:
            log.error("Failed to parse zfs list in hierarchical mode")
        last_dataset = dataset
        last_depth = depth

    return zfslist
