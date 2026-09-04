"""The S3 service's global configuration and the render feed."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import ipaddress
import os
from typing import Any, TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    S3AccesskeyEntry,
    S3BindipChoicesArgs,
    S3BindipChoicesResult,
    S3Entry,
    S3GrantEntry,
    S3Listener,
    S3Update,
    S3UpdateArgs,
    S3UpdateResult,
    SharingS3Entry,
    ZFSResourceQuery,
)
from middlewared.async_validators import validate_port
from middlewared.service import SystemServicePart, SystemServiceService, ValidationErrors, private
import middlewared.sqlalchemy as sa
from middlewared.utils.crypto import generate_token, ssl_uuid4

from .accesskey_crud import S3AccesskeyService
from .grants import grant_label, grant_principals, label_grants, principal_names, validate_grants
from .lifecycle import MISSING_ALERT, render_and_apply

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


@dataclass(frozen=True, slots=True, kw_only=True)
class RenderedGrant:
    """One [grant …] section: the heading, minus its brackets, and the row."""

    heading: str
    grant: S3GrantEntry


@dataclass(frozen=True, slots=True, kw_only=True)
class RenderedBucket:
    """A bucket beside what the render adds to it."""

    entry: SharingS3Entry
    mountpoint: str
    grants: list[RenderedGrant]


@dataclass(frozen=True, slots=True, kw_only=True)
class RenderData:
    """Everything the etc templates read, gathered once per generate."""

    config: S3Entry
    host_id: str
    owner_id_seed: str
    listen: str
    listen_tls: str
    tls_cert: str | None
    tls_key: str | None
    global_grants: list[RenderedGrant]
    buckets: list[RenderedBucket]
    accesskeys: list[S3AccesskeyEntry]
    audit_licensed: bool


def _listen_text(listeners: Sequence[S3Listener]) -> tuple[str, str]:
    """[server] listen and listen_tls: the plaintext and the TLS addresses,
    comma separated, an IPv6 address in brackets. No listener at all is
    every address on port 9000 in plaintext."""
    if not listeners:
        listeners = [S3Listener(address="0.0.0.0")]
    plain, secure = [], []
    for listener in listeners:
        ip, port = listener.address, listener.port
        text = f"[{ip}]:{port}" if isinstance(ipaddress.ip_address(ip), ipaddress.IPv6Address) else f"{ip}:{port}"
        (secure if listener.tls else plain).append(text)
    return ", ".join(plain), ", ".join(secure)


def _rendered_grants(grants: Sequence[S3GrantEntry], bucket: str) -> list[RenderedGrant]:
    """Each grant under the heading its section carries: the principal
    kind, its label (quoted, stripped of what would break the grammar) and
    the bucket, `*` for every bucket. A user and a group may share a label,
    but the same principal twice is a duplicate section the daemon refuses;
    validation keeps a list free of those, and the last one wins here as a
    backstop."""
    by_principal: dict[tuple[str, int | None], RenderedGrant] = {}
    for grant in grants:
        kind = grant.principal_type.lower()
        if kind == "everyone":
            heading = f'grant everyone "{bucket}"'
        else:
            heading = f'grant {kind} "{grant_label(grant)}" "{bucket}"'
        by_principal[(grant.principal_type, grant.xid)] = RenderedGrant(heading=heading, grant=grant)
    return list(by_principal.values())


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
        """The entry is constructed from this rather than validated, so the
        nested rows are made models here, once, and every reader past this
        point holds `S3Listener` and `S3GrantEntry`."""
        if isinstance(data.get("certificate"), dict):
            data["certificate"] = data["certificate"]["id"]
        for key in ("host_id", "owner_id_seed"):
            data.pop(key, None)
        data["listeners"] = [S3Listener.model_validate(row) for row in data["listeners"]]
        names = await principal_names(self.middleware, grant_principals(data["global_grants"]))
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

        listeners = new.listeners
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
        return await self.middleware.call("system.license") is not None

    async def effective_certificate(self, cert_id: int | None) -> int | None:
        """The certificate the TLS listeners serve: the chosen one, or the
        UI's when none is chosen. One certificate to manage for the box
        unless a deployment wants otherwise."""
        if cert_id is not None:
            return cert_id
        return (await self.middleware.call("system.general.config"))["ui_certificate"]

    async def certificate_paths(self, cert_id: int | None) -> tuple[str | None, str | None]:
        """Where the certificate's pair is rendered, or nothing when none is
        chosen. Not judged here: the daemon checks the pair at start-up and
        on every reload and refuses the deployment when it is unusable,
        which keeps a TLS listener from ever serving without it."""
        if cert_id is None:
            return None, None
        cert = await self.middleware.call("certificate.query", [["id", "=", cert_id]], {"get": True})
        return cert["certificate_path"], cert["privatekey_path"]

    async def render_data(self) -> RenderData:
        """Everything the etc templates render, gathered once per generate
        and shaped so a template only loops and prints.

        The daemon reads every file whole and one malformed value refuses
        the entire load, so what a template must never print is decided
        here: a certificate pair with no TLS listener is not rendered, a
        grant heading's label is stripped of what would break
        its grammar, and a bucket whose dataset is gone keeps its row at the
        mount point it would have, so the daemon answers 503 for it rather
        than saying it never existed. That last case raises the alert here
        too, since this is where it is seen.
        """
        config = await self.config()
        identity = await self._identity()
        tls_cert, tls_key = await self.certificate_paths(await self.effective_certificate(config.certificate))
        listen, listen_tls = _listen_text(config.listeners)
        if not listen_tls:
            tls_cert = tls_key = None

        buckets: list[SharingS3Entry] = await self.middleware.call("sharing.s3.query")
        datasets = (
            {
                row["name"]: row
                for row in await self.call2(
                    self.s.zfs.resource.query_impl,
                    ZFSResourceQuery(paths=[b.dataset for b in buckets], properties=["mountpoint"]),
                )
            }
            if buckets
            else {}
        )

        rendered_buckets = []
        for bucket in buckets:
            live = datasets.get(bucket.dataset)
            mountpoint = live["properties"]["mountpoint"]["value"] if live else None
            if not mountpoint or not mountpoint.startswith("/"):
                mountpoint = f"/mnt/{bucket.dataset}"
            if bucket.enabled and live is None:
                args = {"id": bucket.id, "name": bucket.name, "dataset": bucket.dataset}
                await self.middleware.call("alert.oneshot_create", MISSING_ALERT, args)
            else:
                await self.middleware.call("alert.oneshot_delete", MISSING_ALERT, bucket.id)
            rendered_buckets.append(
                RenderedBucket(entry=bucket, mountpoint=mountpoint, grants=_rendered_grants(bucket.grants, bucket.name))
            )

        accesskeys: list[S3AccesskeyEntry] = await self.middleware.call("s3.accesskey.query")
        for key in accesskeys:
            if key.status == "USER_MISSING" and not key.local:
                # a directory services account that does not resolve right now
                # may just be a directory that is not answering; the key renders
                # disabled until the next render finds the account again
                self.logger.warning(
                    "s3: access key %s belongs to a directory services account that does not resolve, rendered "
                    "disabled",
                    key.access_key,
                )

        return RenderData(
            config=config,
            host_id=identity["host_id"],
            owner_id_seed=identity["owner_id_seed"],
            listen=listen,
            listen_tls=listen_tls,
            tls_cert=tls_cert,
            tls_key=tls_key,
            global_grants=_rendered_grants(config.global_grants, "*"),
            buckets=rendered_buckets,
            accesskeys=accesskeys,
            audit_licensed=await self.audit_licensed(),
        )


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
    async def render_data(self) -> RenderData:
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
