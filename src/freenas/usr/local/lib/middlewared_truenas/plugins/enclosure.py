from collections import OrderedDict
from decimal import Decimal
import logging
import os
import re
import subprocess

from bsd import geom

from middlewared.schema import Bool, Dict, Int, Str, accepts
from middlewared.service import CallError, CRUDService, filterable, private
from middlewared.utils import filter_list

logger = logging.getLogger(__name__)


class EnclosureService(CRUDService):

    @filterable
    def query(self, filters, options):
        enclosures = []
        for enc in self.__get_enclosures():
            enclosure = {
                "id": enc.encid,
                "name": enc.name,
                "label": enc.label,
                "elements": [],
            }

            for name, elems in enc.iter_by_name().items():
                header = None
                elements = []
                has_slot_status = False

                for elem in elems:
                    header = list(elem.get_columns().keys())
                    element = {
                        "slot": elem.slot,
                        "data": dict(zip(elem.get_columns().keys(), elem.get_values())),
                        "name": elem.name,
                        "descriptor": elem.descriptor,
                        "status": elem.status,
                        "value_raw": hex(elem.value_raw),
                    }
                    if hasattr(elem, "device_slot_set"):
                        has_slot_status = True
                        element["fault"] = elem.fault
                        element["identify"] = elem.identify

                    elements.append(element)

                if header is not None and elements:
                    enclosure["elements"].append({
                        "name": name,
                        "header": header,
                        "elements": elements,
                        "has_slot_status": has_slot_status
                    })

            enclosures.append(enclosure)

        return filter_list(enclosures, filters=filters or [], options=options or {})

    @accepts(
        Str("id"),
        Dict(
            "enclosure_update",
            Str("label"),
            update=True,
        ),
    )
    async def do_update(self, id, data):
        if "label" in data:
            await self.middleware.call("datastore.delete", "truenas.enclosurelabel", [["encid", "=", id]])
            await self.middleware.call("datastore.insert", "truenas.enclosurelabel", {
                "encid": id,
                "label": data["label"]
            })

        return await self._get_instance(id)

    @accepts(Str("disk"))
    def find_disk_enclosure(self, disk):
        encs = self.__get_enclosures()
        elem = encs.find_device_slot(disk)
        return elem.enclosure.devname

    @accepts(Str("enclosure_id"), Int("slot"), Str("status", enum=["CLEAR", "FAULT", "IDENTIFY"]))
    def set_slot_status(self, enclosure_id, slot, status):
        encs = self.__get_enclosures()
        enc = encs.get_by_encid(enclosure_id)
        ele = enc.get_by_slot(slot)
        if not ele.device_slot_set(status.lower()):
            raise CallError()

    @private
    def sync_disk(self, id):
        disk = self.middleware.call_sync('disk.query', [['identifier', '=', id]], {'get': True})

        try:
            enclosures = self.__get_enclosures()
            element = enclosures.find_device_slot(disk['name'])
            enclosure_slot = element.enclosure.num * 1000 + element.slot
        except Exception:
            enclosure_slot = None

        if enclosure_slot != disk['enclosure_slot']:
            self.middleware.call_sync('disk.update', id, {'enclosure_slot': enclosure_slot})

    @private
    @accepts(Str("pool", null=True, default=None))
    def sync_zpool(self, pool):
        """
        Sync enclosure of a given ZFS pool
        """

        encs = self.__get_enclosures()
        if len(list(encs)) == 0:
            self.logger.debug("Enclosure not found, skipping enclosure sync")
            return None

        if pool is None:
            pools = [pool["name"] for pool in self.middleware.call_sync("pool.query")]
        else:
            pools = [pool]

        geom.scan()
        seen_devs = []
        label2disk = {}
        for pool in pools:
            try:
                pool = self.middleware.call_sync("zfs.pool.query", [["name", "=", pool]], {"get": True})
            except IndexError:
                continue

            label2disk.update({
                label: self.middleware.call_sync("disk.label_to_disk", label)
                for label in self.middleware.call_sync("zfs.pool.get_devices", pool["id"])
            })

            for dev in self.middleware.call_sync("zfs.pool.find_not_online", pool["id"]):
                if dev["path"] is None:
                    continue

                label = dev["path"].replace("/dev/")
                seen_devs.append(label)

                disk = label2disk.get(label)
                enc_slot = self.__get_enclosure_slot_from_disk(disk)
                if enc_slot:
                    enc = encs.get_by_id(enc_slot[0])
                    element = enc.get_by_slot(enc_slot[1])
                    if element:
                        element.device_slot_set("fault")

            for node in pool["groups"]["spare"]:
                for vdev in node["children"]:
                    for dev in vdev["children"]:
                        if dev["path"] is None:
                            continue

                        label = dev["path"].replace("/dev/")
                        disk = label2disk.get(label)

                        if disk is None:
                            continue

                        if dev["status"] != "AVAIL":
                            continue

                        seen_devs.append(dev["path"])

                        element = encs.find_device_slot(disk)
                        if element:
                            self.logger.debug("Identifying bay slot for %r", disk)
                            element.device_slot_set("identify")

            """
            Go through all devs in the pool
            Make sure the enclosure status is clear for everything else
            """
            for label, disk in label2disk.items():
                if label in seen_devs:
                    continue

                seen_devs.append(label)

                slot = self.__get_enclosure_slot_from_disk(disk)
                if not slot:
                    continue

                enc = encs.get_by_id(slot[0])
                element = enc.get_by_slot(slot[1])
                if element:
                    print("CLEAR %r %r" % (label, disk))
                    element.device_slot_set("clear")

        disks = []
        for label in seen_devs:
            disk = label2disk[label]
            if disk.startswith("multipath/"):
                try:
                    disks.append(self.middleware.call(
                        "disk.query", [["multipath_name", "=", label.replace("multipath/", "")]],
                        {"get": True, "order_by": ["expiretime"]}
                    )["name"])
                except IndexError:
                    pass
            else:
                disks.append(disk)

        """
        Clear all slots without an attached disk
        """
        for enc in encs:
            for element in enc.iter_by_name().get("Array Device Slot", []):
                if not element.devname or element.devname not in disks:
                    element.device_slot_set("clear")

    def __get_enclosures(self):
        return Enclosures(self.__get_enclosures_stat(), {
            label["encid"]: label["label"]
            for label in self.middleware.call_sync("datastore.query", "truenas.enclosurelabel")
        })

    def __get_enclosures_stat(self):
        """
        Call getencstat for all enclosures devices avaiable

        Returns:
            dict: all enclosures available with index as key
        """

        output = {}
        encnumb = 0
        while os.path.exists('/dev/ses%d' % (encnumb,)):
            out = self.__get_enclosure_stat(encnumb)
            if out:
                # In short, getencstat reserves the exit codes for
                # failing to change states and doesn't actually
                # error out if it can't read or poke at the enclosure
                # device.
                output[encnumb] = out
            encnumb += 1

        return output

    def __get_enclosure_stat(self, encnumb):
        """
        Call getencstat for single enclosures device
        """

        cmd = "/usr/sbin/getencstat -V /dev/ses%d" % (encnumb,)
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, close_fds=True)
        # getencstat may return not valid utf8 bytes (especially on Legacy TrueNAS)
        out = p1.communicate()[0].decode('utf8', 'ignore')
        return out

    def __get_enclosure_slot_from_disk(self, disk):
        enclosures = self.__get_enclosures()

        try:
            element = enclosures.find_device_slot(disk)
            return element.enclosure.num, element.slot
        except AssertionError:
            pass

        self.logger.debug("Disk %r not found in enclosure, trying from disk cache table", disk)

        if disk.startswith("multipath/"):
            f = [["multipath_name", "=", disk.replace("multipath/", "")]]
        else:
            f = [["name", "=", disk]]

        try:
            disk = self.middleware.call("disk.query", f, {"get": True, "order_by": ["expiretime"]})
            if disk["enclosure_slot"]:
                return divmod(disk["enclosure_slot"], 1000)
        except IndexError:
            pass


