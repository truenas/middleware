from pyudev import Context

from libsg3.ses import EnclosureDevice
from middlewared.service import private, Service


class EnclosureService(Service):

    @private
    def list_ses_enclosures(self):
        ctx = Context()
        return [f'/dev/bsg/{i.sys_name}' for i in ctx.list_devices(subsystem='enclosure')]

    @private
    def get_ses_enclosures(self):
        output = {}
        for i, name in enumerate(self.list_ses_enclosures()):
            dev = EnclosureDevice(name)
            try:
                cf = dev.get_configuration()
            except OSError:
                self.logger.warning('Error querying configuration page for %r', name, exc_info=True)
                continue

            try:
                es = dev.get_enclosure_status()
            except OSError:
                self.logger.warning('Error querying enclosure status page for %r', name, exc_info=True)
                continue

            output[i] = (name.removeprefix('/dev/'), (cf, es))

        return output
