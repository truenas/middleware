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
import re

class Pool(object):
    id = None
    name = None

    data = None
    cache = None
    spare = None
    log = None

    def __init__(self, pid, name):
        self.id = pid
        self.name = name

    def __getitem__(self, name):
        if hasattr(self, name):
            return getattr(self, name)
        elif name == self.name:
            return self.data
        else:
            raise KeyError

    def add_root(self, root):
        setattr(self, root.name, root)

    def validate(self):
        for key in ('data', 'cache', 'spare', 'log', self.name):
            if getattr(self, key):
                getattr(self, key).validate()

    def __repr__(self):
        return repr({
            'data': self.data,
            'cache': self.cache,
            'spare': self.spare,
            'log': self.log,
        })

class Tnode(object):
    name = None
    children = None
    parent = None
    type = None
    status = None

    def __init__(self, name, doc, status=None):
        self._doc = doc
        self.name = name
        self.children = []
        self.status = status

    def find_by_name(self, name):
        for c in self.children:
            if c.name == name:
                return c
        return None

    def find_unavail(self):
        if len(self.children) == 0:
            if self.status != 'ONLINE':
                return self
        else:
            unavails = []
            for c in self.children:
                find = c.find_unavail()
                if find:
                    if isinstance(find, list):
                        unavails += find
                    else:
                        unavails.append(find)
            return unavails

    def append(self, tnode):
        raise NotImplementedError

    @staticmethod
    def pprint(node, level=0):
        print '   ' * level + node.name
        for c in node.children:
            node.pprint(c, level+1)

    def _is_vdev(self, name):
        if name in ('stripe', 'mirror', 'raidz', 'raidz1', 'raidz2', 'raidz3') \
            or re.search(r'^(mirror|raidz|raidz1|raidz2|raidz3)(-\d+)?$', name):
            return True
        return False

    def __iter__(self):
        for c in list(self.children):
            yield c

    def _vdev_type(self, name):
        # raidz needs to appear after other raidz types
        supported_types = ('stripe', 'mirror', 'raidz3', 'raidz2', 'raidz')
        for type in supported_types:
            if name.startswith(type):
                return type
        return False

    def validate(self, level=0):
        raise NotImplementedError

    def dump(self, level=0):
        raise NotImplementedError

class Root(Tnode):

    def append(self, node):
        if not isinstance(node, Vdev):
            raise Exception("Not a vdev: %s" % node)
        self.children.append(node)
        node.parent = self

    def dump(self):
        self.validate()
        vdevs = []
        for c in self:
            vdevs.append(c.dump())
        return {'name': self.name, 'vdevs': vdevs}

    def validate(self):
        for c in self:
            c.validate()

class Vdev(Tnode):

    def __repr__(self):
        return "<Section: %s>" % self.name

    def append(self, node):
        if not isinstance(node, Dev):
            raise Exception("Not a device: %s" % node)
        self.children.append(node)
        node.parent = self

    def dump(self):
        disks = []
        for c in self:
            disks.append(c.dump())
        return {'disks': disks, 'type': self.type}

    def validate(self):
        for c in self:
            c.validate()
        if len(self.children) == 0:
            stripe = self.parent.find_by_name("stripe")
            if not stripe:
                stripe = Tnode("stripe", self._doc)
                stripe.type = 'stripe'
                self.parent.append(stripe)
            self.parent.children.remove(self)
            stripe.append(self)
            stripe.validate(level)
        else:
            self.type = self._vdev_type(self.name)

class Dev(Tnode):

    def __repr__(self):
        return "<Node: %s>" % self.name

    def append(self, node):
        raise Exception("What? You can't append child to a Dev")

    def dump(self):
        return self.devname

    def validate(self):
        for c in self:
            c.validate()
        # The parent of a leaf should be a vdev
        if not self._is_vdev(self.parent.name) and \
            self.parent.parent is not None:
            raise Exception("Oh noes! This damn thing should be a vdev! %s" % self.parent)
        search = self._doc.xpathEval("//class[name = 'LABEL']//provider[name = '%s']/../name" % self.name)
        if len(search) > 0:
            self.devname = search[0].content
        else:
            search = self._doc.xpathEval("//class[name = 'DEV']/geom[name = '%s']" % self.name)
            if len(search) > 0:
                self.devname = self.name
            elif self.status == 'ONLINE':
                raise Exception("It should be a valid device: %s" % self.name)
            else:
                self.devname = self.name

def parse_status(name, doc, data):

    status = data.split('config:')[1]
    pid = re.search(r'id: (?P<id>\d+)', data)
    if pid:
        pid = pid.group("id")
    else:
        pid = None
    pool = Pool(pid=pid, name=name)
    lastident = None
    for line in status.split('\n'):
        if line.startswith('\t'):

            try:
                spaces, word, status = re.search(r'^(?P<spaces>[ ]*)(?P<word>\S+)\s+(?P<status>\S+)', line[1:]).groups()
            except:
                spaces, word = re.search(r'^(?P<spaces>[ ]*)(?P<word>\S+)', line[1:]).groups()
                status = None
            ident = len(spaces) / 2
            if ident < lastident:
                for x in range(lastident - ident):
                    pnode = pnode.parent

            if ident == 0:
                if word != 'NAME':
                    tree = Root(word, doc)
                    tree.status = status
                    pnode = tree
                    pool.add_root(tree)

            elif ident == 1:
                if pnode._is_vdev(word):
                    node = Vdev(word, doc, status=status)
                    pnode.append(node)
                    pnode = node
                else:
                    if lastident != ident:
                        node = Vdev("stripe", doc)
                        node.status = status
                        pnode.append(node)
                    else:
                        node = pnode
                        pnode = node.parent

                    node2 = Dev(word, doc, status=status)
                    node.append(node2)
                    pnode = node
            elif ident == 2:
                node = Dev(word, doc, status=status)
                pnode.append(node)

            lastident = ident
    pool.validate()
    return pool
