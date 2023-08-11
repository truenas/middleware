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
            i['label'] = labels.get(i['id']) or i['name']
            enclosures.append(i)

        # TODO: fix nvme mapping
        # enclosures.extend(self.middleware.call_sync("enclosure.map_nvme"))
        enclosures = map_enclosures(enclosures)
        return filter_list(enclosures, filters, options)
