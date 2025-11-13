# -*- coding=utf-8 -*-
import logging
from unittest.mock import ANY, AsyncMock

import pytest

from middlewared.plugins.interface.link_address import InterfaceService, setup as link_address_setup
from middlewared.pytest.unit.plugins.datastore.test_datastore import Model, datastore_test
import middlewared.sqlalchemy as sa

logger = logging.getLogger(__name__)


class NetworkBridgeModel(Model):
    __tablename__ = 'network_bridge'

    id = sa.Column(sa.Integer(), primary_key=True)  # noqa
    interface_id = sa.Column(sa.ForeignKey('network_interfaces.id', ondelete='CASCADE'))
    members = sa.Column(sa.JSON(list), default=[])


class NetworkInterfaceModel(Model):
    __tablename__ = "network_interfaces"

    id = sa.Column(sa.Integer(), primary_key=True)  # noqa
    int_interface = sa.Column(sa.Integer(), nullable=False)
    int_settings = sa.Column(sa.Integer())


class NetworkInterfaceLinkAddressModel(Model):
    __tablename__ = 'network_interface_link_address'

    id = sa.Column(sa.Integer, primary_key=True)  # noqa
    interface = sa.Column(sa.String(300))
    link_address = sa.Column(sa.String(17), nullable=True)
    link_address_b = sa.Column(sa.String(17), nullable=True)


class NetworkLaggInterfaceModel(Model):
    __tablename__ = 'network_lagginterface'

    id = sa.Column(sa.Integer, primary_key=True)  # noqa
    lagg_interface_id = sa.Column(sa.Integer(), sa.ForeignKey('network_interfaces.id'))


class NetworkLaggInterfaceMemberModel(Model):
    __tablename__ = 'network_lagginterfacemembers'

    id = sa.Column(sa.Integer, primary_key=True)  # noqa
    lagg_ordernum = sa.Column(sa.Integer())
    lagg_interfacegroup_id = sa.Column(sa.ForeignKey('network_lagginterface.id', ondelete='CASCADE'), index=True)
    lagg_physnic = sa.Column(sa.String(120), unique=True)


class NetworkVlanModel(Model):
    __tablename__ = 'network_vlan'

    id = sa.Column(sa.Integer(), primary_key=True)  # noqa
    vlan_vint = sa.Column(sa.String(120))
    vlan_pint = sa.Column(sa.String(300))


class VMDeviceModel(Model):
    __tablename__ = 'vm_device'

    id = sa.Column(sa.Integer(), primary_key=True)  # noqa
    attributes = sa.Column(sa.JSON())


