import pathlib

from pyudev import Context

from libsg3.ses import EnclosureDevice
from middlewared.service import Service, filterable
from middlewared.utils import filter_list
from .enclosure_class import Enclosure
from .map2 import map_enclosures


class Enclosure2Service(Service):

    class Config:
        cli_namespace = 'storage.enclosure2'
        private = True

    def get_ses_enclosures(self):
        """This generates the "raw" list of enclosures detected on the system. It
        serves as the "entry" point to "enclosure2.query" and is foundational in
        how all of the structuring of the final data object is returned.

        We use pyudev to enumerate enclosure type devices using a socket to the
        udev database. While we're at it, we also add some useful keys to the
        object (/dev/bsg, /dev/sg, and dmi). Then we use SCSI commands (issued
        directly to the enclosure) to generate an object of all elements and the
        information associated to each element.

        It's _VERY_ important to understand that the "dmi" key is the hingepoint for
        identifying what platform we're on. This is SMBIOS data and is burned into
        the motherboard before we ship to our customers. This is also how we map the
        enclosure's array device slots (disk drives) to a human friendly format.

        The `Enclosure` class is where all the magic happens wrt to taking in all the
        raw data and formatting it into a structured object that will be consumed by
        the webUI team as well as on the backend (alerts, drive identifiction, etc).
        """
        output = list()
        dmi = self.middleware.call_sync('system.dmidecode_info')['system-product-name']
        for i in Context().list_devices(subsystem='enclosure'):
            bsg = f'/dev/bsg/{i.sys_name}'
            try:
                enc_status = EnclosureDevice(bsg).status()
            except OSError:
                self.logger.error('Error querying enclosure status for %r', bsg)
                continue

            sg = next(pathlib.Path(f'/sys/class/enclosure/{i.sys_name}/device/scsi_generic').iterdir())
            output.append(Enclosure(bsg, f'/dev/{sg.name}', dmi, enc_status).asdict())

        return output

    def to_ignore(self, enclosure):
        """On our MINI and R20 platforms, we actually use the Virtual AHCI
        enclosure devices since those platforms don't have another enclosure
        wired up interally for which the drives are attached. This function
        checks to make sure that we skip the Virtual AHCI enclosures on all
        platforms with the exception of MINIs and R20 variants.
        """
        return all((
            enclosure['product'] == 'SGPIOEnclosure',
            '-MINI-' not in enclosure['model'],
            not enclosure['model'].startswith('R20'),
        ))

    @filterable
    def query(self, filters, options):
        enclosures = []
        if self.middleware.call_sync('truenas.get_chassis_hardware') == 'TRUENAS-UNKNOWN':
            # this feature is only available on hardware that ix sells
            return enclosures

        labels = {
            label["encid"]: label["label"]
            for label in self.middleware.call_sync("datastore.query", "truenas.enclosurelabel")
        }
        for i in filter(lambda x: not self.to_ignore(x), self.get_ses_enclosures()):
            # this is a user-provided string to label the enclosures so we'll add it at as a
            # top-level dictionary key "label", if the user hasn't provided a label then we'll
            # fill in the info with whatever is in the "name" key. The "name" key is the
            # t10 vendor, product and revision information combined as a single space separated
            # string reported by the enclosure itself via a standard inquiry command
            i['label'] = labels.get(i['id']) or i['name']
            enclosures.append(i)

        # TODO: fix nvme mapping
        # enclosures.extend(self.middleware.call_sync("enclosure.map_nvme"))
        enclosures = map_enclosures(enclosures)
        return filter_list(enclosures, filters, options)
