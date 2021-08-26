from middlewared.schema import Dict, Int, Str, accepts
from middlewared.service import CallError, CRUDService, filterable, private
from middlewared.service_exception import MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list
from bsd.enclosure import Enclosure as ENC
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

        labels = {
            label['encid']: label['label']
            for label in self.middleware.call_sync('datastore.query', 'truenas.enclosurelabel')
        }
        enclosures = []
        for enc in self.__get_enclosures(prod):
            enclosure = {
                'id': enc.encid,
                'number': enc.num,
                'name': enc.encname,
                'model': enc.model,
                'controller': enc.controller,
                'label': labels.get(enc.encid) or enc.encname,
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

        return filter_list(enclosures, filters, options)

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

    @accepts(
        Str("enclosure_id"),
        Int("slot"),
        Str("status", enum=["CLEAR", "FAULT", "IDENTIFY"])
    )
    def set_slot_status(self, enclosure_id, slot, status):
        """
        Set an enclosure's, with id of `enclosure_id`, disk array element `slot` to `status`.
        """
        try:
            info = self.middleware.call_sync('enclosure.query', [['id', '=', enclosure_id]])[0]
        except IndexError:
            # the enclosure given to us doesn't match anything connected to the system
            raise CallError(f'Enclosure with id: {enclosure_id} not found')

        # create enclosure object
        enc = ENC(f'/dev/ses{info["number"]}')

        # gotta make sure the slot number given to us exists on the enclosure
        if slot not in enc.status()['elements']:
            raise CallError(f'Enclosure with id: {enclosure_id} does not have slot: {slot}')

        # set the status of the enclosure slot
        if status == 'CLEAR':
            enc.clear(slot)
        elif status == 'FAULT':
            enc.fault(slot)
        elif status == 'IDENTIFY':
            enc.identify(slot)

    @private
    async def sync_disks(self, enclosure_info=None):
        if enclosure_info is None:
            enclosure_info = await self.middleware.call('enclosure.query')

        # build a manageable dict that has enclosure slot info
        # and the associated disk attached to that slot
        curr_slot_info = {}
        for enc in enclosure_info:
            for slot, slot_data in enc['elements']['Array Device Slot'].items():
                if slot_data['status'] != 'Unsupported' and slot_data['dev']:
                    curr_slot_info.update({
                        enc['number'] * 1000 + int(slot): slot_data['dev']
                    })

        # now build a manageable dict from the db with the same
        # information as the `curr_slot_info` dict
        db_info = {
            i['disk_enclosure_slot']: (i['disk_name'], i['disk_identifier'])
            for i in await self.middleware.call('datastore.query', 'storage.disk') if i['disk_enclosure_slot']
        }

        # now go through any disks that have changed slots and update the db
        for slot, disk in dict(curr_slot_info.items() - {k: v[0] for k, v in db_info.items()}.items()).items():
            await self.middleware.call(
                'datastore.update', 'storage.disk', db_info[slot][1], {'disk_enclosure_slot': slot}
            )

    async def _get_enclosure_number_and_slot_for_disk(self, disk):
        for enc in await self.middleware.call('enclosure.query'):
            for slot, info in enc['elements']['Array Device Slot'].items():
                if info['dev'] == disk:
                    return enc['number'], slot

        raise MatchNotFound()

    @private
    async def sync_disk(self, id):
        disk = await self.middleware.call(
            'disk.query', [['identifier', '=', id]], {'get': True, "extra": {'include_expired': True}}
        )
        if not disk:
            return

        try:
            encnum, slot = await self._get_enclosure_number_and_slot_for_disk(disk['name'])
        except MatchNotFound:
            disk_enclosure = None
        else:
            disk_enclosure = {"number": encnum, "slot": slot}

        if disk_enclosure != disk['enclosure']:
            await self.middleware.call('disk.update', id, {'enclosure': disk_enclosure})

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
