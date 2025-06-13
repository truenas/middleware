import asyncio

from middlewared.api import api_method
from middlewared.api.current import (
    SystemGeneralUiAddressChoicesArgs,
    SystemGeneralUiAddressChoicesResult,
    SystemGeneralUiCertificateChoicesArgs,
    SystemGeneralUiCertificateChoicesResult,
    SystemGeneralUiHttpsprotocolsChoicesArgs,
    SystemGeneralUiHttpsprotocolsChoicesResult,
    SystemGeneralLocalUrlArgs,
    SystemGeneralLocalUrlResult,
    SystemGeneralUiRestartArgs,
    SystemGeneralUiRestartResult,
    SystemGeneralUiV6addressChoicesArgs,
    SystemGeneralUiV6addressChoicesResult,
)
from middlewared.service import CallError, private, Service

from .utils import HTTPS_PROTOCOLS


class SystemGeneralService(Service):
    ui_allowlist = []

    class Config:
        namespace = "system.general"
        cli_namespace = "system.general"

    @api_method(
        SystemGeneralUiAddressChoicesArgs,
        SystemGeneralUiAddressChoicesResult,
        roles=["SYSTEM_GENERAL_READ"],
    )
    async def ui_address_choices(self):
        """Returns network interfaces that have statically configured
        IPv4 address(es). These addresses can be used to bind the UI
        server."""
        return {
            d["address"]: d["address"]
            for d in await self.middleware.call(
                "interface.ip_in_use",
                {"ipv4": True, "ipv6": False, "any": True, "static": True},
            )
        }

    @api_method(
        SystemGeneralUiV6addressChoicesArgs,
        SystemGeneralUiV6addressChoicesResult,
        roles=["SYSTEM_GENERAL_READ"],
    )
    async def ui_v6address_choices(self):
        """Returns network interfaces that have statically configured
        IPv6 address(es). These addresses can be used to bind the UI
        server."""
        return {
            d["address"]: d["address"]
            for d in await self.middleware.call(
                "interface.ip_in_use",
                {"ipv4": False, "ipv6": True, "any": True, "static": True},
            )
        }

    @api_method(
        SystemGeneralUiHttpsprotocolsChoicesArgs,
        SystemGeneralUiHttpsprotocolsChoicesResult,
        roles=["SYSTEM_GENERAL_READ"],
    )
    def ui_httpsprotocols_choices(self):
        """Returns available HTTPS protocols."""
        return dict(zip(HTTPS_PROTOCOLS, HTTPS_PROTOCOLS))

    @api_method(
        SystemGeneralUiCertificateChoicesArgs,
        SystemGeneralUiCertificateChoicesResult,
        roles=["SYSTEM_GENERAL_READ"]
    )
    async def ui_certificate_choices(self):
        """Return available certificates that may be used to
        bind the webserver to when connecting via HTTPS protocol."""
        return {
            i["id"]: i["name"]
            for i in await self.middleware.call(
                "certificate.query", [("cert_type_CSR", "=", False)]
            )
        }

    @api_method(
        SystemGeneralUiRestartArgs,
        SystemGeneralUiRestartResult,
        roles=["SYSTEM_GENERAL_WRITE"],
    )
    async def ui_restart(self, delay: int):
        """
        Restart HTTP server to use latest UI settings.

        HTTP server will be restarted after `delay` seconds.
        """
        event_loop = asyncio.get_event_loop()
        event_loop.call_later(
            delay,
            lambda: self.middleware.create_task(
                self.middleware.call("service.control", "RESTART", "http")
            ),
        )

    @api_method(
        SystemGeneralLocalUrlArgs,
        SystemGeneralLocalUrlResult,
        roles=["SYSTEM_GENERAL_READ"]
    )
    async def local_url(self):
        """
        Returns configured local url in the format of protocol://host:port
        """
        config = await self.middleware.call("system.general.config")
        if config["ui_certificate"]:
            protocol = "https"
            port = config["ui_httpsport"]
        else:
            protocol = "http"
            port = config["ui_port"]

        if "0.0.0.0" in config["ui_address"] or "127.0.0.1" in config["ui_address"]:
            hosts = ["127.0.0.1"]
        else:
            hosts = config["ui_address"]

        errors = []
        for host in hosts:
            try:
                reader, writer = await asyncio.wait_for(
                    self.middleware.create_task(
                        asyncio.open_connection(
                            host,
                            port=port,
                        )
                    ),
                    timeout=5,
                )
                writer.close()

                return f"{protocol}://{host}:{port}"

            except Exception as e:
                errors.append(f"{host}: {e}")

        raise CallError(
            "Unable to connect to any of the specified UI addresses:\n"
            + "\n".join(errors)
        )

    @private
    async def get_ui_urls(self):
        config = await self.middleware.call("system.general.config")
        kwargs = (
            {"static": True} if await self.middleware.call("failover.licensed") else {}
        )

        # http is always used
        http_proto = "http://"
        http_port = config["ui_port"]

        # populate https data if necessary
        https_proto = https_port = None
        if config["ui_certificate"]:
            https_proto = "https://"
            https_port = config["ui_httpsport"]

        all_ip4 = "0.0.0.0" in config["ui_address"]
        all_ip6 = "::" in config["ui_v6address"]

        urls = set()
        for i in await self.middleware.call("interface.ip_in_use", kwargs):
            http_url = http_proto + (
                i["address"] if i["type"] == "INET" else f"[{i['address']}]"
            )
            if http_port != 80:
                http_url += f":{http_port}"

            https_url = None
            if https_proto is not None:
                https_url = https_proto + (
                    i["address"] if i["type"] == "INET" else f"[{i['address']}]"
                )
                if https_port != 443:
                    https_url += f":{https_port}"

            if (i["type"] == "INET" and all_ip4) or (i["type"] == "INET6" and all_ip6):
                urls.add(http_url)
                if https_url:
                    urls.add(https_url)
            elif (
                i["address"] in config["ui_address"]
                or i["address"] in config["ui_v6address"]
            ):
                urls.add(http_url)
                if https_url:
                    urls.add(https_url)

        return sorted(urls)

    @private
    async def get_ui_allowlist(self):
        """
        We store this in a state and not read this configuration variable directly from the database so it is
        synchronized with HTTP service restarts and HTTP configuration commit/rollback works properly.
        Otherwise, changing `ui_allowlist` would immediately block/unblock new connections (we want to block/unblock
        them only after explicit HTTP service restart).
        """
        return self.ui_allowlist

    @private
    async def update_ui_allowlist(self):
        self.ui_allowlist = (await self.middleware.call("system.general.config"))[
            "ui_allowlist"
        ]


async def setup(middleware):
    await middleware.call("system.general.update_ui_allowlist")
