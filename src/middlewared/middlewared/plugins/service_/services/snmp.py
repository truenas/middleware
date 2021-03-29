from .base import SimpleService


class SNMPService(SimpleService):
    name = "snmp"

    etc = ["snmpd"]

    freebsd_rc = "snmpd"
    freebsd_pidfile = "/var/run/net_snmpd.pid"

    systemd_unit = "snmpd"

    async def systemd_extra_units(self):
        return ["snmp-agent"]

    async def _start_freebsd(self):
        await super()._start_freebsd()
        await self._freebsd_service("snmp-agent", "start")

    async def _stop_freebsd(self):
        await self._freebsd_service("snmp-agent", "stop")
        await super()._stop_freebsd()

    async def _start_linux(self):
        await super()._start_linux()
        await self._systemd_unit("snmp-agent", "start")

    async def _stop_linux(self):
        await self._systemd_unit("snmp-agent", "stop")
        await super()._stop_linux()
