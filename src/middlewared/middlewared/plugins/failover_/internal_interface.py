# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from pathlib import Path

from truenas_pynetif.address.address import add_address
from truenas_pynetif.address.bond import BondLacpRate, BondXmitHashPolicy
from truenas_pynetif.address.constants import RTNType
from truenas_pynetif.address.get_links import get_link, get_links
from truenas_pynetif.address.link import set_link_down, set_link_name, set_link_up
from truenas_pynetif.address.route import add_route
from truenas_pynetif.configure import BondConfig, configure_bond
from truenas_pynetif.ethtool import get_ethtool
from truenas_pynetif.netlink._core import netlink_route
from truenas_pynetif.netlink._exceptions import NetlinkError, RouteAlreadyExists
from truenas_pynetif.netlink import DeviceNotFound

from middlewared.plugins.failover_.detect_utils import is_vseries_v2_interconnect
from middlewared.service import Service
from middlewared.utils.functools_ import cache


def _find_vseries_x710_ports() -> list[str]:
    # Intel X710 10GBASE-T family (the 4IXGA_PEX89032 board uses X710-AT2).
    # The on-board X710-AT2 reports SUBSYS_ID=8086:0000 — same value a retail
    # X710-AT2 add-in card is likely to report — so VID:DID + SUBSYS_ID alone
    # is not a sufficient discriminator. Instead we also check the NIC's
    # parent PCI bridge: both on-board ports sit directly behind a PEX89032
    # (Broadcom / LSI PEX890xx Gen 5) switch downstream port. A user-installed
    # X710-AT2 in a normal PCIe slot will parent to a CPU root port or a
    # different bridge and therefore be ignored here.
    ports: list[tuple[str, str]] = []
    for iface in Path('/sys/class/net/').iterdir():
        try:
            uevent = (iface / 'device/uevent').read_text()
        except (FileNotFoundError, OSError):
            continue
        if 'PCI_ID=8086:15FF' not in uevent:
            continue
        try:
            nic_pci = (iface / 'device').resolve()
            parent_vendor = (nic_pci.parent / 'vendor').read_text().strip()
            parent_device = (nic_pci.parent / 'device').read_text().strip()
        except (FileNotFoundError, OSError):
            continue
        if (parent_vendor, parent_device) != ('0x1000', '0xc034'):
            continue
        ports.append((nic_pci.name, iface.name))
    ports.sort()
    return [name for _, name in ports]


