from middlewared.schema import Dict, Int, Str, accepts
from middlewared.service import CallError, CRUDService, filterable, private
from middlewared.service_exception import MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list
from bsd.enclosure import Enclosure as ENC
from .enclosure_.enclosure_class import Enclosure
from .enclosure_.regex import RE


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
            enclosures.extend(self.middleware.call_sync('enclosure.mseries_plx_enclosures', prod))
        elif prod == 'TRUENAS-R50':
            enclosures.extend(self.middleware.call_sync('enclosure.rseries_nvme_enclosures', prod))

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
        Str('enclosure_id'),
        Int('slot'),
        Str('status', enum=['CLEAR', 'FAULT', 'IDENTIFY']),
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

        for disk in await self.middleware.call('disk.query', [], {'extra': {'include_expired': True}}):
            try:
                encnum, slot = await self.get_enclosure_number_and_slot_for_disk(disk['name'], enclosure_info)
            except MatchNotFound:
                disk_enclosure = None
            else:
                disk_enclosure = {'number': encnum, 'slot': slot}

            if disk_enclosure != disk['enclosure']:
                await self.middleware.call('disk.update', disk['identifier'], {'enclosure': disk_enclosure})

    @private
    async def get_enclosure_number_and_slot_for_disk(self, disk, enclosure_info=None):
        if enclosure_info is None:
            enclosure_info = await self.middleware.call('enclosure.query')

        for enc in enclosure_info:
            for slot, info in enc['elements']['Array Device Slot'].items():
                if info['dev'] == disk:
                    return enc['number'], slot

        raise MatchNotFound()

    @private
    async def sync_disk(self, id):
        filters = [['identifier', '=', id]]
        options = {'extra': {'include_expired': True}}
        for disk in await self.middleware.call('disk.query', filters, options):
            try:
                encnum, slot = await self.get_enclosure_number_and_slot_for_disk(disk['name'])
            except MatchNotFound:
                disk_enclosure = None
            else:
                disk_enclosure = {'number': encnum, 'slot': slot}

            if disk_enclosure != disk['enclosure']:
                await self.middleware.call('disk.update', id, {'enclosure': disk_enclosure})

    @private
    @accepts(Str("pool", null=True, default=None))
    async def sync_zpool(self, pool):
        encs = await self.middleware.call('enclosure.query')
        if not encs:
            self.logger.debug('Skipping enclosure slot to zpool sync because no enclosures found')
            return

        batch_operations = {i['number']: {'clear': set(), 'identify': set()} for i in encs}
        for enc in encs:
            for disk_slot, disk_info in enc['elements']['Array Device Slot'].items():
                if disk_info['status'] != 'Unsupported' and disk_info['value'] != 'None':
                    # only clear the disk slots status that need it
                    batch_operations[enc['number']]['clear'].add(disk_slot)

        if (await self.middleware.call('truenas.get_chassis_hardware')).startswith('TRUENAS-Z'):
            # we only turn on the "IDENTIFY" light on the zseries hardware and only on
            # hot-spares in a zpool. We do not do this for other hardware platforms because
            # the "IDENTIFY" light color is red. Customers see red and think something is wrong
            pools = []
            try:
                pool = await self.middleware.call(
                    'zfs.pool.query',
                    [['name', '=', pool]] if pool else [['name', 'nin', ['freenas-boot', 'boot-pool']]],
                    {'get': True} if pool else {},
                )
                pools.append(pool) if isinstance(pool, dict) else pools.extend(pool)
            except IndexError:
                # means a specific pool was given to us and it wasn't
                # detected on the system
                pools = []

            if pools:
                label2disk = {}
                cache = await self.middleware.call('disk.label_to_dev_disk_cache')
                for label, part in cache['label_to_dev'].items():
                    disk = cache['dev_to_disk'].get(part)
                    if disk:
                        """
                        final dict looks like
                        {
                            'gptid/2aa24f29-6e92-4501-b178-1d2e28097451': 'da50',
                            'gptid/6532d307-9aba-4599-8751-d2565926f485': 'da51',
                            ...
                        }
                        """
                        if disk.startswith('multipath/'):
                            try:
                                disk = await self.middleware.call(
                                    'disk.query',
                                    [['devname', '=', disk]],
                                    {'get': True, 'extra': {'include_expired': True, 'order_by': ['expiretime']}},
                                )['name']
                            except IndexError:
                                continue

                        label2disk.update({label: disk})

                for pool in pools:
                    spare_devs = (await self.middleware.call('zfs.pool.find_not_online', pool['id']))['groups']['spare']
                    for spare_dev in spare_devs:
                        if spare_dev['status'] != 'AVAIL':
                            # when a hot-spare gets automatically attached to a zpool
                            # its status is reported as "UNAVAIL"
                            continue

                        path = spare_dev['path']
                        if not path:
                            continue

                        label = path[5:]
                        if not label:
                            continue

                        disk = label2disk.get(label)
                        if not disk:
                            continue

                        # getting here means we've found disks that are hot-spares in zpool(s)
                        encnum, slot = await self.get_enclosure_number_and_slot_for_disk(disk)

                        # now we need to make sure we mark this slot to be "IDENTIFYed"
                        batch_operations[encnum]['clear'].discard(slot)
                        batch_operations[encnum]['identify'].add(slot)

        # finally we can set the disk slots
        await self.middleware.run_in_thread(self.__bulk_disk_slot_op, batch_operations)

    def __bulk_disk_slot_op(self, batch_operations):
        for enc, action in batch_operations.items():
            enc = ENC(f'/dev/ses{enc}')
            for slot_to_be_cleared in action['clear']:
                enc.clear(slot_to_be_cleared)
            for slot_to_be_identified in action['identify']:
                enc.identify(slot_to_be_identified)

    def __get_enclosures(self, product):
        blacklist = ['VirtualSES']
        if product.startswith('TRUENAS-'):
            if '-MINI-' not in product and product not in RE.R20_VARIANTS.value:
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
