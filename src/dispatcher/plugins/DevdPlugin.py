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
import netifaces
from balancer import QueueClass
from event import EventSource
from task import Provider
from dispatcher.rpc import schema, description
from gevent import socket
from lib import geom
from lib.freebsd import get_sysctl
from lxml import etree

class DeviceInfoPlugin(Provider):
    def initialize(self, context):
        # Enumerate disks and create initial disk queues
        for disk in self.__get_class_disk():
            context.dispatcher.balancer.create_queue(QueueClass.DISK, disk["name"])

    def get_classes(self):
        return [
            "disk",
            "network",
            "cpu"
        ]

    @schema({
        'title': 'dev_class',
        'type': 'string'
    })
    def get_devices(self, dev_class):
        method = "__get_class_{0}".format(dev_class)
        if hasattr(self, method):
            return getattr(self, method)

        return None

    def __get_class_disk(self):
        disk = None
        result = []
        confxml = geom.confxml()

        for child in confxml.findall("class"):
            if child.find("name").text == "DISK":
                disk = child

        if disk is None:
            return []

        for child in disk.findall("geom"):
            device = child.find("name").text
            mediasize = int(child.find("provider/mediasize").text)
            descr = child.find("provider/config/descr").text
            result.append({
                "name": device,
                "mediasize" : mediasize,
                "description": descr
            })

        return result

    def __get_class_network(self):
        result = []
        for i in netifaces.interfaces():
            node = get_sysctl(re.sub('(\w+)([0-9]+)', '\\1.\\2', i))
            result.append({
                'name': i,
                'description': node['%desc'],
                'pnpinfo': node['%pnpinfo']
            })

        return result

    def __get_class_cpu(self):
        pass


class DevdEventSource(EventSource):
    def __init__(self, dispatcher):
        super(DevdEventSource, self).__init__(dispatcher)
        self.register_event_type("system.device.attached")
        self.register_event_type("system.device.detached")
        self.register_event_type("system.device.changed")
        self.register_event_type("system.network.interface.attached")
        self.register_event_type("system.network.interface.detached")
        self.register_event_type("system.network.interface.link_up")
        self.register_event_type("system.network.interface.link_down")
        self.register_event_type("fs.zfs.scrub.start")
        self.register_event_type("fs.zfs.scrub.finish")

    def __tokenize(self, line):
        return {i.split("=")[0]: i.split("=")[1] for i in line.split()}

    def __process_devfs(self, args):
        if args["subsystem"] == "CDEV":
            params = {
                "name": args["cdev"],
                "path": os.path.join("/dev", args["cdev"])
            }

            if args["type"] == "CREATE":
                params["description"] = "Device {0} attached".format(args["cdev"])
                self.emit_event("system.device.attached", **params)

            if args["type"] == "DESTROY":
                params["description"] = "Device {0} detached".format(args["cdev"])
                self.emit_event("system.device.detached", **params)

    def __process_ifnet(self, args):
        params = {
            "interface": args["subsystem"]
        }

    def __process_zfs(self, args):
        event_mapping = {
            "misc.fs.zfs.scrub_start": ("fs.zfs.scrub.start", "Scrub on volume {0} started"),
            "misc.fs.zfs.scrub_finish": ("fs.zfs.scrub.finish", "Scrub on volume {0} finished")
        }

        params = {
            "pool": args["pool_name"],
            "guid": args["pool_guid"],
            "description": event_mapping[args["type"]][1].format(args["pool_name"])
        }

        self.emit_event(event_mapping[args["type"]][0], **params)

    def run(self):
        self.socket = socket.socket(family=socket.AF_UNIX)
        self.socket.connect("/var/run/devd.pipe")

        f = self.socket.makefile("r", 0)
        while True:
            line = f.readline()
            if line is None:
                # Connection closed - we need to reconnect
                pass

            args = self.__tokenize(line[1:].strip())
            if ("system", "subsystem") not in args:
                # WTF
                pass

            if args["system"] == "DEVFS":
                self.__process_devfs(args)

            if args["system"] == "IFNET":
                self.__process_ifnet(args)

            if args["system"] == "ZFS":
                self.__process_zfs(args)


def _compatible():
    return ["FreeBSD:*"]

def _init(dispatcher):
    dispatcher.register_provider("system.device", DeviceInfoPlugin)
    dispatcher.register_event_source("system.device", DevdEventSource)