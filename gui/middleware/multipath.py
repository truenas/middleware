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

class Multipath(object):
    """
    Class representing a GEOM_MULTIPATH
    """

    @property
    def status(self):
        return getattr(self, '_status', 'Unknown')

    @status.setter
    def status(self, value):
        self._status = value

    @property
    def devices(self):
        devs = []
        for consumer in self.consumers:
            devs.append(consumer.devname)
        return devs

    def __init__(self, doc, xmlnode):
        self.name = xmlnode.xpathEval("./name")[0].content
        self.devname = "multipath/%s" % self.name
        self.status =  xmlnode.xpathEval("./config/State")[0].content
        self.consumers = []
        for consumer in xmlnode.xpathEval("./consumer"):
            status = consumer.xpathEval("./config/State")[0].content
            provref = consumer.xpathEval("./provider/@ref")[0].content
            prov = doc.xpathEval("//provider[@id = '%s']" % provref)[0]
            self.consumers.append(Consumer(status, prov))

        self.__xml = xmlnode
        self.__doc = doc

    def __repr__(self):
        return "<Multipath:%s [%s]>" % (self.name, ",".join(self.devices))

class Consumer(object):

    def __init__(self, status, xmlnode):
        self.status = status
        self.devname = xmlnode.xpathEval("./name")[0].content
        self.__xml = xmlnode
