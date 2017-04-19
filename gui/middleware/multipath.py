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
        self.name = xmlnode.xpath("./name")[0].text
        self.devname = "multipath/%s" % self.name
        self._status = xmlnode.xpath("./config/State")[0].text
        self.consumers = []
        for consumer in xmlnode.xpath("./consumer"):
            status = consumer.xpath("./config/State")[0].text
            provref = consumer.xpath("./provider/@ref")[0]
            prov = doc.xpath("//provider[@id = '%s']" % provref)[0]
            self.consumers.append(Consumer(status, prov))

        self.__xml = xmlnode
        self.__doc = doc

    def __repr__(self):
        return "<Multipath:%s [%s]>" % (self.name, ",".join(self.devices))


class Consumer(object):

    def __init__(self, status, xmlnode):
        self.status = status
        self.devname = xmlnode.xpath("./name")[0].text
        try:
            self.lunid = xmlnode.xpath("./config/lunid")[0].text
        except:
            self.lunid = ''
        self.__xml = xmlnode