async def sync_zpool(middleware):
    await middleware.call("enclosure.sync_zpool")


def setup(middleware):
    middleware.register_hook("pool.post_delete", sync_zpool)


STATUS_DESC = [
    "Unsupported",
    "OK",
    "Critical",
    "Noncritical",
    "Unrecoverable",
    "Not installed",
    "Unknown",
    "Not available",
    "No access allowed",
    "reserved [9]",
    "reserved [10]",
    "reserved [11]",
    "reserved [12]",
    "reserved [13]",
    "reserved [14]",
    "reserved [15]",
]

ENCLOSURE_ACTIONS = {
    'clear': '0x80 0x00 0x00 0x00',
    'identify': '0x80 0x00 0x02 0x00',
    'fault': '0x80 0x00 0x00 0x20',
}


class Enclosures(object):

    def __init__(self, stat, labels):
        self.__enclosures = []
        for num, data in stat.items():
            self.__enclosures.append(Enclosure(num=num, data=data, labels=labels))

    def __iter__(self):
        for e in list(self.__enclosures):
            yield e

    def append(self, enc):
        if not isinstance(enc, Enclosure):
            raise ValueError("Not an enclosure")
        self.__enclosures.append(enc)

    def find_device_slot(self, devname):
        for enc in self:
            find = enc.find_device_slot(devname)
            if find is not None:
                return find
        raise AssertionError("Enclosure slot not found for %s" % devname)

    def get_by_id(self, _id):
        for e in self:
            if e.num == _id:
                return e

    def get_by_encid(self, _id):
        for e in self:
            if e.encid == _id:
                return e


