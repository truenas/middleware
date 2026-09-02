from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    QueryOptions,
    S3AccesskeyCreate,
    S3AccesskeyCreateArgs,
    S3AccesskeyCreateResult,
    S3AccesskeyDeleteArgs,
    S3AccesskeyDeleteResult,
    S3AccesskeyEntry,
    S3AccesskeyUpdate,
    S3AccesskeyUpdateArgs,
    S3AccesskeyUpdateResult,
)
from middlewared.plugins.idmap_.idmap_constants import BASE_SYNTHETIC_DATASTORE_ID
from middlewared.service import CRUDService, CRUDServicePart, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.crypto import generate_s3_access_key, generate_s3_secret_key
from middlewared.utils.sid import sid_is_valid
from middlewared.utils.time_utils import utc_now
from middlewared.utils.types import AuditCallback

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("S3AccesskeyService",)


class S3AccesskeyModel(sa.Model):
    __tablename__ = "truenas_s3_accesskey"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(200))
    user_identifier = sa.Column(sa.String(200))
    access_key = sa.Column(sa.String(128), unique=True)
    # SigV4 derives signing keys from the secret itself, so it is stored
    # recoverable. NULL means it was lost to a config restore without the
    # secret seed and the key must be rotated
    secret = sa.Column(sa.EncryptedText(), nullable=True)
    enabled = sa.Column(sa.Boolean(), default=True)
    expiry = sa.Column(sa.Integer(), default=0)
    created_at = sa.Column(sa.DateTime())


class S3AccesskeyServicePart(CRUDServicePart[S3AccesskeyEntry]):
    _datastore = "truenas_s3.accesskey"
    _entry = S3AccesskeyEntry

    async def extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
        # user.query performs an expensive datastore extend that is not
        # needed here, so query the table directly
        users = await self.middleware.call("datastore.query", "account.bsdusers", [], {"prefix": "bsdusr_"})
        by_id: dict[int, str | None] = {x["id"]: x["username"] for x in users}

        # Keys for directory services accounts that have no SID (plain LDAP)
        # are stored by the `user.query` id synthesized from the account's
        # UID, which the local user table cannot resolve. Look each distinct
        # one up through NSS once per query.
        for row in rows:
            if not row["user_identifier"].isdigit():
                continue

            synthetic_id = int(row["user_identifier"])
            if synthetic_id < BASE_SYNTHETIC_DATASTORE_ID or synthetic_id in by_id:
                continue

            try:
                pwdobj = await self.middleware.call(
                    "user.get_user_obj", {"uid": synthetic_id - BASE_SYNTHETIC_DATASTORE_ID}
                )
            except KeyError:
                by_id[synthetic_id] = None
            else:
                by_id[synthetic_id] = pwdobj["pw_name"]

        return {"by_id": by_id, "by_sid": {}, "now": utc_now(naive=False)}

    async def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        user_identifier = data["user_identifier"]
        expiry = data.pop("expiry")

        data.update({"username": None, "local": True, "expires_at": None})
        if user_identifier.isdigit():
            data["user_identifier"] = int(user_identifier)
            # Ids at or above the synthetic base belong to directory services accounts.
            data["local"] = data["user_identifier"] < BASE_SYNTHETIC_DATASTORE_ID
            data["username"] = context["by_id"].get(data["user_identifier"])
        elif sid_is_valid(user_identifier):
            data["local"] = False
            if (username := context["by_sid"].get(user_identifier)) is None:
                resp = await self.middleware.call("idmap.convert_sids", [user_identifier])
                if entry := resp["mapped"].get(user_identifier):
                    username = entry["name"]
                    # there may be several keys for the same SID
                    context["by_sid"][user_identifier] = username

            if username:
                data["username"] = username

        if expiry:
            data["expires_at"] = datetime.fromtimestamp(expiry, UTC)

        # Only ENABLED renders as usable. The order puts what needs an
        # administrator first.
        if not data["secret"]:
            data["status"] = "SECRET_LOST"
        elif data["username"] is None:
            data["status"] = "USER_MISSING"
        elif not data["enabled"]:
            data["status"] = "DISABLED"
        elif data["expires_at"] is not None and data["expires_at"] <= context["now"]:
            data["status"] = "EXPIRED"
        else:
            data["status"] = "ENABLED"

        return data

    def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        out = data.copy()
        if "expires_at" in out:
            if (expires_at := out.pop("expires_at")) is None:
                out["expiry"] = 0
            else:
                out["expiry"] = int(expires_at.timestamp())

        # extend() converts a digit user_identifier to int; coerce back to
        # str so the SQLA String column stays consistent on round trip.
        if isinstance(out.get("user_identifier"), int):
            out["user_identifier"] = str(out["user_identifier"])

        for key in ("username", "local", "status", "rotate"):
            out.pop(key, None)

        return out

    async def _validate(
        self,
        schema_name: str,
        name: str,
        expires_at: datetime | None,
        verrors: ValidationErrors,
        id_: int | None = None,
    ) -> None:
        if await self.middleware.call("datastore.query", self._datastore, [["name", "=", name], ["id", "!=", id_]]):
            verrors.add(f"{schema_name}.name", "name must be unique")

        if expires_at is not None and utc_now(naive=False) > expires_at:
            verrors.add(f"{schema_name}.expires_at", "Expiration date is in the past")

    async def do_create(self, data: S3AccesskeyCreate) -> S3AccesskeyEntry:
        verrors = ValidationErrors()
        await self._validate("s3_accesskey_create", data.name, data.expires_at, verrors)

        users = await self.middleware.call("user.query", [["username", "=", data.username]])
        if not users:
            verrors.add("s3_accesskey_create.username", "User does not exist.")

        if data.access_key is not None and await self.middleware.call(
            "datastore.query", self._datastore, [["access_key", "=", data.access_key]]
        ):
            verrors.add("s3_accesskey_create.access_key", "access_key must be unique")

        verrors.check()

        user = users[0]
        if user["local"]:
            user_identifier = str(user["id"])
        elif user["sid"]:
            user_identifier = user["sid"]
        else:
            # DS but no SID; fall back to the synthesized DB id (derived from the UID)
            user_identifier = str(user["id"])

        # an omitted Secret field arrives as None rather than Secret(None)
        secret = data.secret.get_secret_value() if data.secret is not None else None

        # the service half of the plugin re-renders the credentials file
        # from the s3.accesskey.post_create/post_update/post_delete hooks
        # CRUDService fires for every mutation
        return await self._create(
            {
                "name": data.name,
                "user_identifier": user_identifier,
                "access_key": data.access_key or generate_s3_access_key(),
                "secret": secret or generate_s3_secret_key(),
                "enabled": data.enabled,
                "expires_at": data.expires_at,
                "created_at": utc_now(),
            }
        )

    async def do_update(self, audit_callback: AuditCallback, id_: int, data: S3AccesskeyUpdate) -> S3AccesskeyEntry:
        old = await self.get_instance(id_)
        audit_callback(old.name)

        rotate = data.model_dump(exclude_unset=True).get("rotate", False)
        new = old.updated(data)

        verrors = ValidationErrors()
        await self._validate("s3_accesskey_update", new.name, new.expires_at, verrors, id_=id_)
        verrors.check()

        update = new.model_dump(context={"expose_secrets": True}, exclude={"id", "created_at"})
        if rotate:
            update["secret"] = generate_s3_secret_key()

        return await self._update(id_, update)

    async def do_delete(self, audit_callback: AuditCallback, id_: int) -> None:
        entry = await self.get_instance(id_)
        audit_callback(entry.name)

        await self._delete(id_)


