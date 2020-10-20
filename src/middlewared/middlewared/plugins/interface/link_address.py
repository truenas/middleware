import re

from middlewared.utils import osc

RE_FREEBSD_BRIDGE = re.compile(r"bridge([0-9]+)$")
RE_FREEBSD_LAGG = re.compile(r"lagg([0-9]+)$")


class InterfaceCollection:
    def __init__(self, interfaces):
        self.interfaces = interfaces

    @property
    def by_name(self):
        return {self.get_name(i): i for i in self.interfaces}

    @property
    def by_link_address(self):
        return {self.get_link_address(i): i for i in self.interfaces}

    def __iter__(self):
        return iter(self.interfaces)

    def get_name(self, i):
        raise NotImplementedError

    def get_link_address(self, i):
        raise NotImplementedError


class DatabaseInterfaceCollection(InterfaceCollection):
    def get_name(self, i):
        return i["interface"]

    def get_link_address(self, i):
        return i["link_address"]


class RealInterfaceCollection(InterfaceCollection):
    def get_name(self, i):
        return i["name"]

    def get_link_address(self, i):
        return i["state"]["link_address"]


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


async def setup(middleware):
    try:
        real_interfaces = RealInterfaceCollection(await middleware.call("interface.query", [["fake", "!=", True]]))
        db_interfaces = DatabaseInterfaceCollection(
            await middleware.call("datastore.query", "network.interfaces", [], {"prefix": "int_"}),
        )

        # Migrate BSD network interfaces to Linux
        if osc.IS_LINUX:
            for db_interface in db_interfaces:
                if m := RE_FREEBSD_BRIDGE.match(db_interface["interface"]):
                    name = f"br{m.group(1)}"
                    await rename_interface(middleware, db_interface, name)
                    db_interface["interface"] = name

                if m := RE_FREEBSD_LAGG.match(db_interface["interface"]):
                    name = f"bond{m.group(1)}"
                    await rename_interface(middleware, db_interface, name)
                    db_interface["interface"] = name

                if db_interface["link_address"] is not None:
                    if real_interfaces.by_name.get(db_interface["interface"]) is not None:
                        # There already is an interface that matches DB cached one, doing nothing
                        continue

                    real_interface_by_link_address = real_interfaces.by_link_address.get(db_interface["link_address"])
                    if real_interface_by_link_address is None:
                        middleware.logger.warning(
                            "Interface with link address %r does not exist anymore (its name was %r)",
                            db_interface["link_address"], db_interface["interface"],
                        )
                        continue

                    db_interface_for_real_interface = db_interfaces.by_name.get(real_interface_by_link_address["name"])
                    if db_interface_for_real_interface is not None:
                        if db_interface_for_real_interface != db_interface:
                            middleware.logger.warning(
                                "Database already has interface %r (we wanted to set that name for interface %r "
                                "because it matches its link address %r)",
                                real_interface_by_link_address["name"], db_interface["interface"],
                                db_interface["link_address"],
                            )
                        continue

                    middleware.logger.info(
                        "Interface %r is now %r (matched by link address %r)",
                        db_interface["interface"], real_interface_by_link_address["name"], db_interface["link_address"],
                    )
                    await rename_interface(middleware, db_interface, real_interface_by_link_address["name"])
                    db_interface["interface"] = real_interface_by_link_address["name"]

        # Update link addresses for interfaces in the database
        for db_interface in db_interfaces:
            real_interface = real_interfaces.by_name.get(db_interface["interface"])
            if real_interface is None:
                link_address = None
            else:
                link_address = real_interface["state"]["link_address"]

            if db_interface["link_address"] != link_address:
                middleware.logger.debug("Setting link address %r for interface %r",
                                        link_address, db_interface["interface"])
                await middleware.call("datastore.update", "network.interfaces", db_interface["id"],
                                      {"link_address": link_address}, {"prefix": "int_"})
    except Exception:
        middleware.logger.error("Unhandled exception while migrating network interfaces", exc_info=True)