class Enclosure(object):

    def __init__(self, num, data, labels):
        self.num = num
        self.devname = "ses%d" % num
        self.encname = ""
        self.encid = ""
        self.status = "OK"
        self.__elements = []
        self.__elementsbyname = {}
        self._parse(data)
        self.enclabel = labels.get(self.encid)

    def _parse(self, data):

        lname = ""
        status = re.search(
            r'Enclosure Name: (.+)',
            data)
        if status:
            self.encname = status.group(1)
        else:
            self.encname = self.devname
        status = re.search(
            r'Enclosure ID: (.+)',
            data)
        if status:
            self.encid = status.group(1)
        status = re.search(
            r'Enclosure Status <(.+)>',
            data)
        if status:
            self.status = status.group(1)
        elements = re.findall(
            r'Element\s+(?P<element>.+?): (?P<name>.+?)'
            ', status: (?P<status>.+?) \((?P<value>[^)]+)\)'
            '(?:, descriptor: \'(?P<desc>[^\']+)\')?'
            '(?:, dev: \'(?P<dev>.+?)\')?',
            data)
        for element in elements:
            slot, name, status, value, desc, dev = element
            if name != lname:
                lname = name
                continue
            newvalue = 0
            for i, v in enumerate(value.split(' ')):
                v = int(v.replace("0x", ""), 16)
                newvalue |= v << (2 * (3 - i)) * 4
            slot = int(slot, 16)
            if not desc:
                desc = "%s %d" % (name, slot)
            ele = self._enclosure_element(
                slot,
                name,
                newvalue,
                status,
                desc,
                dev)
            if ele is not None:
                self.append(ele)

    def iter_by_name(self):
        return OrderedDict(sorted(self.__elementsbyname.items()))

    def append(self, element):
        self.__elements.append(element)
        if element.name not in self.__elementsbyname:
            self.__elementsbyname[element.name] = [element]
        else:
            self.__elementsbyname[element.name].append(element)
        element.enclosure = self

    def _enclosure_element(self, slot, name, value, status, desc, dev):

        if name == "Audible alarm":
            return AlarmElm(slot=slot, value_raw=value, desc=desc)
        elif name == "Communication Port":
            return CommPort(slot=slot, value_raw=value, desc=desc)
        elif name == "Current Sensor":
            return CurrSensor(slot=slot, value_raw=value, desc=desc)
        elif name == "Enclosure":
            return EnclosureElm(slot=slot, value_raw=value, desc=desc)
        elif name == "Voltage Sensor":
            return VoltSensor(slot=slot, value_raw=value, desc=desc)
        elif name == "Cooling":
            return Cooling(slot=slot, value_raw=value, desc=desc)
        elif name == "Temperature Sensors":
            return TempSensor(slot=slot, value_raw=value, desc=desc)
        elif name == "Power Supply":
            return PowerSupply(slot=slot, value_raw=value, desc=desc)
        elif name == "Array Device Slot":
            # Echostream have actually only 16 physical disk slots
            # See #24254
            if self.encname.startswith('ECStream 3U16+4R-4X6G.3') and slot > 16:
                return
            return ArrayDevSlot(slot=slot, value_raw=value, desc=desc, dev=dev)
        elif name == "SAS Connector":
            return SASConnector(slot=slot, value_raw=value, desc=desc)
        elif name == "SAS Expander":
            return SASExpander(slot=slot, value_raw=value, desc=desc)
        else:
            return Element(slot=slot, name=name, value_raw=value, desc=desc)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return '<Enclosure: %s>' % self.name

    def __iter__(self):
        for e in list(self.__elements):
            yield e

    @property
    def name(self):
        return self.encname

    @property
    def label(self):
        return self.enclabel or self.name

    def find_device_slot(self, devname):
        """
        Get the element that the device name points to
        getencstat /dev/ses0 | grep da6
        Element 0x7: Array Device Slot, status: OK (0x01 0x00 0x00 0x00),
        descriptor: 'Slot 07', dev: 'da6,pass6'
        What we are interested in is the 0x7

        Returns:
            A tuple of the form (Enclosure-slot-number, element)

        Raises:
            AssertionError: enclosure slot not found
        """
        for e in self.__elementsbyname.get('Array Device Slot', []):
            if e.devname == devname:
                return e

    def get_by_slot(self, slot):
        for e in self:
            if e.slot == slot:
                return e


