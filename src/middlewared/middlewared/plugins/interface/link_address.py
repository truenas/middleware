import re

from sqlalchemy.exc import IntegrityError

from middlewared.service import private, Service

INTERFACE_FILTERS = [["type", "=", "PHYSICAL"]]
RE_FREEBSD_BRIDGE = re.compile(r"bridge([0-9]+)$")
RE_FREEBSD_LAGG = re.compile(r"lagg([0-9]+)$")


class DuplicateHardwareInterfaceLinkAddresses(Exception):
    def __init__(self, name1, name2, link_address):
        self.name1 = name1
        self.name2 = name2
        self.link_address = link_address
        super().__init__(name1, name2, link_address)

    def __str__(self):
        return f"Interfaces {self.name1!r} and {self.name2!r} have the same hardware link address {self.link_address!r}"


class InterfaceService(Service):

    class Config:
        namespace_alias = "interfaces"

    @private
    async def persist_link_addresses(self):
        try:
            local_key, remote_key = await self._get_keys()

            real_interfaces = RealInterfaceCollection(
                await self.middleware.call("interface.query", INTERFACE_FILTERS),
            )

            real_interfaces_remote = None
            if await self.middleware.call("failover.status") == "MASTER":
                try:
                    real_interfaces_remote = RealInterfaceCollection(
                        await self.middleware.call("failover.call_remote", "interface.query", [INTERFACE_FILTERS]),
                    )
                except Exception as e:
                    self.middleware.logger.warning(f"Exception while retrieving remote network interfaces: {e!r}")

            db_interfaces = DatabaseInterfaceCollection(
                await self.middleware.call("datastore.query", "network.interface_link_address"),
            )

            for real_interface in real_interfaces:
                name = real_interfaces.get_name(real_interface)
                await self.__handle_interface(db_interfaces, name, local_key,
                                              real_interface["state"]["hardware_link_address"])
                if real_interfaces_remote is not None:
                    real_interface_remote = real_interfaces_remote.by_name.get(name)
                    if real_interface_remote is None:
                        self.middleware.logger.warning(f"Interface {name!r} is only present on the local system")
                    else:
                        try:
                            remote_hardware_link_address = real_interface_remote["state"]["hardware_link_address"]
                        except KeyError:
                            pass
                        else:
                            await self.__handle_interface(db_interfaces, name, remote_key, remote_hardware_link_address)
        except DuplicateHardwareInterfaceLinkAddresses as e:
            self.middleware.logger.error(f"Not persisting network interfaces link addresses: {e}")
        except Exception:
            self.middleware.logger.error("Unhandled exception while persisting network interfaces link addresses",
                                         exc_info=True)

    async def _get_keys(self):
        if await self.middleware.call("failover.node") == "B":
            local_key = "link_address_b"
            remote_key = "link_address"
        else:
            local_key = "link_address"
            remote_key = "link_address_b"

        return local_key, remote_key

    async def __handle_interface(self, db_interfaces, name, key, link_address):
        interface = db_interfaces.by_name.get(name)
        if interface is None:
            self.middleware.logger.debug(f"Creating interface {name!r} {key} = {link_address!r}")

            interface = {
                "interface": name,
                "link_address": None,
                "link_address_b": None,
                key: link_address,
            }
            interface["id"] = await self.middleware.call("datastore.insert", "network.interface_link_address",
                                                         interface)
            db_interfaces.interfaces.append(interface)
        elif interface[key] != link_address:
            self.middleware.logger.debug(f"Updating interface {name!r} {key} = {link_address!r}")

            await self.middleware.call("datastore.update", "network.interface_link_address", interface["id"],
                                       {key: link_address})

    @private
    async def local_macs_to_remote_macs(self):
        local_key, remote_key = await self._get_keys()
        return {
            interface[local_key]: interface[remote_key]
            for interface in await self.middleware.call("datastore.query", "network.interface_link_address")
            if interface[local_key] is not None and interface[remote_key] is not None
        }


