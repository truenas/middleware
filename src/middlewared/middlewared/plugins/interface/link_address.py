from middlewared.service import private, Service


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
    def get_name(self, i):
        return i["name"]


async def setup(middleware):
    await middleware.call("interface.persist_link_addresses")