@pytest.mark.parametrize("before,after", [
    # BSD -> Linux interface rename
    (
        {
            "hw": {"em0": "08:00:27:1e:9f:d3", "em1": "08:00:27:1e:9f:d4"},
            "interface": {"em0": 0, "em1": 1, "bridge6": 66, "lagg7": 77, "vlan8": 88},
            "bridge": {"bridge6": ["em0", "em1"]},
            "lagg": {"lagg7": ["em1", "em0"]},
            "vlan": {"vlan8": "em1"},
            "vm": ["em1"],
        },
        {
            "hw": {"eth0": "08:00:27:1e:9f:d3", "eth1": "08:00:27:1e:9f:d4"},
            "interface": {"eth0": 0, "eth1": 1, "br6": 66, "bond7": 77, "vlan8": 88},
            "bridge": {"br6": ["eth0", "eth1"]},
            "lagg": {"bond7": ["eth1", "eth0"]},
            "vlan": {"vlan8": "eth1"},
            "vm": ["eth1"],
        },
    ),
    # Interfaces swapped names
    (
        {
            "hw": {"eth0": "08:00:27:1e:9f:d3", "eth1": "08:00:27:1e:9f:d4"},
            "interface": {"eth0": 0, "eth1": 1, "lagg0": 10, "lagg1": 11},
            "lagg": {"lagg0": ["eth0"], "lagg1": ["eth1"]},
        },
        {
            "hw": {"eth1": "08:00:27:1e:9f:d3", "eth0": "08:00:27:1e:9f:d4"},
            "interface": {"eth1": 0, "eth0": 1, "bond0": 10, "bond1": 11},
            "lagg": {"bond0": ["eth1"], "bond1": ["eth0"]},
        },
    ),
    # Multiple LAGGs
    (
        {
            "hw": {"eth0": "00:00:00:00:00:00", "eth1": "00:00:00:00:00:01",
                   "eth2": "00:00:00:00:00:02", "eth3": "00:00:00:00:00:03"},
            "interface": {"eth0": 0, "eth1": 1, "eth2": 2, "eth3": 3, "bond0": 10, "bond1": 11},
            "lagg": {"bond0": ["eth0", "eth1"], "bond1": ["eth2", "eth3"]},
        },
        {
            "hw": {"enp131s0": "00:00:00:00:00:00", "enp131s1": "00:00:00:00:00:01",
                   "enp131s2": "00:00:00:00:00:02", "enp131s3": "00:00:00:00:00:03"},
            "interface": {"enp131s0": 0, "enp131s1": 1, "enp131s2": 2, "enp131s3": 3, "bond0": 10, "bond1": 11},
            "lagg": {"bond0": ["enp131s0", "enp131s1"], "bond1": ["enp131s2", "enp131s3"]},
        },
    ),
    # Interface gone
    (
        {
            "hw": {"eth0": "08:00:27:1e:9f:d3", "eth1": "08:00:27:1e:9f:d4"},
            "interface": {"eth0": 0, "eth1": 1, "br0": 66, "bond0": 77, "vlan0": 88},
            "bridge": {"br0": ["eth0", "eth1"]},
            "lagg": {"bond0": ["eth0", "eth1"]},
            "vlan": {"vlan0": "eth1"},
            "vm": ["eth1"],
        },
        {
            "interface.query": {"eth0": "08:00:27:1e:9f:d3"},
            "hw": {"eth0": "08:00:27:1e:9f:d3", "eth1": "08:00:27:1e:9f:d4"},
            "interface": {"eth0": 0, "eth1": 1, "br0": 66, "bond0": 77, "vlan0": 88},
            "bridge": {"br0": ["eth0", "eth1"]},
            "lagg": {"bond0": ["eth0", "eth1"]},
            "vlan": {"vlan0": "eth1"},
            "vm": ["eth1"],
        },
    ),
    # New interface
    (
        {
            "hw": {"eth0": "08:00:27:1e:9f:d3"},
            "interface": {"eth0": 0, "eth1": 1, "br0": 66, "bond0": 77, "vlan0": 88},
            "bridge": {"br0": ["eth0", "eth1"]},
            "lagg": {"bond0": ["eth0", "eth1"]},
            "vlan": {"vlan0": "eth1"},
            "vm": ["eth1"],
        },
        {
            "interface.query": {"eth0": "08:00:27:1e:9f:d3", "eth1": "08:00:27:1e:9f:d4"},
            "hw": {"eth0": "08:00:27:1e:9f:d3", "eth1": "08:00:27:1e:9f:d4"},
            "interface": {"eth0": 0, "eth1": 1, "br0": 66, "bond0": 77, "vlan0": 88},
            "bridge": {"br0": ["eth0", "eth1"]},
            "lagg": {"bond0": ["eth0", "eth1"]},
            "vlan": {"vlan0": "eth1"},
            "vm": ["eth1"],
        },
    ),
    # Duplicate addresses
    (
        {
            "hw": {"eth0": "08:00:27:1e:9f:d3", "eth1": "08:00:27:1e:9f:d3"},
            "interface": {"eth0": 0, "eth1": 1},
        },
        {
            "interface.query": {"eth0": "08:00:27:1e:9f:d3", "eth1": "08:00:27:1e:9f:d3"},
            "hw": {"eth0": "08:00:27:1e:9f:d3", "eth1": "08:00:27:1e:9f:d3"},
            "interface": {"eth0": 0, "eth1": 1},
        },
    ),
])
@pytest.mark.asyncio
async def test__interface_link_address_setup(before, after):
    async with datastore_test() as ds:
        ds.middleware["failover.node"] = AsyncMock(return_value="MANUAL")
        ds.middleware["failover.status"] = AsyncMock(return_value="SINGLE")
        ds.middleware["interface.persist_link_addresses"] = InterfaceService(ds.middleware).persist_link_addresses

        for interface, link_address in before.get("hw", {}).items():
            await ds.insert("network.interface_link_address", {
                "interface": interface,
                "link_address": link_address,
            })

        interface_id = {}
        for interface, settings in before.get("interface", {}).items():
            interface_id[interface] = await ds.insert("network.interfaces", {
                "interface": interface,
                "settings": settings,
            }, {"prefix": "int_"})

        for interface, members in before.get("bridge", {}).items():
            await ds.insert("network.bridge", {
                "interface": interface_id[interface],
                "members": members,
            })

        for interface, members in before.get("lagg", {}).items():
            lagg_id = await ds.insert("network.lagginterface", {
                "interface": interface_id[interface],
            }, {"prefix": "lagg_"})

            for order, member in enumerate(members):
                await ds.insert("network.lagginterfacemembers", {
                    "interfacegroup": lagg_id,
                    "physnic": member,
                    "ordernum": order,
                }, {"prefix": "lagg_"})

        for vint, pint in before.get("vlan", {}).items():
            await ds.insert("network.vlan", {
                "vint": vint,
                "pint": pint,
            }, {"prefix": "vlan_"})

        for interface in before.get("vm", []):
            id_ = await ds.insert("vm.device", {
                "attributes": {"nic_attach": interface, "dtype": "NIC"},
            })
            ds.middleware["vm.device.query"] = lambda *args: [
                {'id': id_, "attributes": {"nic_attach": interface, "dtype": "NIC"}}
            ]

        ds.middleware["interface.query"] = AsyncMock(return_value=[
            {
                "name": name,
                "state": {
                    "hardware_link_address": link_address,
                }
            }
            for name, link_address in (
                after["interface.query"] if "interface.query" in after else after.get("hw", {})
            ).items()
        ])

        await link_address_setup(ds.middleware)

        assert await ds.query("network.interface_link_address", [], {"prefix": "int_"}) == [
            {
                "id": ANY,
                "interface": interface,
                "link_address": link_address,
                "link_address_b": None,
            }
            for interface, link_address in after.get("hw", {}).items()
        ]

        assert await ds.query("network.interfaces", [], {"prefix": "int_"}) == [
            {
                "id": ANY,
                "interface": interface,
                "settings": settings,
            }
            for interface, settings in after.get("interface", {}).items()
        ]

        assert await ds.query("network.bridge") == [
            {
                "id": ANY,
                "interface": {"id": ANY, "int_interface": interface, "int_settings": ANY},
                "members": members,
            }
            for interface, members in after.get("bridge", {}).items()
        ]

        assert await ds.query("network.lagginterface", [], {"prefix": "lagg_"}) == [
            {
                "id": ANY,
                "interface": {"id": ANY, "int_interface": interface, "int_settings": ANY},
            }
            for interface, members in after.get("lagg", {}).items()
        ]

        for lagg in await ds.query("network.lagginterface", [], {"prefix": "lagg_"}):
            members = after["lagg"].get(lagg["interface"]["int_interface"])

            assert await ds.query(
                "network.lagginterfacemembers",
                [["interfacegroup", "=", lagg["id"]]],
                {"prefix": "lagg_", "order_by": ["ordernum"]}
            ) == [
                {
                    "id": ANY,
                    "interfacegroup": ANY,
                    "physnic": member,
                    "ordernum": ANY,
                }
                for member in members
            ]

        assert await ds.query("network.vlan", [], {"prefix": "vlan_"}) == [
            {
                "id": ANY,
                "vint": vint,
                "pint": pint,
            }
            for vint, pint in after.get("vlan", {}).items()
        ]

        assert await ds.query("vm.device") == [
            {
                "id": ANY,
                "attributes": {"nic_attach": interface, "dtype": "NIC"},
            }
            for interface in after.get("vm", [])
        ]
