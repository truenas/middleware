from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from middlewared.api import api_method
from middlewared.api.current import (
    S3AccesskeyCreate,
    S3AccesskeyCreateArgs,
    S3AccesskeyCreateResult,
    S3AccesskeyDeleteArgs,
    S3AccesskeyDeleteResult,
    S3AccesskeyEntry,
    S3AccesskeyUpdate,
    S3AccesskeyUpdateArgs,
    S3AccesskeyUpdateResult,
    UserGetUserObj,
)
from middlewared.plugins.idmap_.idmap_constants import BASE_SYNTHETIC_DATASTORE_ID
from middlewared.service import CRUDServicePart, GenericCRUDService, ValidationErrors, private
import middlewared.sqlalchemy as sa
from middlewared.utils.crypto import generate_s3_access_key, generate_s3_secret_key
from middlewared.utils.sid import sid_is_valid
from middlewared.utils.time_utils import utc_now
from middlewared.utils.types import AuditCallback

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("S3AccesskeyService",)


def _assume_utc(value: datetime | None) -> datetime | None:
    """Treat a naive expiry as UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class S3AccesskeyModel(sa.Model):
    __tablename__ = "truenas_s3_accesskey"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(200))
    user_identifier = sa.Column(sa.String(200))
    access_key = sa.Column(sa.String(128), unique=True)
    # SigV4 needs the secret itself, so it is stored recoverable. NULL means it was lost to a config restore.
    secret = sa.Column(sa.EncryptedText(), nullable=True)
    enabled = sa.Column(sa.Boolean())
    expiry = sa.Column(sa.Integer())
    created_at = sa.Column(sa.DateTime())
    # unix seconds, reported by the S3 service. 0 means never used
    last_used = sa.Column(sa.Integer(), default=0)
    manage_buckets = sa.Column(sa.Boolean(), default=False)


class S3AccesskeyServicePart(CRUDServicePart[S3AccesskeyEntry]):
    _datastore = "truenas_s3.accesskey"
    _datastore_sql_filters = frozenset(("id", "name", "access_key", "enabled", "manage_buckets"))
    _entry = S3AccesskeyEntry

    async def extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
        # query the table directly: user.query's extend is expensive
        users = await self.middleware.call("datastore.query", "account.bsdusers", [], {"prefix": "bsdusr_"})
        by_id: dict[int, str | None] = {x["id"]: x["username"] for x in users}

        # directory accounts without a SID are keyed by the synthesized
        # user.query id. Resolve those through NSS.
        for row in rows:
            if not row["user_identifier"].isdigit():
                continue

            synthetic_id = int(row["user_identifier"])
            if synthetic_id < BASE_SYNTHETIC_DATASTORE_ID or synthetic_id in by_id:
                continue

            try:
                pwdobj = await self.call2(
                    self.s.user.get_user_obj,
                    UserGetUserObj(uid=synthetic_id - BASE_SYNTHETIC_DATASTORE_ID),
                )
            except KeyError:
                by_id[synthetic_id] = None
            else:
                by_id[synthetic_id] = pwdobj.pw_name

        return {"by_id": by_id, "by_sid": {}, "now": utc_now(naive=False)}

    async def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        user_identifier = data["user_identifier"]
        expiry = data.pop("expiry")
        last_used = data.pop("last_used")

        data.update({"username": None, "local": True, "expires_at": None})
        # 0 is a key the S3 service has never accepted a request for
        data["last_used_at"] = datetime.fromtimestamp(last_used, UTC) if last_used else None
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

        # only ENABLED renders as usable
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
            if (expires_at := _assume_utc(out.pop("expires_at"))) is None:
                out["expiry"] = 0
            else:
                out["expiry"] = int(expires_at.timestamp())

        # keep user_identifier a str for the String column
        if isinstance(out.get("user_identifier"), int):
            out["user_identifier"] = str(out["user_identifier"])

        # last_used_at is only written by report_usage
        for key in ("username", "local", "status", "rotate", "last_used_at"):
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
        expires_at = _assume_utc(expires_at)
        if await self.middleware.call("datastore.query", self._datastore, [["name", "=", name], ["id", "!=", id_]]):
            verrors.add(f"{schema_name}.name", "name must be unique")

        if expires_at is not None and utc_now(naive=False) > expires_at:
            verrors.add(f"{schema_name}.expires_at", "Expiration date is in the past")

    async def _validate_manage_buckets(self, schema_name: str, username: str | None, verrors: ValidationErrors) -> None:
        """The account must hold `SHARING_S3_WRITE` for a key with
        `manage_buckets`. Roles come from `privilege.roles_for_user`, which also
        covers directory services accounts."""
        if username is None:
            verrors.add(
                f"{schema_name}.manage_buckets",
                "This access key belongs to an account that no longer exists, so it cannot manage buckets.",
            )
            return
        roles = await self.call2(self.s.privilege.roles_for_user, username)
        if "SHARING_S3_WRITE" not in roles:
            verrors.add(
                f"{schema_name}.manage_buckets",
                f"Account {username!r} does not hold the SHARING_S3_WRITE role, so a key of theirs cannot manage "
                "buckets. Grant the account a privilege that includes it, or leave manage_buckets off.",
            )

    async def do_create(self, data: S3AccesskeyCreate) -> S3AccesskeyEntry:
        verrors = ValidationErrors()
        await self._validate("s3_accesskey_create", data.name, data.expires_at, verrors)

        users = await self.call2(self.s.user.query, [["username", "=", data.username]])
        if not users:
            verrors.add("s3_accesskey_create.username", "User does not exist.")
        elif users[0].uid == 0:
            # a root-owned key is restrained by no permission or grant
            verrors.add(
                "s3_accesskey_create.username",
                "An access key may not belong to root. Give the key an account that owns only what it should "
                "reach.",
            )

        if data.access_key is not None and await self.middleware.call(
            "datastore.query", self._datastore, [["access_key", "=", data.access_key]]
        ):
            verrors.add("s3_accesskey_create.access_key", "access_key must be unique")

        if data.manage_buckets:
            await self._validate_manage_buckets("s3_accesskey_create", data.username, verrors)

        verrors.check()

        user = users[0]
        if user.local:
            user_identifier = str(user.id)
        elif user.sid:
            user_identifier = user.sid
        else:
            # DS but no SID; fall back to the synthesized DB id (derived from the UID)
            user_identifier = str(user.id)

        # an omitted Secret field arrives as None rather than Secret(None)
        secret = data.secret.get_secret_value() if data.secret is not None else None

        # the post_create/post_update/post_delete hooks re-render the credentials file
        return await self._create(
            {
                "name": data.name,
                "user_identifier": user_identifier,
                "access_key": data.access_key or generate_s3_access_key(),
                "secret": secret or generate_s3_secret_key(),
                "enabled": data.enabled,
                "expires_at": data.expires_at,
                "created_at": utc_now(),
                "manage_buckets": data.manage_buckets,
            }
        )

    async def do_update(self, audit_callback: AuditCallback, id_: int, data: S3AccesskeyUpdate) -> S3AccesskeyEntry:
        old = await self.get_instance(id_)
        audit_callback(old.name)

        rotate = data.model_dump(exclude_unset=True).get("rotate", False)
        new = old.updated(data)

        verrors = ValidationErrors()
        await self._validate("s3_accesskey_update", new.name, new.expires_at, verrors, id_=id_)
        # checked when the flag is turned on, not on every update
        if "manage_buckets" in data.model_fields_set and new.manage_buckets:
            await self._validate_manage_buckets("s3_accesskey_update", old.username, verrors)
        verrors.check()

        update = new.model_dump(expose_secrets=True, exclude={"id", "created_at"})
        if rotate:
            update["secret"] = generate_s3_secret_key()

        return await self._update(id_, update)

    async def do_delete(self, audit_callback: AuditCallback, id_: int) -> None:
        entry = await self.get_instance(id_)
        audit_callback(entry.name)

        await self._delete(id_)

    async def delete_for_user(self, user_id: int) -> list[int]:
        """Delete the keys of a deleted local account and return their ids."""
        rows = await self.middleware.call("datastore.query", self._datastore, [["user_identifier", "=", str(user_id)]])
        for row in rows:
            await self.middleware.call("datastore.delete", self._datastore, row["id"])
            self.middleware.send_event("s3.accesskey.query", "REMOVED", id=row["id"])
        return [row["id"] for row in rows]


class S3AccesskeyService(GenericCRUDService[S3AccesskeyEntry]):
    class Config:
        namespace = "s3.accesskey"
        cli_namespace = "service.s3.accesskey"
        entry = S3AccesskeyEntry
        role_prefix = "SHARING_S3"
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = S3AccesskeyServicePart(self.context)

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

    @private
    async def delete_for_user(self, user_id: int) -> list[int]:
        return await self._svc_part.delete_for_user(user_id)

    @private
    async def report_usage(self, used: list[dict[str, Any]]) -> int:
        """Record when each access key was last used. Called by the S3 service
        over its unix socket. Each entry is `{"access_key": str, "last_used":
        <unix seconds>}`. A stored value only moves forward. Unknown keys are
        skipped. Returns the number of rows changed."""
        rows = await self.middleware.call(
            "datastore.query", self._svc_part._datastore, [], {"select": ["id", "access_key", "last_used"]}
        )
        by_key = {row["access_key"]: row for row in rows}
        changed = 0
        for entry in used:
            row = by_key.get(entry["access_key"])
            if row is None or row["last_used"] >= entry["last_used"]:
                continue
            await self.middleware.call(
                "datastore.update", self._svc_part._datastore, row["id"], {"last_used": entry["last_used"]}
            )
            changed += 1
        return changed
