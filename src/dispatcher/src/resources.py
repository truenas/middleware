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


import networkx as nx
from threading import Lock


class Resource(object):
    def __init__(self, name):
        self.name = name
        self.busy = False


class ResourceGraph(object):
    def __init__(self):
        self.mutex = Lock()
        self.root = Resource('root')
        self.resources = nx.DiGraph()
        self.resources.add_node(self.root)

    def lock(self):
        self.mutex.acquire()

    def unlock(self):
        self.mutex.release()

    def add_resource(self, resource, parents=None):
        self.resources.add_node(resource)
        if not parents:
            parents = ['root']

        for p in parents:
            node = self.get_resource(p)
            self.resources.add_edge(node, resource)

    def remove_resource(self, resource):
        pass

    def get_resource(self, name):
        for i in self.resources.nodes():
            if i.name == name:
                return i

        return None

    def acquire(self, name):
        res = self.get_resource(name)
        for i in nx.ancestors(self.resources, res):
            if i.busy:
                raise Exception('Cannot acquire')

        res.busy = True

    def can_acquire_all(self, names):
        for i in names:
            if not self.can_acquire(i):
                return False

        return True

    def can_acquire(self, name):
        res = self.get_resource(name)

        if res.busy:
            return False

        for i in nx.ancestors(self.resources, res):
            if i.busy:
                return False

        return True

    def release(self, name):
        res = self.get_resource(name)
        res.busy = False