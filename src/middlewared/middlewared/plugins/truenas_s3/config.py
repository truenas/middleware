"""The S3 service's global configuration and the render feed."""

from __future__ import annotations

import os
from typing import Any, TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    S3BindipChoicesArgs,
    S3BindipChoicesResult,
    S3Entry,
    S3Listener,
    S3Update,
    S3UpdateArgs,
    S3UpdateResult,
    ZFSResourceQuery,
)
from middlewared.async_validators import validate_port
from middlewared.service import SystemServicePart, SystemServiceService, ValidationErrors, private
import middlewared.sqlalchemy as sa
from middlewared.utils.crypto import generate_token, ssl_uuid4

from .accesskey_crud import S3AccesskeyService
from .grants import grant_principals, label_grants, principal_names, validate_grants
from .lifecycle import render_and_apply

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("S3Service",)

OWNER_ID_SEED_BYTES = 28
"""The seed is 56 hex digits; generate_token returns hex, two per byte."""

MAX_LISTENERS = 8
"""The daemon's ceiling on listen addresses, plaintext and TLS together."""

MAX_SERVERS = 8
"""The daemon's ceiling on reactor threads, its credential broker's ring limit."""


class S3Model(sa.Model):
    __tablename__ = "services_truenas_s3"

    id = sa.Column(sa.Integer(), primary_key=True)
    listeners = sa.Column(sa.JSON(list), default=[])
    servers = sa.Column(sa.Integer(), default=1)
    certificate_id = sa.Column(sa.ForeignKey("system_certificate.id"), index=True, nullable=True)
    region = sa.Column(sa.String(120), default="")
    log_level = sa.Column(sa.String(16), default="NOTICE")
    default_audit = sa.Column(sa.JSON(list), default=[])
    default_audit_overflow = sa.Column(sa.String(16), default="DROP")
    global_grants = sa.Column(sa.JSON(list), default=[])
    # the two per-appliance identities the daemon wants stated once and never
    # moved. Generated on the first read and never exposed through the API.
    host_id = sa.Column(sa.String(64), default="")
    owner_id_seed = sa.Column(sa.String(64), default="")


