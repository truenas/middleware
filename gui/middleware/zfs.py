#!/usr/bin/env python
#-
# Copyright (c) 2010 iXsystems, Inc.
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

class Tnode(object):
    name = None
    leaf = False
    children = None
    parent = None
    type = None
    status = None

    def __init__(self, name, doc):
        self._doc = doc
        self.name = name
        self.children = []

    def find_by_name(self, name):
        for c in self.children:
            if c.name == name:
                return c
        return None

    def find_unavail(self, node):
        if len(self.children) == 0:
            if self.status == 'UNAVAIL':
                return self
        else:
            unavails = []
            for c in self.children:
                find = self.find_unavail(c)
                if find:
                    unavails.append(find)
            return unavails

    def append(self, tnode):
        self.children.append(tnode)
        tnode.parent = self

    @staticmethod
    def pprint(node, level=0):
        print '   ' * level + node.name
        for c in node.children:
            node.pprint(c, level+1)

    def __repr__(self):
        if not self.parent:
            return "<Section: %s>" % self.name
        return "<Node: %s>" % self.name

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
        for c in self:
            c.validate(level+1)
        if level == 1:
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
        elif level == 2:
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
                else:
                    raise Exception("It should be a valid device: %s" % self.name)
    def dump(self, level=0):
        if level == 2:
            return self.devname
        if level == 1:
            disks = []
            for c in self:
                disks.append(c.dump(level+1))
            return {'disks': disks, 'type': self.type}
        if level == 0:
            self.validate()
            vdevs = []
            for c in self:
                vdevs.append(c.dump(level+1))
            return {'name': self.name, 'vdevs': vdevs}

def parse_status(name, doc, data):

    status = data.split('config:')[1]
    roots = {'cache': None, 'logs': None, 'spares': None}
    lastident = None
    for line in status.split('\n'):
        if line.startswith('\t'):
            spaces, word, status = re.search(r'^(?P<spaces>[ ]*)(?P<word>\S+)\s+(?P<status>\S+)', line[1:]).groups()
            ident = len(spaces) / 2
            if ident == 0:
                if word == name:
                    tree = Tnode(word, doc)
                    tree.status = status
                    roots[word] = tree
                    pnode = tree
            elif ident == lastident + 1:
                node = Tnode(word, doc)
                node.status = status
                pnode.append(node)
                pnode = node
            elif ident == lastident:
                node = Tnode(word, doc)
                node.status = status
                pnode.parent.append(node)
            elif ident < lastident:
                node = Tnode(word, doc)
                node.status = status
                tree.append(node)
                pnode = node
            lastident = ident
    return roots
