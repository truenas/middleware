# -*- coding=utf8 -*-
import json
import subprocess

from middlewared.service import Service


class VrrpService(Service):

    class Config:
        private = True
        namespace_aliases = 'interfaces'

    def vrrp_config(self, ifname):

        # query db for configured settings
        info = self.middleware.call_sync(
            'datastore.query',
            'network.interfaces',
            [('int_interface', '=', ifname)],
        )
        configured_vips = [
            i['int_vip'] for i in info if i['int_vip']
        ]

        # if there are no VIPs then there is no reason to continue
        if not configured_vips:
            self.logger.warning(
                'No VIPs have been configured for %s.', ifname
            )
            return

        # get current addresses on `ifname` in json form
        data = subprocess.run(
            ['ip', '-j', 'addr', 'show', ifname],
            stdout=subprocess.PIPE,
        )
        if data.stdout:
            try:
                data = json.loads(data.stdout.decode())
            except Exception:
                self.logger.error(
                    'Unable to parse address information for %s.', ifname,
                    exc_info=True
                )
                return

        # now get the current IP addresses on the interface
        iface_addrs = [
            i['local'] for i in data[0]['addr_info'] if i['family'] == 'inet'
        ]

        addrs = []
        addr = {
            'address': None,
            'state': None,
        }
        # check if the configured VIP is on the interface
        for i in configured_vips:
            if i in iface_addrs:
                addr['address'] = i
                addr['state'] = 'MASTER'
            else:
                addr['state'] = 'BACKUP'

            addrs.append(addr)

        return addrs