class S3ConfigPart(SystemServicePart[S3Entry]):
    _datastore = "services.truenas_s3"
    _entry = S3Entry
    _service = "truenas_s3"

    async def config(self) -> S3Entry:
        # the base get-or-insert creates the row the identities are stored in
        entry = await super().config()
        await self._identity()
        return entry

    async def extend(self, data: dict[str, Any]) -> dict[str, Any]:
        if isinstance(data.get("certificate"), dict):
            data["certificate"] = data["certificate"]["id"]
        for key in ("host_id", "owner_id_seed"):
            data.pop(key, None)
        names = await principal_names(self.middleware, *grant_principals(data["global_grants"]))
        data["global_grants"] = label_grants(data["global_grants"], names)
        return data

    async def _identity(self) -> dict[str, str]:
        """host_id and owner_id_seed, generated on first use. host_id names
        the appliance in every error body; owner_id_seed is the top of every
        canonical owner id, so changing it would rewrite them all."""
        row = await self.middleware.call("datastore.config", self._datastore)
        update = {}
        if not row["host_id"]:
            update["host_id"] = str(ssl_uuid4())
        if not row["owner_id_seed"]:
            update["owner_id_seed"] = generate_token(OWNER_ID_SEED_BYTES)
        if update:
            await self.middleware.call("datastore.update", self._datastore, row["id"], update)
            row.update(update)
        return {"host_id": row["host_id"], "owner_id_seed": row["owner_id_seed"]}

    async def bindip_choices(self) -> dict[str, str]:
        # the static addresses (the VIPs on HA), the loopbacks for a
        # deployment served only from the box itself, and the wildcards
        choices = await self.middleware.call(
            "interface.ip_in_use", {"static": True, "loopback": True, "any": True, "ipv4": True, "ipv6": True}
        )
        return {d["address"]: d["address"] for d in choices}

    async def do_update(self, data: S3Update) -> S3Entry:
        old = await self.config()
        new = old.updated(data)
        verrors = ValidationErrors()

        # the base builds the entry without validating it, so a list the
        # update did not touch holds plain dicts; the ones it did hold
        # models. One shape for the checks below, whichever side it came from
        listeners = [S3Listener.model_validate(row) for row in new.model_dump()["listeners"]]
        if len(listeners) > MAX_LISTENERS:
            verrors.add("s3_update.listeners", f"The S3 service listens on at most {MAX_LISTENERS} addresses.")
        choices = await self.bindip_choices()
        seen: set[tuple[str, int]] = set()
        for i, listener in enumerate(listeners):
            if listener.address not in choices:
                verrors.add(
                    f"s3_update.listeners.{i}.address",
                    f"Cannot use {listener.address}. Please provide a valid ip address.",
                )
            # the daemon binds every entry, and the same address twice
            # would bind twice
            if (listener.address, listener.port) in seen:
                verrors.add(f"s3_update.listeners.{i}", "The same address and port may only be listed once.")
            seen.add((listener.address, listener.port))
            verrors.extend(
                await validate_port(
                    self.middleware, f"s3_update.listeners.{i}.port", listener.port, "s3", listener.address
                )
            )
        if not listeners:
            verrors.extend(await validate_port(self.middleware, "s3_update.listeners", 9000, "s3", "0.0.0.0"))
        if any(listener.tls for listener in listeners) and await self.effective_certificate(new.certificate) is None:
            verrors.add(
                "s3_update.certificate",
                "A listener served over TLS needs a certificate, and no UI certificate is set to fall back on.",
            )

        # every thread is a ring with its own pool; more than the CPUs
        # the system has serves nothing but the memory bill
        ceiling = min(os.cpu_count() or 1, MAX_SERVERS)
        if new.servers > ceiling:
            verrors.add("s3_update.servers", f"This system serves with at most {ceiling} reactor threads.")

        if new.certificate is not None:
            verrors.extend(
                await self.middleware.call(
                    "certificate.cert_services_validation", new.certificate, "s3_update.certificate", False
                )
            )

        if (new.default_audit or new.default_audit_overflow != "DROP") and not await self.audit_licensed():
            verrors.add("s3_update.default_audit", "Auditing the S3 service requires an Enterprise license.")

        await validate_grants(self.middleware, "s3_update.global_grants", new.global_grants, verrors)
        verrors.check()

        if new.certificate is not None and new.certificate != old.certificate:
            # the certificate files are rendered by the ssl group; make sure
            # they exist before the daemon is pointed at them
            await (await self.middleware.call("service.control", "START", "ssl")).wait(raise_error=True)

        update = new.model_dump(exclude={"id"})
        update["global_grants"] = [g.model_dump(exclude={"name"}) for g in new.global_grants]
        await self.middleware.call("datastore.update", self._datastore, old.id, update)
        await render_and_apply(self.middleware)
        return await self.config()

    async def audit_licensed(self) -> bool:
        # the audit trail is an Enterprise feature the daemon knows nothing
        # about: middleware withholds every audit key from the rendered
        # config on an unlicensed system. Gated on holding a license until
        # an S3 audit entitlement exists in truenas_license.
        return await self.middleware.call("system.license") is not None

    async def effective_certificate(self, cert_id: int | None) -> int | None:
        """The certificate the TLS listeners serve: the chosen one, or the
        UI's when none is chosen. One certificate to manage for the box
        unless a deployment wants otherwise."""
        if cert_id is not None:
            return cert_id
        return (await self.middleware.call("system.general.config"))["ui_certificate"]

    async def certificate_paths(self, cert_id: int | None) -> tuple[str | None, str | None]:
        if cert_id is None:
            return None, None
        try:
            await self.middleware.call("certificate.cert_services_validation", cert_id, "s3.certificate")
        except Exception:
            self.logger.warning("s3: certificate %d is not usable, serving plaintext", cert_id)
            return None, None
        cert = await self.middleware.call("certificate.query", [["id", "=", cert_id]], {"get": True})
        return cert["certificate_path"], cert["privatekey_path"]

    async def render_data(self) -> dict[str, Any]:
        """Everything the renderers need, shaped for `render.py`."""
        config = await self.config()
        identity = await self._identity()
        tls_cert, tls_key = await self.certificate_paths(await self.effective_certificate(config.certificate))
        buckets = [b.model_dump() for b in await self.middleware.call("sharing.s3.query")]
        datasets = (
            {
                row["name"]: row
                for row in await self.call2(
                    self.s.zfs.resource.query_impl,
                    ZFSResourceQuery(paths=[b["dataset"] for b in buckets], properties=["mountpoint"]),
                )
            }
            if buckets
            else {}
        )

        rendered_buckets = []
        for bucket in buckets:
            live = datasets.get(bucket["dataset"])
            rendered_buckets.append(
                {
                    **bucket,
                    "owner_label": bucket["owner"],
                    "owner_id": bucket["owner_uid"],
                    "dataset_missing": live is None,
                    "live_mountpoint": live["properties"]["mountpoint"]["value"] if live else None,
                }
            )

        return {
            "config": {
                **config.model_dump(),
                **identity,
                "tls_cert": tls_cert,
                "tls_key": tls_key,
            },
            "buckets": rendered_buckets,
            "accesskeys": [
                key.model_dump(context={"expose_secrets": True})
                for key in await self.middleware.call("s3.accesskey.query")
            ],
            "audit_licensed": await self.audit_licensed(),
        }


class S3Service(SystemServiceService[S3Entry]):
    class Config:
        service = "truenas_s3"
        service_verb = "reload"
        datastore = "services.truenas_s3"
        cli_namespace = "service.s3"
        role_prefix = "SHARING_S3"
        generic = True
        entry = S3Entry

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = S3ConfigPart(self.context)
        self.accesskey = S3AccesskeyService(middleware)

    async def config(self) -> S3Entry:
        return await self._svc_part.config()

    @api_method(S3UpdateArgs, S3UpdateResult, audit="Update S3 configuration", check_annotations=True)
    async def do_update(self, data: S3Update) -> S3Entry:
        """
        Update the S3 service configuration.

        Changing the listeners, the reactor thread count or the region
        restarts the S3 service, draining in-flight requests for up to 30
        seconds. Every other change applies with a reload, the certificate
        included: a different one, or the UI certificate changing while
        the service follows it, rotates in place.
        """
        return await self._svc_part.do_update(data)

    @api_method(S3BindipChoicesArgs, S3BindipChoicesResult, check_annotations=True)
    async def bindip_choices(self) -> dict[str, str]:
        """
        Returns the IP addresses a listener may name.
        """
        return await self._svc_part.bindip_choices()

    @private
    async def render_data(self) -> dict[str, Any]:
        return await self._svc_part.render_data()

    @private
    async def audit_licensed(self) -> bool:
        return await self._svc_part.audit_licensed()

    @private
    async def effective_certificate(self, cert_id: int | None) -> int | None:
        return await self._svc_part.effective_certificate(cert_id)

    @private
    async def reconfigure(self, force_restart: bool = False) -> str | None:
        """Re-render the S3 service's files and reload or restart it as the
        change requires. The one path every change to a bucket, grant,
        access key or account takes."""
        return await render_and_apply(self.middleware, force_restart=force_restart)
