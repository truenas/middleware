import re

from middlewared.service import private, Service

RE_FREEBSD_BRIDGE = re.compile(r"bridge([0-9]+)$")
RE_FREEBSD_LAGG = re.compile(r"lagg([0-9]+)$")


class InterfaceService(Service):

    class Config:
        namespace_alias = "interfaces"

    @private
    async def persist_link_addresses(self):
        try:
            if await self.middleware.call("failover.node") == "B":
                local_key = "link_address_b"
                remote_key = "link_address"
            else:
                local_key = "link_address"
                remote_key = "link_address_b"

            real_interfaces = RealInterfaceCollection(
                await self.middleware.call("interface.query", [["fake", "!=", True]]),
            )

            real_interfaces_remote = None
            if await self.middleware.call("failover.status") == "MASTER":
                try:
                    real_interfaces_remote = RealInterfaceCollection(
                        await self.middleware.call("failover.call_remote", "interface.query", [[["fake", "!=", True]]]),
                    )
                except Exception as e:
                    self.middleware.logger.warning(f"Exception while retrieving remote network interfaces: {e!r}")

            db_interfaces = DatabaseInterfaceCollection(
                await self.middleware.call("datastore.query", "network.interfaces", [], {"prefix": "int_"}),
            )

            # Update link addresses for interfaces in the database
            for db_interface in db_interfaces:
                update = {}
                self.__handle_update(real_interfaces, db_interface, local_key, update)
                if real_interfaces_remote is not None:
                    self.__handle_update(real_interfaces_remote, db_interface, remote_key, update)

                if update:
                    await self.middleware.call("datastore.update", "network.interfaces", db_interface["id"],
                                               update, {"prefix": "int_"})
        except Exception:
            self.middleware.logger.error("Unhandled exception while persisting network interfaces link addresses",
                                         exc_info=True)

    def __handle_update(self, real_interfaces, db_interface, key, update):
        real_interface = real_interfaces.by_name.get(db_interface["interface"])
        if real_interface is None:
            link_address_local = None
        else:
            link_address_local = real_interface["state"]["link_address"]

        if db_interface[key] != link_address_local:
            self.middleware.logger.debug(
                f"Setting interface {db_interface['interface']!r} {key} = {link_address_local!r}",
            )
            update[key] = link_address_local


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
    @property
    def by_link_address(self):
        return {i["state"]["link_address"]: i for i in self.interfaces}

    def get_name(self, i):
        return i["name"]


async def rename_interface(middleware, db_interface, name):
    middleware.logger.info("Renaming interface %r to %r", db_interface["interface"], name)
    await middleware.call("datastore.update", "network.interfaces", db_interface["id"],
                          {"interface": name}, {"prefix": "int_"})

    for bridge in await middleware.call("datastore.query", "network.bridge"):
        try:
            index = bridge["members"].index(db_interface["interface"])
        except ValueError:
            continue

        bridge["members"][index] = name
        middleware.logger.info("Setting bridge %r members: %r", bridge["id"], bridge["members"])
        await middleware.call("datastore.update", "network.bridge", bridge["id"], {"members": bridge["members"]})

    for lagg_member in await middleware.call("datastore.query", "network.lagginterfacemembers"):
        if lagg_member["lagg_physnic"] == db_interface["interface"]:
            middleware.logger.info("Setting LAGG member %r physical NIC %r", lagg_member["id"], name)
            await middleware.call("datastore.update", "network.lagginterfacemembers", lagg_member["id"],
                                  {"lagg_physnic": name})

    for vlan in await middleware.call("datastore.query", "network.vlan"):
        if vlan["vlan_pint"] == db_interface["interface"]:
            middleware.logger.info("Setting VLAN %r parent NIC %r", vlan["vlan_vint"], vlan["vlan_pint"])
            await middleware.call("datastore.update", "network.vlan", vlan["id"],
                                  {"vlan_pint": name})

    for vm_device in await middleware.call("datastore.query", "vm.device", [["dtype", "=", "NIC"]]):
        if vm_device["attributes"].get("nic_attach") == db_interface["interface"]:
            middleware.logger.info("Updating VM NIC device for %r", vm_device["attributes"]["nic_attach"])
            await middleware.call("datastore.update", "vm.device", vm_device["id"], {
                "attributes": {**vm_device["attributes"], "nic_attach": name},
            })


async def setup(middleware):
    try:
        if await middleware.call("failover.node") == "B":
            link_address_key = "link_address_b"
        else:
            link_address_key = "link_address"

        real_interfaces = RealInterfaceCollection(await middleware.call("interface.query", [["fake", "!=", True]]))
        db_interfaces = DatabaseInterfaceCollection(
            await middleware.call("datastore.query", "network.interfaces", [], {"prefix": "int_"}),
        )

        # Migrate BSD network interfaces to Linux
        for db_interface in db_interfaces:
            iface = db_interface["interface"]
            if iface.startswith(("vlan", "bond")) or (iface[:2] == "br" and iface.find("bridge") == -1):
                # "vlan" interfaces dont need to be migrated since they share the same name with CORE
                # "bond" and "br" interfaces have already been migrated
                continue

            if m := RE_FREEBSD_BRIDGE.match(db_interface["interface"]):
                name = f"br{m.group(1)}"
                await rename_interface(middleware, db_interface, name)
                db_interface["interface"] = name

            if m := RE_FREEBSD_LAGG.match(db_interface["interface"]):
                name = f"bond{m.group(1)}"
                await rename_interface(middleware, db_interface, name)
                db_interface["interface"] = name

            if db_interface[link_address_key] is not None:
                if real_interfaces.by_name.get(db_interface["interface"]) is not None:
                    # There already is an interface that matches DB cached one, doing nothing
                    continue

                real_interface_by_link_address = real_interfaces.by_link_address.get(db_interface[link_address_key])
                if real_interface_by_link_address is None:
                    middleware.logger.warning(
                        "Interface with link address %r does not exist anymore (its name was %r)",
                        db_interface[link_address_key], db_interface["interface"],
                    )
                    continue

                db_interface_for_real_interface = db_interfaces.by_name.get(real_interface_by_link_address["name"])
                if db_interface_for_real_interface is not None:
                    if db_interface_for_real_interface != db_interface:
                        middleware.logger.warning(
                            "Database already has interface %r (we wanted to set that name for interface %r "
                            "because it matches its link address %r)",
                            real_interface_by_link_address["name"], db_interface["interface"],
                            db_interface[link_address_key],
                        )
                    continue

                middleware.logger.info(
                    "Interface %r is now %r (matched by link address %r)",
                    db_interface["interface"], real_interface_by_link_address["name"], db_interface[link_address_key],
                )
                await rename_interface(middleware, db_interface, real_interface_by_link_address["name"])
                db_interface["interface"] = real_interface_by_link_address["name"]
    except Exception:
        middleware.logger.error("Unhandled exception while migrating network interfaces", exc_info=True)

    await middleware.call("interface.persist_link_addresses")