class Element(object):

    def __init__(self, **kwargs):
        if 'name' in kwargs:
            self.name = kwargs.pop('name')
        self.value_raw = kwargs.pop('value_raw')
        self.slot = kwargs.pop('slot')
        self.status_raw = (self.value_raw >> 24) & 0xf
        try:
            self.descriptor = kwargs.pop('desc')
        except:
            self.descriptor = 'Unknown'
        self.enclosure = None

    def __repr__(self):
        return '<Element: %s>' % self.name

    def get_columns(self):
        return OrderedDict([
            ('Descriptor', lambda y: y.descriptor),
            ('Status', lambda y: y.status),
            ('Value', lambda y: y.value),
        ])

    def get_values(self):
        for value in list(self.get_columns().values()):
            yield value(self)

    @property
    def value(self):
        return Decimal(self.value_raw & 0xffff)

    @property
    def status(self):
        return STATUS_DESC[self.status_raw]


class AlarmElm(Element):
    name = "Audible alarm"

    @property
    def identify(self):
        return (self.value_raw >> 16) & 0x80

    @property
    def fail(self):
        return (self.value_raw >> 16) & 0x40

    @property
    def rqmute(self):
        return self.value_raw & 0x80

    @property
    def muted(self):
        return self.value_raw & 0x40

    @property
    def remind(self):
        return self.value_raw & 0x10

    @property
    def info(self):
        return self.value_raw & 0x08

    @property
    def noncrit(self):
        return self.value_raw & 0x04

    @property
    def crit(self):
        return self.value_raw & 0x02

    @property
    def unrec(self):
        return self.value_raw & 0x01

    @property
    def value(self):
        output = []
        if self.identify:
            output.append("Identify on")

        if self.fail:
            output.append("Fail on")

        if self.rqmute:
            output.append("RQST mute")

        if self.muted:
            output.append("Muted")

        if self.remind:
            output.append("Remind")

        if self.info:
            output.append("INFO")

        if self.noncrit:
            output.append("NON-CRIT")

        if self.crit:
            output.append("CRIT")

        if self.unrec:
            output.append("UNRECOV")

        if not output:
            output.append("None")
        return ', '.join(output)


class CommPort(Element):
    name = "Communication Port"

    @property
    def identify(self):
        return (self.value_raw >> 16) & 0x80

    @property
    def fail(self):
        return (self.value_raw >> 16) & 0x40

    @property
    def disabled(self):
        return self.value_raw & 0x01

    @property
    def value(self):
        output = []
        if self.identify:
            output.append("Identify on")

        if self.fail:
            output.append("Fail on")

        if self.disabled:
            output.append("Disabled")

        if not output:
            output.append("None")
        return ', '.join(output)


class CurrSensor(Element):
    name = "Current Sensor"

    @property
    def identify(self):
        return (self.value_raw >> 16) & 0x80

    @property
    def fail(self):
        return (self.value_raw >> 16) & 0x40

    @property
    def warnover(self):
        return (self.value_raw >> 16) & 0x8

    @property
    def critover(self):
        return (self.value_raw >> 16) & 0x2

    @property
    def value(self):
        output = []
        output.append("%sA" % (Decimal(self.value_raw & 0xffff) / 100, ))

        if self.identify:
            output.append("Identify on")

        if self.fail:
            output.append("Fail on")

        if self.warnover:
            output.append("Warn over")

        if self.critover:
            output.append("Crit over")

        return ', '.join(output)


class EnclosureElm(Element):
    name = "Enclosure"

    @property
    def identify(self):
        return (self.value_raw >> 16) & 0x80

    @property
    def pctime(self):
        return (self.value_raw >> 10) & 0x3f

    @property
    def potime(self):
        return (self.value_raw >> 2) & 0x3f

    @property
    def failind(self):
        return (self.value_raw >> 8) & 0x02

    @property
    def warnind(self):
        return (self.value_raw >> 8) & 0x01

    @property
    def value(self):
        output = []
        if self.identify:
            output.append("Identify on")

        if self.failind:
            output.append("Fail on")

        if self.warnind:
            output.append("Warn on")

        if self.pctime:
            output.append("Power cycle %d min, power off for %d min" % (self.pctime, self.potime))

        if not output:
            output.append("None")
        return ', '.join(output)


