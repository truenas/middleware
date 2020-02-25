from .base import SimpleService


class SNMPService(SimpleService):
    name = "snmp"

    etc = ["snmpd"]

    freebsd_rc = "snmpd"
    freebsd_pidfile = "/var/run/net_snmpd.pid"

    async def _start_freebsd(self):
        await self._freebsd_service("snmpd", "start")
        await self._freebsd_service("snmp-agent", "start")

    async def _stop_freebsd(self):
        await self._freebsd_service("snmp-agent", "stop")
        await self._freebsd_service("snmpd", "stop")
