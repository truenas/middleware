import glob
import logging
import os
import re
import subprocess
from collections import OrderedDict

from middlewared.schema import Dict, Int, Str, accepts
from middlewared.service import CallError, CRUDService, filterable, private
from middlewared.service_exception import MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list

logger = logging.getLogger(__name__)

ENCLOSURE_ACTIONS = {
    'clear': '0x80 0x00 0x00 0x00',
    'identify': '0x80 0x00 0x02 0x00',
    'fault': '0x80 0x00 0x00 0x20',
}

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

M_SERIES_REGEX = re.compile(r"(ECStream|iX) 4024S([ps])")
R_SERIES_REGEX = re.compile(r"ECStream (FS2|DSS212S[ps])")
R20A_REGEX = re.compile(r"SMC SC826-P")
R50_REGEX = re.compile(r"iX eDrawer4048S([12])")
X_SERIES_REGEX = re.compile(r"CELESTIC (P3215-O|P3217-B)")
ES24_REGEX = re.compile(r"(ECStream|iX) 4024J")
ES24F_REGEX = re.compile(r"(ECStream|iX) 2024J([ps])")


class EnclosureLabelModel(sa.Model):
    __tablename__ = 'truenas_enclosurelabel'

    id = sa.Column(sa.Integer(), primary_key=True)
    encid = sa.Column(sa.String(200), unique=True)
    label = sa.Column(sa.String(200))