class VoltSensor(Element):
    name = "Voltage Sensor"

    @property
    def identify(self):
        return (self.value_raw >> 16) & 0x80

    @property
    def fail(self):
        return (self.value_raw >> 16) & 0x40

    @property
    def warnover(self):
        return (self.value_raw >> 16) & 0x8

    @property
    def warnunder(self):
        return (self.value_raw >> 16) & 0x4

    @property
    def critover(self):
        return (self.value_raw >> 16) & 0x2

    @property
    def critunder(self):
        return (self.value_raw >> 16) & 0x1

    @property
    def value(self):
        output = []
        output.append("%sV" % (Decimal(self.value_raw & 0xffff) / 100, ))

        if self.identify:
            output.append("Identify on")

        if self.fail:
            output.append("Fail on")

        if self.warnover:
            output.append("Warn over")

        if self.warnunder:
            output.append("Warn under")

        if self.critover:
            output.append("Crit over")

        if self.critunder:
            output.append("Crit under")

        return ', '.join(output)


class Cooling(Element):
    name = "Cooling"

    @property
    def value(self):
        return "%s RPM" % (Decimal((self.value_raw & 0x7ff00) >> 8) * 10, )


class TempSensor(Element):
    name = "Temperature Sensor"

    @property
    def value(self):
        value = (self.value_raw & 0xff00) >> 8
        if not value:
            value = None
        else:
            # 8 bits represents -19 C to +235 C */
            # value of 0 (would imply -20 C) reserved */
            value -= 20
            value = "%dC" % value
        return value


class PowerSupply(Element):
    name = "Power Supply"

    @property
    def identify(self):
        return (self.value_raw >> 16) & 0x80

    @property
    def overvoltage(self):
        return (self.value_raw >> 8) & 0x8

    @property
    def undervoltage(self):
        return (self.value_raw >> 8) & 0x4

    @property
    def overcurrent(self):
        return (self.value_raw >> 8) & 0x2

    @property
    def fail(self):
        return self.value_raw & 0x40

    @property
    def off(self):
        return self.value_raw & 0x10

    @property
    def tempfail(self):
        return self.value_raw & 0x8

    @property
    def tempwarn(self):
        return self.value_raw & 0x4

    @property
    def acfail(self):
        return self.value_raw & 0x2

    @property
    def dcfail(self):
        return self.value_raw & 0x1

    @property
    def value(self):
        output = []
        if self.identify:
            output.append("Identify on")

        if self.fail:
            output.append("Fail on")

        if self.overvoltage:
            output.append("DC overvoltage")

        if self.undervoltage:
            output.append("DC undervoltage")

        if self.overcurrent:
            output.append("DC overcurrent")

        if self.tempfail:
            output.append("Overtemp fail")

        if self.tempwarn:
            output.append("Overtemp warn")

        if self.acfail:
            output.append("AC fail")

        if self.dcfail:
            output.append("DC fail")

        if not output:
            output.append("None")
        return ', '.join(output)


class ArrayDevSlot(Element):
    name = "Array Device Slot"

    def __init__(self, dev=None, **kwargs):
        super(ArrayDevSlot, self).__init__(**kwargs)
        dev = [y for y in dev.strip().split(',') if not y.startswith('pass')]
        if dev:
            self.devname = dev[0]
        else:
            self.devname = ''

    def get_columns(self):
        columns = super(ArrayDevSlot, self).get_columns()
        columns['Device'] = lambda y: y.devname
        return columns

    def device_slot_set(self, status):
        """
        Actually issue the command to set ``status'' in a given `slot''
        of the enclosure number ``encnumb''

        Returns:
            True if the command succeeded, False otherwise
        """

        proc = subprocess.Popen(
            ["/usr/bin/pgrep", "setobjstat"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf8',
        )
        pgrep = proc.communicate()[0]
        if proc.returncode == 0 and len(pgrep.strip('\n').split('\n')) > 10:
            # setobjstat already running, system may be stuck/hung
            logger.warn("multiple (10) setobjstat already running, skipping...")
            return True

        cmd = """/usr/sbin/setobjstat /dev/%s 0x%x %s""" % \
              (self.enclosure.devname, self.slot, ENCLOSURE_ACTIONS[status])
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            shell=True,
        )
        proc.communicate()
        return not bool(proc.returncode)

    @property
    def identify(self):
        if (self.value_raw >> 8) & 0x2:
            return True
        return False

    @property
    def fault(self):
        if self.value_raw & 0x20:
            return True
        return False

    @property
    def value(self):
        output = []
        if self.identify:
            output.append("Identify on")

        if self.fault:
            output.append("Fault on")

        if not output:
            output.append("None")
        return ', '.join(output)


