from middlewared.schema import Dict, Int, Str, accepts
from middlewared.service import CallError, CRUDService, filterable, private
from middlewared.service_exception import MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list
from .enclosure_.enclosure_class import Enclosure


class EnclosureLabelModel(sa.Model):
    __tablename__ = 'truenas_enclosurelabel'

    id = sa.Column(sa.Integer(), primary_key=True)
    encid = sa.Column(sa.String(200))
    label = sa.Column(sa.String(200))


class EnclosureService(CRUDService):

    @filterable
    def query(self, filters, options):
        dmi = self.middleware.call_sync('system.dmidecode_info')
        prod = dmi['system-product-name']
        prod_vers = dmi['system-version']

        enclosures = []
        for enc in self.__get_enclosures(prod):
            enclosure = {
                'id': enc.encid,
                'number': enc.num,
                'name': enc.encname,
                'model': enc.model,
                'controller': enc.controller,
                'elements': enc.elements,
            }
            # Ensure R50's first expander is first in
            # the list independent of how it was cabled
            if 'eDrawer4048S1' in enclosure['name']:
                enclosures.insert(0, enclosure)
            else:
                enclosures.append(enclosure)

        if prod in ('TRUENAS-M50', 'TRUENAS-M60'):
            enclosures.extend(self.middleware.call_sync('enclosure.mseries_plx_enclosures'))
        elif prod == 'TRUENAS-R50':
            enclosures.extend(self.middleware.call_sync('enclosure.rseries_nvme_enclosures'))

        enclosures = self.middleware.call_sync('enclosure.map_enclosures', enclosures, prod, prod_vers)

        labels = {
            label['encid']: label['label']
            for label in self.middleware.call_sync('datastore.query', 'truenas.enclosurelabel')
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

    async def _build_slot_for_disks_dict(self):
        enclosure_info = await self.middleware.call('enclosure.query')

        results = {}
        for enc in enclosure_info:
            slots = next(filter(lambda x: x["name"] == "Array Device Slot", enc["elements"]))["elements"]
            results.update({
                enc["number"] * 1000 + j["slot"]: j["data"]["Device"] or None for j in slots
            })

        return results

    def _get_slot(self, slot_filter, enclosure_query=None, enclosure_info=None):
        if enclosure_info is None:
            enclosure_info = self.middleware.call_sync("enclosure.query", enclosure_query or [])

        for enclosure in enclosure_info:
            try:
                elements = next(filter(lambda element: element["name"] == "Array Device Slot",
                                       enclosure["elements"]))["elements"]
                slot = next(filter(slot_filter, elements))
                return enclosure, slot
            except StopIteration:
                pass

        raise MatchNotFound()

    def _get_slot_for_disk(self, disk, enclosure_info=None):
        return self._get_slot(lambda element: element["data"]["Device"] == disk, enclosure_info=enclosure_info)

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
    async def sync_disks(self):
        curr_slot_info = await self._build_slot_for_disks_dict()
        for db_entry in await self.middleware.call('datastore.query', 'storage.disk'):
            for curr_slot, curr_disk in curr_slot_info.items():
                if db_entry['disk_name'] == curr_disk and db_entry['disk_enclosure_slot'] != curr_slot:
                    await self.middleware.call(
                        'datastore.update', 'storage.disk',
                        db_entry['disk_identifier'],
                        {'disk_enclosure_slot': curr_slot},
                    )

    @private
    def sync_disk(self, id, enclosure_info=None):
        disk = self.middleware.call_sync(
            'disk.query',
            [['identifier', '=', id]],
            {'get': True, "extra": {'include_expired': True}}
        )

        try:
            enclosure, element = self._get_slot_for_disk(disk["name"], enclosure_info)
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
        cache = self.middleware.call_sync("disk.label_to_dev_disk_cache")
        hardware = self.middleware.call_sync("truenas.get_chassis_hardware")
        for pool in pools:
            try:
                pool = self.middleware.call_sync("zfs.pool.query", [["name", "=", pool]], {"get": True})
            except IndexError:
                continue

            label2disk.update({
                label: self.middleware.call_sync("disk.label_to_disk", label, False, cache)
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

            if hardware.startswith("TRUENAS-Z"):
                # We want spares to have identify set on the enclosure slot for
                # Z-series systems only see #32706 for details. Gist is that
                # the other hardware platforms "identify" light is red which
                # causes customer confusion because they see red and think
                # something is wrong.
                spare_value = "identify"
            else:
                spare_value = "clear"

            for node in pool["groups"]["spare"]:
                if node["path"] is None:
                    continue

                label = node["path"].replace("/dev/", "")
                disk = label2disk.get(label)
                if disk is None:
                    continue

                if node["status"] != "AVAIL":
                    # when a hot-spare gets automatically attached to a zpool
                    # its status is reported as "UNAVAIL"
                    continue

                seen_devs.append(node["path"])

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
                    element = encs.find_device_slot(disk)
                    if element:
                        element.device_slot_set("clear")
                except AssertionError:
                    # happens for pmem devices since those
                    # are NVDIMM sticks internal to each
                    # controller
                    continue

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

    def __get_enclosures(self, product):
        blacklist = ['VirtualSES']
        if product.startswith('TRUENAS-'):
            if '-MINI-' not in product and product not in ('TRUENAS-R20', 'TRUENAS-R20A'):
                blacklist.append('AHCI SGPIO Enclosure 2.00')

        result = []
        for idx, enc in self.middleware.call_sync('enclosure.get_ses_enclosures').items():
            if enc['name'] in blacklist:
                continue
            else:
                result.append(Enclosure(idx, enc, product))
        return result


async def devd_zfs_hook(middleware, data):
    events = (
        'ATTACH',
        'DETACH',
        'resource.fs.zfs.removed',
        'misc.fs.zfs.config_sync',
        'misc.fs.zfs.vdev_remove',
    )
    if data.get('type') in events:
        await middleware.call('enclosure.sync_zpool')


async def pool_post_delete(middleware, id):
    await middleware.call('enclosure.sync_zpool')


def setup(middleware):
    middleware.register_hook('devd.zfs', devd_zfs_hook)
    middleware.register_hook('pool.post_delete', pool_post_delete)