class S3AccesskeyService(CRUDService[S3AccesskeyEntry]):
    class Config:
        namespace = "s3.accesskey"
        cli_namespace = "service.s3.accesskey"
        entry = S3AccesskeyEntry
        role_prefix = "SHARING_S3"
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = S3AccesskeyServicePart(self.context)

    async def query(
        self, filters: list[Any] | None = None, options: dict[str, Any] | None = None
    ) -> list[S3AccesskeyEntry] | S3AccesskeyEntry | int:
        return await self._svc_part.query(filters or [], QueryOptions(**(options or {})))

    async def get_instance(self, id_: int, options: dict[str, Any] | None = None) -> S3AccesskeyEntry:
        return await self._svc_part.get_instance(id_, extra=(options or {}).get("extra"))

    @api_method(
        S3AccesskeyCreateArgs,
        S3AccesskeyCreateResult,
        audit="Create S3 access key",
        audit_extended=lambda data: data["name"],
        check_annotations=True,
    )
    async def do_create(self, data: S3AccesskeyCreate) -> S3AccesskeyEntry:
        """
        Create an S3 access key.

        An access key is the SigV4 credential pair a client signs S3 requests
        with. It belongs to a local or directory services account, and the S3
        service runs that key's requests as the account. It can never
        authenticate to the TrueNAS API. The access key id and the secret are
        generated unless supplied. The secret stays readable to administrators
        holding ``SHARING_S3_WRITE``.
        """
        return await self._svc_part.do_create(data)

    @api_method(
        S3AccesskeyUpdateArgs,
        S3AccesskeyUpdateResult,
        audit="Update S3 access key",
        audit_callback=True,
        check_annotations=True,
    )
    async def do_update(self, audit_callback: AuditCallback, id_: int, data: S3AccesskeyUpdate) -> S3AccesskeyEntry:
        """
        Update S3 access key ``id``.

        Specify ``rotate: true`` to generate a new secret under the same access
        key id. The account an access key belongs to cannot be changed.
        """
        return await self._svc_part.do_update(audit_callback, id_, data)

    @api_method(
        S3AccesskeyDeleteArgs,
        S3AccesskeyDeleteResult,
        audit="Delete S3 access key",
        audit_callback=True,
        check_annotations=True,
    )
    async def do_delete(self, audit_callback: AuditCallback, id_: int) -> Literal[True]:
        """
        Delete S3 access key ``id``.
        """
        await self._svc_part.do_delete(audit_callback, id_)
        return True