class SASConnector(Element):
    name = "SAS Connector"

    @property
    def type(self):
        """
        Determine the type of the connector

        Based on sysutils/sg3-utils source code
        """
        conn_type = (self.value_raw >> 16) & 0x7f
        if conn_type == 0x0:
            return "No information"
        elif conn_type == 0x1:
            return "SAS 4x receptacle (SFF-8470) [max 4 phys]"
        elif conn_type == 0x2:
            return "Mini SAS 4x receptacle (SFF-8088) [max 4 phys]"
        elif conn_type == 0x3:
            return "QSFP+ receptacle (SFF-8436) [max 4 phys]"
        elif conn_type == 0x4:
            return "Mini SAS 4x active receptacle (SFF-8088) [max 4 phys]"
        elif conn_type == 0x5:
            return "Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]"
        elif conn_type == 0x6:
            return "Mini SAS HD 8x receptacle (SFF-8644) [max 8 phys]"
        elif conn_type == 0x7:
            return "Mini SAS HD 16x receptacle (SFF-8644) [max 16 phys]"
        elif conn_type == 0xf:
            return "Vendor specific external connector"
        elif conn_type == 0x10:
            return "SAS 4i plug (SFF-8484) [max 4 phys]"
        elif conn_type == 0x11:
            return "Mini SAS 4i receptacle (SFF-8087) [max 4 phys]"
        elif conn_type == 0x12:
            return "Mini SAS HD 4i receptacle (SFF-8643) [max 4 phys]"
        elif conn_type == 0x13:
            return "Mini SAS HD 8i receptacle (SFF-8643) [max 8 phys]"
        elif conn_type == 0x20:
            return "SAS Drive backplane receptacle (SFF-8482) [max 2 phys]"
        elif conn_type == 0x21:
            return "SATA host plug [max 1 phy]"
        elif conn_type == 0x22:
            return "SAS Drive plug (SFF-8482) [max 2 phys]"
        elif conn_type == 0x23:
            return "SATA device plug [max 1 phy]"
        elif conn_type == 0x24:
            return "Micro SAS receptacle [max 2 phys]"
        elif conn_type == 0x25:
            return "Micro SATA device plug [max 1 phy]"
        elif conn_type == 0x26:
            return "Micro SAS plug (SFF-8486) [max 2 phys]"
        elif conn_type == 0x27:
            return "Micro SAS/SATA plug (SFF-8486) [max 2 phys]"
        elif conn_type == 0x2f:
            return "SAS virtual connector [max 1 phy]"
        elif conn_type == 0x3f:
            return "Vendor specific internal connector"
        else:
            if conn_type < 0x10:
                return "unknown external connector type: 0x%x" % conn_type
            elif conn_type < 0x20:
                return "unknown internal wide connector type: 0x%x" % conn_type
            elif conn_type < 0x30:
                return (
                    "unknown internal connector to end device, type: 0x%x" % (
                        conn_type,
                    )
                )
            elif conn_type < 0x3f:
                return "reserved for internal connector, type:0x%x" % conn_type
            elif conn_type < 0x70:
                return "reserved connector type: 0x%x" % conn_type
            elif conn_type < 0x80:
                return "vendor specific connector type: 0x%x" % conn_type
            else:
                return "unexpected connector type: 0x%x" % conn_type

    @property
    def fail(self):
        if self.value_raw & 0x40:
            return True
        return False

    @property
    def value(self):
        output = [self.type]
        if self.fail:
            output.append("Fail on")
        return ', '.join(output)


class SASExpander(Element):
    name = "SAS Expander"

    @property
    def identify(self):
        return (self.value_raw >> 16) & 0x80

    @property
    def fail(self):
        return (self.value_raw >> 16) & 0x40

    @property
    def value(self):
        output = []
        if self.identify:
            output.append("Identify on")

        if self.fail:
            output.append("Fail on")

        if not output:
            output.append("None")
        return ', '.join(output)
