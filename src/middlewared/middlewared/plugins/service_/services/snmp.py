from .base import SimpleService


class SNMPService(SimpleService):
    name = "snmp"

    etc = ["snmpd"]

    systemd_unit = "snmpd"

    async def systemd_extra_units(self):
        return ["snmp-agent"]

    async def start(self):
        await super().start()
        await self._systemd_unit("snmp-agent", "start")

    async def stop(self):
        await self._systemd_unit("snmp-agent", "stop")
        await super().stop()
