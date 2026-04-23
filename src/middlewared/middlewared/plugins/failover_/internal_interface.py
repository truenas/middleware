# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import ipaddress
import subprocess
from pathlib import Path

from pyroute2 import NDB

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


def _bond_members(bond: str) -> list[str]:
    try:
        return Path(f'/sys/class/net/{bond}/bonding/slaves').read_text().split()
    except FileNotFoundError:
        return []


class InternalInterfaceService(Service):

    http_site = None

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
        #
        # Note: backport shells out to `ip` / `ethtool` rather than using
        # truenas_pynetif (not present on 25.10.x). The master branch uses
        # the pynetif genl helpers directly.
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

        bond_name = 'internode0'
        target_names = ('internode0_1', 'internode0_2')

        # If bond already exists with the right members we're done.
        # Otherwise tear it down and rebuild from scratch.
        if Path(f'/sys/class/net/{bond_name}').exists():
            if set(_bond_members(bond_name)) == set(target_names):
                return
            subprocess.run(['ip', 'link', 'del', bond_name], check=True)

        # Rename each member to a stable, intent-revealing name
        # (internode0_1 / internode0_2) before enslavement. Links must be
        # DOWN to be renamed.
        renamed: list[str] = []
        for current, target in zip(members, target_names):
            if current == target:
                renamed.append(current)
                continue
            subprocess.run(['ip', 'link', 'set', current, 'down'], check=True)
            subprocess.run(
                ['ip', 'link', 'set', current, 'name', target], check=True
            )
            renamed.append(target)

        # Apply per-member X710 tuning while the members are DOWN — avoids
        # resets that would otherwise flap LACP on a live bond.
        for port in renamed:
            self._tune_vseries_x710_port(port)

        # Create the bond DOWN with no slaves so mode-family options can be
        # set (kernel rejects mode change once a bond has any slaves).
        subprocess.run(
            ['ip', 'link', 'add', bond_name, 'type', 'bond'], check=True
        )
        subprocess.run(['ip', 'link', 'set', bond_name, 'down'], check=True)
        subprocess.run(
            [
                'ip', 'link', 'set', bond_name, 'type', 'bond',
                'mode', '802.3ad',
                'xmit_hash_policy', 'layer3+4',
                'lacp_rate', 'fast',
                'miimon', '100',
            ],
            check=True,
        )
        for member in renamed:
            subprocess.run(['ip', 'link', 'set', member, 'down'], check=True)
            subprocess.run(
                ['ip', 'link', 'set', member, 'master', bond_name], check=True
            )
        subprocess.run(
            ['ip', 'link', 'set', bond_name, 'mtu', '9000'], check=True
        )
        subprocess.run(['ip', 'link', 'set', bond_name, 'up'], check=True)

    def _tune_vseries_x710_port(self, iface: str) -> None:
        # Disable the i40e firmware LLDP agent so stray LLDP frames
        # don't get consumed by firmware and firmware-side DCBX can't
        # misnegotiate on this internal point-to-point interconnect.
        # ethtool is already idempotent for this priv-flag so we don't
        # bother reading current state first.
        try:
            subprocess.run(
                ['ethtool', '--set-priv-flags', iface, 'disable-fw-lldp', 'on'],
                check=True, capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            self.logger.warning(
                '%s: priv-flag tuning skipped: %s', iface,
                e.stderr.decode(errors='replace').strip(),
            )

        # 4-tuple RX flow hash (`sdfn` = src-IP + dst-IP + src-port +
        # dst-port) so inbound controller-to-controller flows spread
        # across X710 RX queues instead of collapsing to a single
        # queue / CPU.
        for flow_type in ('tcp4', 'udp4'):
            try:
                subprocess.run(
                    ['ethtool', '-N', iface, 'rx-flow-hash', flow_type, 'sdfn'],
                    check=True, capture_output=True,
                )
            except subprocess.CalledProcessError as e:
                self.logger.warning(
                    '%s: rx-flow-hash %s failed: %s', iface, flow_type,
                    e.stderr.decode(errors='replace').strip(),
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
        default_table, rtn_blackhole = 254, 6
        with NDB(log='off') as ndb:
            try:
                with ndb.interfaces[iface] as dev:
                    dev.add_ip(f'{internal_ip}/24').set(state='up')
            except KeyError:
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
            dst_network = ipaddress.ip_interface(f'{internal_ip}/23').network.exploded
            try:
                ndb.routes.create(dst=dst_network, table=default_table, type=rtn_blackhole).commit()
            except KeyError:
                # blackhole route already exists
                pass

        self.middleware.call_sync('failover.internal_interface.post_sync', internal_ip)

    async def post_sync(self, internal_ip):
        if self.http_site is None:
            self.http_site = await self.middleware.start_tcp_site(internal_ip)


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
