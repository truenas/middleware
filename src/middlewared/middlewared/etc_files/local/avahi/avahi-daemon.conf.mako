# avahi is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# avahi is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
# License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with avahi; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA.
# See avahi-daemon.conf(5).
<%
    hamode = middleware.call_sync('smb.get_smb_ha_mode')
    hostname_override = None

    if hamode == 'CLUSTERED':
        ipv4_enabled = False
        ipv6_enabled = False
        pnn = middleware.call_sync('ctdb.general.pnn')
        recmaster = middleware.call_sync('ctdb.general.recovery_master')
        if pnn != recmaster:
            raise FileShouldNotExist()

        hostname_override = middleware.call_sync('smb.getparm', 'netbios name', 'GLOBAL')
        allow_interfaces = []
        deny_interfaces = []
        ips = middleware.call_sync('ctdb.general.ips')
        for ip in ips:
            interface_added = False
            if ip['pnn'] != pnn:
                continue

            for i in ip['interfaces']:
                if i['active']:
                    allow_interfaces.append(i)
                    interface_added = True

            if interface_added:
                if ip['alias']['type'] == 'INET':
                    ipv4_enabled = True

                if ip['alias']['type'] == 'INET6':
                    ipv6_enabled = True

        if not allow_interfaces:
            middleware.logger.warning(
                'No public IPs are assigned to node %d which is acting as '
                'master for mDNS advertisement purposes.'
            )
            raise FileShouldNotExist()
    else:
        failover_status = middleware.call_sync('failover.status')
        if failover_status not in ['SINGLE', 'MASTER']:
            raise FileShouldNotExist()
        elif failover_status == 'MASTER':
            hostname_override = middleware.call_sync('network.configuration.config')['hostname_virtual']

        ipv4_enabled = any(middleware.call_sync('interface.ip_in_use', {'ipv4': True, 'ipv6': False}))
        ipv6_enabled = any(middleware.call_sync('interface.ip_in_use', {'ipv4': False, 'ipv6': True}))
        deny_interfaces = middleware.call_sync("interface.internal_interfaces")
        allow_interfaces = middleware.call_sync("interface.query", [["name", "!^", "macvtap"]])
%>

[server]
%if hostname_override is not None:
host-name=${hostname_override}
%endif
%if ipv4_enabled or ipv6_enabled:
use-ipv4=${"yes" if ipv4_enabled else "no"}
use-ipv6=${"yes" if ipv6_enabled else "no"}
%endif
ratelimit-interval-usec=1000000
ratelimit-burst=1000
deny-interfaces=${", ".join(deny_interfaces)}
allow-interfaces=${", ".join([x["name"] for x in allow_interfaces])}
disallow-other-stacks=yes

[wide-area]
enable-wide-area=yes

[publish]
publish-hinfo=no
publish-workstation=no