class EnclosureService(CRUDService):

    class Config:
        cli_namespace = 'storage.enclosure'

    @filterable
    def query(self, filters, options):
        enclosures = []
        for enc in self.__get_enclosures():
            enclosure = {
                "id": enc.encid,
                "name": enc.name,
                "model": enc.model,
                "controller": enc.controller,
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
                        "value": elem.value,
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
                        "descriptor": enc.descriptors.get(name, ""),
                        "header": header,
                        "elements": elements,
                        "has_slot_status": has_slot_status
                    })

            enclosures.append(enclosure)

        enclosures.extend(self.middleware.call_sync("enclosure.m50_plx_enclosures"))
        enclosures.extend(self.middleware.call_sync("enclosure.r50_nvme_enclosures"))

        enclosures = self.middleware.call_sync("enclosure.concatenate_enclosures", enclosures)

        enclosures = self.middleware.call_sync("enclosure.map_enclosures", enclosures)

        for number, enclosure in enumerate(enclosures):
            enclosure["number"] = number

        labels = {
            label["encid"]: label["label"]
            for label in self.middleware.call_sync("datastore.query", "truenas.enclosurelabel")
        }
        for enclosure in enclosures:
            enclosure["label"] = labels.get(enclosure["id"]) or enclosure["name"]

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

    def _get_slot(self, slot_filter, enclosure_query=None):
        for enclosure in self.middleware.call_sync("enclosure.query", enclosure_query or []):
            try:
                elements = next(filter(lambda element: element["name"] == "Array Device Slot",
                                       enclosure["elements"]))["elements"]
                slot = next(filter(slot_filter, elements))
                return enclosure, slot
            except StopIteration:
                pass

        raise MatchNotFound()

    def _get_slot_for_disk(self, disk):
        return self._get_slot(lambda element: element["data"]["Device"] == disk)

    def _get_ses_slot(self, enclosure, element):
        if "original" in element:
            enclosure_id = element["original"]["enclosure_id"]
            slot = element["original"]["slot"]
        else:
            enclosure_id = enclosure["id"]
            slot = element["slot"]

        ses_enclosures = self.__get_enclosures()
        ses_enclosure = ses_enclosures.get_by_encid(enclosure_id)
        if ses_enclosure is None:
            raise MatchNotFound()
        ses_slot = ses_enclosure.get_by_slot(slot)
        if ses_slot is None:
            raise MatchNotFound()
        return ses_slot

    def _get_ses_slot_for_disk(self, disk):
        # This can also return SES slot for disk that is not present in the system
        try:
            enclosure, element = self._get_slot_for_disk(disk)
        except MatchNotFound:
            disk = self.middleware.call_sync(
                "disk.query",
                [["devname", "=", disk]],
                {"get": True, "extra": {"include_expired": True}, "order_by": ["expiretime"]},
            )
            if disk["enclosure"]:
                enclosure, element = self._get_slot(lambda element: element["slot"] == disk["enclosure"]["slot"],
                                                    [["number", "=", disk["enclosure"]["number"]]])
            else:
                raise MatchNotFound()

        return self._get_ses_slot(enclosure, element)

    @accepts(Str("enclosure_id"), Int("slot"), Str("status", enum=["CLEAR", "FAULT", "IDENTIFY"]))
    def set_slot_status(self, enclosure_id, slot, status):
        enclosure, element = self._get_slot(lambda element: element["slot"] == slot, [["id", "=", enclosure_id]])
        ses_slot = self._get_ses_slot(enclosure, element)
        if not ses_slot.device_slot_set(status.lower()):
            raise CallError("Error setting slot status")

    @private
    def sync_disk(self, id):
        disk = self.middleware.call_sync(
            'disk.query',
            [['identifier', '=', id]],
            {'get': True, "extra": {'include_expired': True}}
        )

        try:
            enclosure, element = self._get_slot_for_disk(disk["name"])
        except MatchNotFound:
            disk_enclosure = None
        else:
            disk_enclosure = {
                "number": enclosure["number"],
                "slot": element["slot"],
            }

        if disk_enclosure != disk['enclosure']:
            self.middleware.call_sync('disk.update', id, {'enclosure': disk_enclosure})

    @private
    @accepts(Str("pool", null=True, default=None))
    def sync_zpool(self, pool):
        """
        Sync enclosure of a given ZFS pool
        """

        # As we are only interfacing with SES we can skip mapping enclosures or working with non-SES enclosures

        encs = self.__get_enclosures()
        if len(list(encs)) == 0:
            self.logger.debug("Enclosure not found, skipping enclosure sync")
            return None

        if pool is None:
            pools = [pool["name"] for pool in self.middleware.call_sync("pool.query")]
        else:
            pools = [pool]

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

                label = dev["path"].replace("/dev/", "")
                seen_devs.append(label)

                disk = label2disk.get(label)
                if disk is None:
                    continue

                try:
                    element = self._get_ses_slot_for_disk(disk)
                except MatchNotFound:
                    pass
                else:
                    element.device_slot_set("fault")

            # We want spares to only identify slot for Z-series
            # See #32706
            if self.middleware.call_sync("truenas.get_chassis_hardware").startswith("TRUENAS-Z"):
                spare_value = "identify"
            else:
                spare_value = "clear"

            for node in pool["groups"]["spare"]:
                for vdev in node["children"]:
                    for dev in vdev["children"]:
                        if dev["path"] is None:
                            continue

                        label = dev["path"].replace("/dev/", "")
                        disk = label2disk.get(label)

                        if disk is None:
                            continue

                        if dev["status"] != "AVAIL":
                            continue

                        seen_devs.append(dev["path"])

                        element = encs.find_device_slot(disk)
                        if element:
                            self.logger.debug(f"{spare_value}ing bay slot for %r", disk)
                            element.device_slot_set(spare_value)

            """
            Go through all devs in the pool
            Make sure the enclosure status is clear for everything else
            """
            for label, disk in label2disk.items():
                if label in seen_devs:
                    continue

                seen_devs.append(label)

                try:
                    element = self._get_ses_slot_for_disk(disk)
                except MatchNotFound:
                    pass
                else:
                    element.device_slot_set("clear")

        disks = []
        for label in seen_devs:
            disk = label2disk.get(label)
            if disk is None:
                continue

            if disk.startswith("multipath/"):
                try:
                    disks.append(self.middleware.call_sync(
                        "disk.query",
                        [["devname", "=", disk]],
                        {"get": True, "extra": {"include_expired": True}, "order_by": ["expiretime"]},
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
        return Enclosures(
            self.middleware.call_sync("enclosure.get_ses_enclosures"),
            self.middleware.call_sync("system.dmidecode_info")["system-product-name"]
        )


class Enclosures(object):

    def __init__(self, stat, product_name):
        blacklist = [
            "VirtualSES",
        ]
        if product_name:
            if (
                product_name.startswith("TRUENAS-") and
                "-MINI-" not in product_name and
                product_name not in ["TRUENAS-R20", "TRUENAS-R20A"]
            ):
                blacklist.append("AHCI SGPIO Enclosure 2.00")

        self.__enclosures = []
        enclosures_tail = []
        for num, data in stat.items():
            enclosure = Enclosure(num, data, stat, product_name)
            if any(s in enclosure.encname for s in blacklist):
                continue
            if (
                product_name and product_name in ["TRUENAS-R20", "TRUENAS-R20A"] and
                enclosure.encname == "AHCI SGPIO Enclosure 2.00"
            ):
                if enclosure.model.endswith("Drawer #2"):
                    enclosures_tail.append(enclosure)

                continue

            self.__enclosures.append(enclosure)

        self.__enclosures.extend(enclosures_tail)

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
        raise AssertionError(f"Enclosure slot not found for {devname}")

    def get_by_id(self, _id):
        for e in self:
            if e.num == _id:
                return e

    def get_by_encid(self, _id):
        for e in self:
            if e.encid == _id:
                return e


class Enclosure(object):

    def __init__(self, num, data, stat, product_name):
        self.num = num
        self.stat = stat
        self.product_name = product_name
        self.devname, data = data
        self.encname = ""
        self.encid = ""
        self.model = ""
        self.controller = False
        self.status = "OK"
        self.__elements = []
        self.__elementsbyname = {}
        self.descriptors = {}
        self._parse(data)

    def _parse(self, data):
        cf, es = data

        self.encname = re.sub(r"\s+", " ", cf.splitlines()[0].strip())

        if m := re.search(r"\s+enclosure logical identifier \(hex\): ([0-9a-f]+)", cf):
            self.encid = m.group(1)

        self._set_model(cf)

        self.status = "OK"

        element_type = None
        element_number = None
        for line in es.splitlines():
            if m := re.match(r"\s+Element type: (.+), subenclosure", line):
                element_type = m.group(1)

                if element_type != "Audible alarm":
                    element_type = " ".join([
                        word[0].upper() + word[1:]
                        for word in element_type.split()
                    ])
                if element_type == "Temperature Sensor":
                    element_type = "Temperature Sensors"

                element_number = None
            elif m := re.match(r"\s+Element ([0-9]+) descriptor:", line):
                element_number = int(m.group(1))
            elif m := re.match(r"\s+([0-9a-f ]{11})", line):
                if element_type is not None and element_number is not None:
                    dev = ""
                    if element_type == "Array Device Slot":
                        dev = self._array_device_slot_dev(element_number)

                    element = self._enclosure_element(
                        element_number,
                        element_type,
                        self._parse_raw_value(m.group(1)),
                        None,
                        "",
                        dev,
                    )
                    if element is not None:
                        self.append(element)

                element_number = None
            else:
                element_number = None

    def _array_device_slot_dev(self, element_number):
        try:
            return os.listdir(f"/sys/class/enclosure/{self.devname}/Disk #{element_number:02X}/device/block")[0]
        except (FileNotFoundError, IndexError):
            pass

        if slot := glob.glob(f"/sys/class/enclosure/{self.devname[len('bsg/'):]}/slot{element_number:02} *"):
            try:
                return os.listdir(f"{slot[0]}/device/block")[0]
            except (FileNotFoundError, IndexError):
                pass

        return ""

    def _set_model(self, data):
        if M_SERIES_REGEX.match(self.encname):
            self.model = "M Series"
            self.controller = True
        elif R_SERIES_REGEX.match(self.encname) or R20A_REGEX.match(self.encname):
            self.model = self.product_name.replace("TRUENAS-", "")
            self.controller = True
            if self.model in ["R20", "R20A"]:
                self.model = f"{self.model}, Drawer #1"
            if self.model == "R40":
                index = [v for v in self.stat.values() if "ECStream FS2" in v].index(data)
                self.model = f"{self.model}, Drawer #{index + 1}"
        elif (
            self.product_name in ["TRUENAS-R20", "TRUENAS-R20A"] and
            self.encname == "AHCI SGPIO Enclosure 2.00" and
            len(data.splitlines()) == 6
        ):
            self.model = f"{self.product_name.replace('TRUENAS-', '')}, Drawer #2"
            self.controller = True
        elif m := R50_REGEX.match(self.encname):
            self.model = f"R50, Drawer #{m.group(1)}"
            self.controller = True
        elif X_SERIES_REGEX.match(self.encname):
            self.model = "X Series"
            self.controller = True
        elif self.encname.startswith("iX TrueNAS R20p"):
            self.model = "R20"
        elif self.encname.startswith("QUANTA JB9 SIM"):
            self.model = "E60"
        elif self.encname.startswith("Storage 1729"):
            self.model = "E24"
        elif self.encname.startswith("ECStream 3U16+4R-4X6G.3"):
            if "SD_9GV12P1J_12R6K4" in data:
                self.model = "Z Series"
                self.controller = True
            else:
                self.model = "E16"
        elif self.encname.startswith("ECStream 3U16RJ-AC.r3"):
            self.model = "E16"
        elif self.encname.startswith("HGST H4102-J"):
            self.model = "ES102"
        elif self.encname.startswith("CELESTIC R0904"):
            self.model = "ES60"
        elif ES24_REGEX.match(self.encname):
            self.model = "ES24"
        elif ES24F_REGEX.match(self.encname):
            self.model = "ES24F"
        elif self.encname.startswith("CELESTIC X2012"):
            self.model = "ES12"

    def _parse_raw_value(self, value):
        newvalue = 0
        for i, v in enumerate(value.split(' ')):
            v = int(v.replace("0x", ""), 16)
            newvalue |= v << (2 * (3 - i)) * 4
        return newvalue

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
            if self.model.startswith('R50, ') and slot >= 25:
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
        return f'<Enclosure: {self.name}>'

    def __iter__(self):
        for e in list(self.__elements):
            yield e

    @property
    def name(self):
        return self.encname

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
        except Exception:
            self.descriptor = 'Unknown'
        self.enclosure = None

    def __repr__(self):
        return f'<Element: {self.name}>'

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
        return self.value_raw & 0xffff

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
        output.append("%sA" % ((self.value_raw & 0xffff) / 100))

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
            output.append(f"Power cycle {self.pctime} min, power off for {self.potime} min")

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
        output.append("%sV" % ((self.value_raw & 0xffff) / 100))

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
        return "%s RPM" % (((self.value_raw & 0x7ff00) >> 8) * 10)


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
        if status == "clear":
            commands = ["--clear=fault", "--clear=ident"]
        else:
            if status == "identify":
                commands = ["--set=ident"]
            else:
                commands = [f"--set={status}"]

        ok = True
        for cmd in commands:
            cmd = ["sg_ses", "--index", str(self.slot), cmd, f"/dev/{self.enclosure.devname}"]
            p = subprocess.run(cmd, encoding="utf-8", errors="ignore", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if p.returncode != 0:
                logger.warning("%r failed: %s", cmd, p.stderr)
                ok = False

        return ok

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


async def devd_zfs_hook(middleware, data):
    if data.get('type') in (
        'ATTACH',
        'DETACH',
        'resource.fs.zfs.removed',
        'misc.fs.zfs.config_sync',
        'misc.fs.zfs.vdev_remove',
    ):
        await middleware.call('enclosure.sync_zpool')


async def zfs_events_hook(middleware, data):
    event_id = data['class']

    if event_id in [
        'sysevent.fs.zfs.config_sync',
        'sysevent.fs.zfs.vdev_remove',
    ]:
        await middleware.call('enclosure.sync_zpool')


async def udev_block_devices_hook(middleware, data):
    if data.get('SUBSYSTEM') != 'block' or data.get('DEVTYPE') != 'disk' or data['SYS_NAME'].startswith((
        'sr', 'md', 'dm-', 'loop'
    )):
        return

    if data['ACTION'] in ['add', 'remove']:
        await middleware.call('enclosure.sync_zpool')


async def pool_post_delete(middleware, id):
    await middleware.call('enclosure.sync_zpool')


def setup(middleware):
    middleware.register_hook('zfs.pool.events', zfs_events_hook)
    middleware.register_hook('udev.block', udev_block_devices_hook)
    middleware.register_hook('pool.post_delete', pool_post_delete)
