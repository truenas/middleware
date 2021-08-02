from collections import defaultdict
from xml.etree import ElementTree as etree

from middlewared.schema import accepts, Dict, List, returns
from middlewared.service import private, Service

from .connection import LibvirtConnectionMixin


class VMService(Service, LibvirtConnectionMixin):

    CAPABILITIES = None

    @private
    def update_capabilities_cache(self):
        self._check_setup_connection()
        xml = etree.fromstring(self.LIBVIRT_CONNECTION.getCapabilities())
        supported_archs = defaultdict(list)
        for guest in xml.findall('guest'):
            arch = guest.find('arch')
            if not arch or not arch.get('name'):
                continue
            arch_name = arch.get('name')

            for machine_type in filter(lambda m: m.text, arch.findall('machine')):
                supported_archs[arch_name].append(machine_type.text)

        self.CAPABILITIES = supported_archs