class InterfaceCollection:
    def __init__(self, interfaces):
        self.interfaces = interfaces

    @property
    def by_name(self):
        return {self.get_name(i): i for i in self.interfaces}

    def __iter__(self):
        return iter(self.interfaces)

    def get_name(self, i):
        raise NotImplementedError


class DatabaseInterfaceCollection(InterfaceCollection):
    def get_name(self, i):
        return i["interface"]


class RealInterfaceCollection(InterfaceCollection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.by_link_address = {}
        for i in self.interfaces:
            link_address = i["state"]["hardware_link_address"]
            if link_address in self.by_link_address:
                raise DuplicateHardwareInterfaceLinkAddresses(self.by_link_address[link_address]["name"], i["name"],
                                                              link_address)
            self.by_link_address[link_address] = i

    def get_name(self, i):
        return i["name"]


class InterfaceRenamer:
    def __init__(self, middleware):
        self.middleware = middleware
        self.mapping = {}

    def rename(self, old_name, new_name):
        self.middleware.logger.info("Renaming interface %r to %r", old_name, new_name)
        self.mapping[old_name] = new_name

    async def commit(self):
        for interface in await self.middleware.call("datastore.query", "network.interface_link_address"):
            if new_name := self.mapping.get(interface["interface"]):
                self.middleware.logger.info("Renaming hardware interface %r to %r", interface["interface"], new_name)
                try:
                    await self.middleware.call(
                        "datastore.update", "network.interface_link_address", interface["id"], {"interface": new_name},
                        {"ha_sync": False},
                    )
                except IntegrityError:
                    self.middleware.logger.warning(
                        f"Already had configuration for hardware interface {new_name!r}, removing old entry"
                    )
                    await self.middleware.call(
                        "datastore.delete", "network.interface_link_address", interface["id"], {"ha_sync": False},
                    )

        for interface in await self.middleware.call("datastore.query", "network.interfaces", [], {"prefix": "int_"}):
            if new_name := self.mapping.get(interface["interface"]):
                self.middleware.logger.info("Renaming interface configuration %r to %r", interface["interface"],
                                            new_name)
                try:
                    await self.middleware.call(
                        "datastore.update", "network.interfaces", interface["id"], {"interface": new_name},
                        {"prefix": "int_", "ha_sync": False},
                    )
                except IntegrityError:
                    self.middleware.logger.warning(
                        f"Already had configuration for interface {new_name!r}, removing old entry"
                    )
                    await self.middleware.call(
                        "datastore.delete", "network.interfaces", interface["id"], {"ha_sync": False},
                    )

        for bridge in await self.middleware.call("datastore.query", "network.bridge"):
            updated = False
            for i, member in enumerate(bridge["members"]):
                if new_name := self.mapping.get(member):
                    self.middleware.logger.info("Changing bridge %r member %r to %r", bridge["id"], member, new_name)
                    bridge["members"][i] = new_name
                    updated = True

            if updated:
                await self.middleware.call(
                    "datastore.update", "network.bridge", bridge["id"], {"members": bridge["members"]},
                    {"ha_sync": False},
                )

        await self._commit_laggs()

        for vlan in await self.middleware.call("datastore.query", "network.vlan"):
            if new_name := self.mapping.get(vlan["vlan_pint"]):
                self.middleware.logger.info("Changing VLAN %r parent NIC from %r to %r", vlan["vlan_vint"],
                                            vlan["vlan_pint"], new_name)
                await self.middleware.call(
                    "datastore.update", "network.vlan", vlan["id"], {"vlan_pint": new_name}, {"ha_sync": False},
                )

        # We use vm.device.query because attributes.dtype filter won't work with datastore plugin as attributes
        # column is not serialized at the point datastore plugin applies filters
        for vm_device in await self.middleware.call("vm.device.query", [["attributes.dtype", "=", "NIC"]]):
            if new_name := self.mapping.get(vm_device["attributes"].get("nic_attach")):
                self.middleware.logger.info("Changing VM NIC device %r from %r to %r", vm_device["id"],
                                            vm_device["attributes"]["nic_attach"], new_name)
                await self.middleware.call("datastore.update", "vm.device", vm_device["id"], {
                    "attributes": {**vm_device["attributes"], "nic_attach": new_name},
                }, {"ha_sync": False})

    async def _commit_laggs(self):
        lagg_members = await self.middleware.call("datastore.query", "network.lagginterfacemembers", [],
                                                  {"prefix": "lagg_"})
        lagg_members_changed = False
        for lagg_member in lagg_members:
            if new_name := self.mapping.get(lagg_member["physnic"]):
                self.middleware.logger.info("Changing LAGG member %r physical NIC from %r to %r", lagg_member["id"],
                                            lagg_member["physnic"], new_name)
                lagg_member["physnic"] = new_name
                lagg_member.pop("delete", None)
                lagg_members_changed = True

                for other_lagg_member in lagg_members:
                    if other_lagg_member["id"] != lagg_member["id"]:
                        if other_lagg_member["physnic"] == new_name:
                            other_lagg_member["delete"] = True

        for lagg_member in lagg_members:
            if lagg_member.get("delete"):
                self.middleware.logger.info(
                    "Deleting LAGG member %r as it uses physical NIC which is now also used in another LAGG member",
                    lagg_member["physnic"],
                )

        if lagg_members_changed:
            for lagg_member in lagg_members:
                await self.middleware.call(
                    "datastore.delete", "network.lagginterfacemembers", lagg_member["id"], {"ha_sync": False},
                )
            for order, lagg_member in enumerate(lagg_members):
                if "delete" not in lagg_member:
                    await self.middleware.call("datastore.insert", "network.lagginterfacemembers", {
                        "interfacegroup": lagg_member["interfacegroup"]["id"],
                        "physnic": lagg_member["physnic"],
                        "ordernum": order,
                    }, {"prefix": "lagg_", "ha_sync": False})


async def setup(middleware):
    try:
        interface_renamer = InterfaceRenamer(middleware)

        if await middleware.call("failover.node") == "B":
            link_address_key = "link_address_b"
        else:
            link_address_key = "link_address"

        real_interfaces = RealInterfaceCollection(await middleware.call("interface.query", INTERFACE_FILTERS))

        # Migrate BSD network interfaces to Linux
        for db_interface in await middleware.call("datastore.query", "network.interfaces", [], {"prefix": "int_"}):
            if m := RE_FREEBSD_BRIDGE.match(db_interface["interface"]):
                interface_renamer.rename(db_interface["interface"], f"br{m.group(1)}")

            if m := RE_FREEBSD_LAGG.match(db_interface["interface"]):
                interface_renamer.rename(db_interface["interface"], f"bond{m.group(1)}")

        db_interfaces = DatabaseInterfaceCollection(
            await middleware.call("datastore.query", "network.interface_link_address"),
        )
        for db_interface in db_interfaces:
            if db_interface[link_address_key] is not None:
                real_interface_by_link_address = real_interfaces.by_link_address.get(db_interface[link_address_key])
                if real_interface_by_link_address is None:
                    middleware.logger.warning(
                        "Interface with link address %r does not exist anymore (its name was %r)",
                        db_interface[link_address_key], db_interface["interface"],
                    )
                    continue

                if real_interface_by_link_address["name"] == db_interface["interface"]:
                    continue

                middleware.logger.info(
                    "Interface %r is now %r (matched by link address %r)",
                    db_interface["interface"], real_interface_by_link_address["name"], db_interface[link_address_key],
                )
                interface_renamer.rename(db_interface["interface"], real_interface_by_link_address["name"])

        await interface_renamer.commit()
    except DuplicateHardwareInterfaceLinkAddresses as e:
        middleware.logger.error(f"Not migrating network interfaces: {e}")
    except Exception:
        middleware.logger.error("Unhandled exception while migrating network interfaces", exc_info=True)

    await middleware.call("interface.persist_link_addresses")
