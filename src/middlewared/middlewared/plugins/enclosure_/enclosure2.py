# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions
import errno

from middlewared.api import api_method
from middlewared.api.current import Enclosure2Entry, Enclosure2SetSlotStatusArgs, Enclosure2SetSlotStatusResult
from middlewared.service import Service, filterable_api_method
from middlewared.service_exception import CallError, MatchNotFound, ValidationError
from middlewared.utils import filter_list

from .constants import SUPPORTS_IDENTIFY_KEY
from .enums import JbofModels
from .fseries_drive_identify import InsufficientPrivilege, set_slot_status as fseries_set_slot_status
from .jbof_enclosures import map_jbof, set_slot_status as _jbof_set_slot_status
from .map2 import combine_enclosures
from .nvme2 import map_nvme
from .r30_drive_identify import set_slot_status as r30_set_slot_status
from .r60_drive_identify import set_slot_status as r60_set_slot_status
from .ses_enclosures2 import get_ses_enclosures
from .sysfs_disks import toggle_enclosure_slot_identifier


class Enclosure2Service(Service):

    class Config:
        cli_namespace = 'storage.enclosure2'
        private = True

    def get_ses_enclosures(self):
        """This generates the "raw" list of enclosures detected on the system. It
        serves as the "entry" point to "enclosure2.query" and is foundational in
        how all of the structuring of the final data object is returned. We use
        SCSI commands (issued directly to the enclosure) to generate an object of
        all elements and the information associated to each element. The `Enclosure`
        class is where all the magic happens wrt to taking in all the raw data and
        formatting it into a structured object that will be consumed by the webUI
        team as well as on the backend (alerts, drive identifiction, etc).
        """
        return get_ses_enclosures()

    async def map_jbof(self, jbof_qry=None):
        """This method serves as an endpoint to easily be able to test
        the JBOF mapping logic specifically without having to call enclosure2.query
        which includes the head-unit and all other attached JBO{D/F}s.
        """
        if jbof_qry is None:
            jbof_qry = await self.middleware.call('jbof.query')
        return await map_jbof(jbof_qry)

    def map_nvme(self):
        """This method serves as an endpoint to easily be able to test
        the nvme mapping logic specifically without having to call enclosure2.query
        which includes the head-unit and all attached JBODs.
        """
        return map_nvme()

    def get_original_disk_slot(self, slot, enc_info):
        """Get the original slot based on the `slot` passed to us via the end-user.
        NOTE: Most drives original slot will match their "mapped" slot because there
        is no need to map them. We always include an "original" slot key for all
        enclosures as to keep this for loop as simple as possible and it also allows
        more flexbiility when we do get an enclosure that maps drives differently.
        (i.e. the ES102G2 is a prime example of this (enumerates drives at 1 instead of 0))
        """
        origslot, supports_identify = None, False
        for encslot, devinfo in filter(lambda x: x[0] == slot, enc_info['elements']['Array Device Slot'].items()):
            origslot = devinfo['original']['slot']
            supports_identify = devinfo[SUPPORTS_IDENTIFY_KEY]

        return origslot, supports_identify

    @api_method(Enclosure2SetSlotStatusArgs, Enclosure2SetSlotStatusResult, roles=['ENCLOSURE_WRITE'])
    def set_slot_status(self, data):
        """Set enclosure bay number `slot` to `status` for `enclosure_id`."""
        try:
            enc_info = self.middleware.call_sync(
                'enclosure2.query', [['id', '=', data['enclosure_id']]], {'get': True}
            )
        except MatchNotFound:
            raise ValidationError('enclosure2.set_slot_status', f'Enclosure with id: {data["enclosure_id"]} not found')

        if enc_info['id'].endswith('_nvme_enclosure'):
            if enc_info['id'].startswith('r30'):
                # an all nvme flash system so drive identification is handled
                # in a completely different way than sata/scsi
                return r30_set_slot_status(data['slot'], data['status'])
            elif enc_info['id'].startswith('r60'):
                # R60 nvme flash system with different LED control mechanism
                return r60_set_slot_status(data['slot'], data['status'])
            elif enc_info['id'].startswith(('f60', 'f100', 'f130')):
                try:
                    return fseries_set_slot_status(data['slot'], data['status'])
                except InsufficientPrivilege:
                    if self.middleware.call_sync('failover.licensed'):
                        opts = {'raise_connect_error': False}
                        return self.middleware.call_sync(
                            'failover.call_remote', 'enclosure2.set_slot_status', [data], opts
                        )
            else:
                # mseries, and some rseries have mapped nvme enclosures but they
                # don't support drive LED identification
                return
        elif enc_info['model'] == JbofModels.ES24N.name:
            return self.middleware.call_sync(
                'enclosure2.jbof_set_slot_status', data['enclosure_id'], data['slot'], data['status']
            )

        if enc_info['pci'] is None:
            raise ValidationError('enclosure2.set_slot_status', 'Unable to determine PCI address for enclosure')
        else:
            origslot, supported = self.get_original_disk_slot(data['slot'], enc_info)
            if origslot is None:
                raise ValidationError('enclosure2.set_slot_status', f'Slot {data["slot"]} not found in enclosure')
            elif not supported:
                raise ValidationError(
                    'enclosure2.set_slot_status', f'Slot {data["slot"]} does not support identification'
                )
            else:
                try:
                    toggle_enclosure_slot_identifier(
                        f'/sys/class/enclosure/{enc_info["pci"]}', origslot, data['status'], False, enc_info['model']
                    )
                except FileNotFoundError:
                    raise CallError(f'Slot: {data["slot"]!r} not found', errno.ENOENT)

    async def jbof_set_slot_status(self, ident, slot, status):
        return await _jbof_set_slot_status(ident, slot, status)

    @filterable_api_method(roles=['ENCLOSURE_READ'], item=Enclosure2Entry)
    def query(self, filters, options):
        enclosures = []
        if not self.middleware.call_sync('truenas.is_ix_hardware'):
            # this feature is only available on hardware that ix sells
            return enclosures

        labels = self.middleware.call_sync('enclosure.label.get_all')
        for i in self.get_ses_enclosures() + self.map_nvme() + self.middleware.call_sync('enclosure2.map_jbof'):
            if i.pop('should_ignore'):
                continue

            # this is a user-provided string to label the enclosures so we'll add it at as a
            # top-level dictionary key "label", if the user hasn't provided a label then we'll
            # fill in the info with whatever is in the "name" key. The "name" key is the
            # t10 vendor, product and revision information combined as a single space separated
            # string reported by the enclosure itself via a standard inquiry command
            i['label'] = labels.get(i['id']) or i['name']
            enclosures.append(i)

        combine_enclosures(enclosures)

        enclosures = sorted(enclosures, key=lambda enclosure: (0 if enclosure["controller"] else 1, enclosure['id']))

        return filter_list(enclosures, filters, options)