class InternalInterfaceService(Service):

    http_site_added = False

    class Config:
        private = True
        namespace = 'failover.internal_interface'

    @cache
    def detect(self):
        found = list()
        hardware = self.middleware.call_sync('failover.hardware')
        if hardware == 'BHYVE':
            found.append('enp0s6f1')
        elif hardware == 'IXKVM':
            found.append('enp1s0')
        elif hardware == 'ECHOSTREAM':
            # z-series
            for i in Path('/sys/class/net/').iterdir():
                try:
                    data = (i / 'device/uevent').read_text()
                    if 'PCI_ID=8086:10D3' in data and 'PCI_SUBSYS_ID=8086:A01F' in data:
                        found.append(i.name)
                        break
                except FileNotFoundError:
                    continue
        elif hardware in ('PUMA', 'ECHOWARP', 'LAJOLLA2', 'SUBLIGHT'):
            # {x/m/f/h}-series
            found.append('ntb0')
        elif hardware in ('LUDICROUS', 'PLAID'):
            # v-series. DMI Type 1 Version selects interconnect topology:
            #   < 2.0  — external 10 GbE cable renamed to `internode0` by
            #            systemd `.link` (no bond, no X710 masking).
            #   >= 2.0 — `internode0` is a kernel LACP bond across the two
            #            on-board X710-AT2 ports (see ensure_vseries_bond).
            #            The members must also be returned here: the user
            #            list filter does NOT drop enslaved interfaces on
            #            its own, so member names would otherwise leak
            #            into `interface.query`. We return the stable
            #            post-rename names (`internode0_1`/`internode0_2`)
            #            AND the current kernel names so masking holds
            #            whether this method runs before or after the
            #            rename that happens in ensure_vseries_bond().
            found.append('internode0')
            if is_vseries_v2_interconnect():
                x710_ports = _find_vseries_x710_ports()
                if len(x710_ports) == 2:
                    found.extend(('internode0_1', 'internode0_2'))
                    for port in x710_ports:
                        if port not in found:
                            found.append(port)
        return tuple(found)

    def ensure_vseries_bond(self):
        # On V-Series with DMI Version >= 2.0, `internode0` is an LACP bond
        # across the two on-board X710 cross-connect ports. Create it
        # idempotently before the HA IP is assigned.
        hardware = self.middleware.call_sync('failover.hardware')
        if hardware not in ('LUDICROUS', 'PLAID'):
            return
        if not is_vseries_v2_interconnect():
            return

        members = _find_vseries_x710_ports()
        if len(members) != 2:
            self.logger.warning(
                'v-series >= 2.0: expected 2 internal X710 ports, found %d',
                len(members),
            )
            return

        # Rename each member to a stable, intent-revealing name
        # (internode0_1 / internode0_2) before enslavement. The rename
        # persists across boots via kernel-level naming; udev won't
        # rename it back because its .link rules only rename during
        # initial enumeration, not when an interface already has a
        # non-default name assigned by us here.
        target_names = ('internode0_1', 'internode0_2')
        with netlink_route() as sock:
            links = get_links(sock)
            renamed: list[str] = []
            for current, target in zip(members, target_names):
                if current == target:
                    renamed.append(current)
                    continue
                idx = links[current].index
                set_link_down(sock, index=idx)
                set_link_name(sock, target, index=idx)
                renamed.append(target)

            # Apply X710-side tuning while members are DOWN — avoids
            # resets that would flap LACP on an up bond. One ethtool
            # socket shared across both ports.
            eth = get_ethtool()
            for port in renamed:
                self._tune_vseries_x710_port(eth, port)

            # Refresh the link view so configure_bond sees the new names.
            links = get_links(sock)
            configure_bond(
                sock,
                BondConfig(
                    name='internode0',
                    mode='LACP',
                    members=renamed,
                    xmit_hash_policy=BondXmitHashPolicy.LAYER34,
                    lacpdu_rate=BondLacpRate.FAST,
                    miimon=100,
                    mtu=9000,
                ),
                links,
            )

    def _tune_vseries_x710_port(self, eth, iface: str) -> None:
        # Disable the i40e firmware LLDP agent so stray LLDP frames
        # don't get consumed by firmware and firmware-side DCBX can't
        # misnegotiate on this internal point-to-point interconnect.
        try:
            current = eth.get_priv_flags(iface)
            desired = {'disable-fw-lldp': True}
            to_set = {
                name: value
                for name, value in desired.items()
                if current.get(name) != value
            }
            if to_set:
                eth.set_priv_flags(iface, to_set)
        except (OSError, NetlinkError, ValueError) as e:
            self.logger.warning(
                '%s: priv-flag tuning skipped: %s', iface, e
            )

        # 4-tuple RX flow hash (`sdfn` = src-IP + dst-IP + src-port +
        # dst-port) so inbound controller-to-controller flows spread
        # across X710 RX queues instead of collapsing to a single
        # queue / CPU.
        for flow_type in ('tcp4', 'udp4'):
            try:
                eth.set_rx_flow_hash(iface, flow_type, 'sdfn')
            except (OSError, NetlinkError, ValueError) as e:
                self.logger.warning(
                    '%s: rx-flow-hash %s failed: %s', iface, flow_type, e,
                )

    async def pre_sync(self):
        if not await self.middleware.call('system.is_enterprise'):
            return

        await self.middleware.run_in_thread(self.ensure_vseries_bond)

        node = await self.middleware.call('failover.node')
        if node == 'A':
            internal_ip = '169.254.10.1'
        elif node == 'B':
            internal_ip = '169.254.10.2'
        else:
            self.logger.error('Node position could not be determined.')
            return

        iface = await self.middleware.call('failover.internal_interfaces')
        if not iface:
            self.logger.error('Internal interface not found.')
            return

        iface = iface[0]

        await self.middleware.run_in_thread(self.sync, iface, internal_ip)

    def sync(self, iface, internal_ip):
        with netlink_route() as sock:
            try:
                link = get_link(sock, iface)
            except DeviceNotFound:
                return

            try:
                add_address(sock, internal_ip, 24, index=link.index)
                set_link_up(sock, index=link.index)
            except NetlinkError:
                # ip address already exists on this interface
                pass

            # add a blackhole route of 169.254.10.0/23 which is 1 bit larger than
            # ip address we put on the internal interface. We do this because the
            # f-series platform uses AMD ntb driver and the behavior for when the
            # B controller is active and the A controller reboots, is that the ntb0
            # interface is removed from the B controller. This means any src/dst
            # traffic on the 169.254.10/24 subnet will be forwarded out of the gateway
            # of last resort (default route). Since this is internal traffic, we
            # obviously don't want to forward this traffic to the default gateway.
            # This just routes the data into oblivion (drops it).
            try:
                add_route(
                    sock,
                    dst='169.254.10.0',
                    dst_len=23,
                    route_type=RTNType.BLACKHOLE,
                )
            except RouteAlreadyExists:
                # blackhole route already exists
                pass

        self.middleware.call_sync('failover.internal_interface.post_sync', internal_ip)

    async def post_sync(self, internal_ip):
        if not self.http_site_added:
            await self.middleware.add_tcp_site(internal_ip)


async def __event_system_ready(middleware, event_type, args):
    await middleware.call('failover.internal_interface.pre_sync')


async def setup(middleware):
    # on HA systems, we bind ourselves on 127.0.0.1:6000, however
    # often times developers/CI/CD do `systemctl restart middlewared`
    # which will tear down the local listening socket so we need to
    # be sure and set it up everytime middleware starts. This is a
    # NO-OP otherwise.
    middleware.event_subscribe('system.ready', __event_system_ready)
    if await middleware.call('system.ready'):
        await middleware.call('failover.internal_interface.pre_sync')
