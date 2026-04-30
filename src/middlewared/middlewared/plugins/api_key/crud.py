from __future__ import annotations

from base64 import b64decode
from datetime import UTC, datetime
import errno
from typing import TYPE_CHECKING, Any

import truenas_pyfilter as _tf

from middlewared.api.current import (
    ApiKeyCreate,
    ApiKeyEntry,
    ApiKeyEntryWithKey,
    ApiKeyScramData,
    ApiKeyUpdate,
)
from middlewared.service import CallError, CRUDServicePart, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.auth import LEGACY_API_KEY_USERNAME
from middlewared.utils.crypto import generate_api_key_auth_data, generate_string
from middlewared.utils.filter_list import compile_filters, compile_options
from middlewared.utils.sid import sid_is_valid
from middlewared.utils.time_utils import utc_now

from .internal import (
    api_key_privilege_check,
    check_status,
    validate_api_key_data,
)

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.utils.types import AuditCallback


_ADMIN_UID_FILTER = compile_filters([["uid", "=", 950]])
_ADMIN_UID_GET_OPTS = compile_options({"get": True})

RAW_KEY_SZ = 64


class APIKeyModel(sa.Model):
    __tablename__ = "account_api_key"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(200))
    user_identifier = sa.Column(sa.String(200))
    iterations = sa.Column(sa.Integer())
    salt = sa.Column(sa.EncryptedText())
    server_key = sa.Column(sa.EncryptedText())
    stored_key = sa.Column(sa.EncryptedText())
    created_at = sa.Column(sa.DateTime())
    expiry = sa.Column(sa.Integer())
    revoked_reason = sa.Column(sa.Text(), nullable=True)


class ApiKeyServicePart(CRUDServicePart[ApiKeyEntry]):
    _datastore = "account.api_key"
    _entry = ApiKeyEntry

    async def extend_context(
        self,
        rows: list[dict[str, Any]],
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        # user.query performs an expensive datastore extend that we do not
        # need here (e.g. 2FA status), so query the table directly.
        users = await self.middleware.call("datastore.query", "account.bsdusers", [], {"prefix": "bsdusr_"})

        by_id: dict[int, str] = {x["id"]: x["username"] for x in users}

        # Convert legacy keys into the appropriate local administrator account.
        if result := _tf.tnfilter(users, filters=_ADMIN_UID_FILTER, options=_ADMIN_UID_GET_OPTS):
            root_name = result[0]["username"]
        else:
            root_name = "root"

        return {
            "by_id": by_id,
            "by_sid": {},
            "now": utc_now(naive=False),
            "root_name": root_name,
        }

    async def extend(
        self,
        data: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        * modify `user_identifier` (change type to int if digit, otherwise
          keep as string)
        * remove `expiry`
        * add `username` - resolved from `user_identifier`
        * add `local`
        * add `expires_at` - derived from `expiry`
        * add `revoked` - derived from `expiry`
        """
        user_identifier = data["user_identifier"]
        expiry = data.pop("expiry")

        data.update(
            {
                "username": None,
                "local": True,
                "expires_at": None,
                "revoked": False,
            }
        )
        if user_identifier.isdigit():
            # If we can't resolve the ID then the account was probably deleted
            # and we didn't quite get to clean up yet.
            data["user_identifier"] = int(user_identifier)
            data["username"] = context["by_id"].get(data["user_identifier"])
        elif user_identifier == LEGACY_API_KEY_USERNAME:
            # This may be magic string designating a migrated API key
            data["username"] = context["root_name"]
        elif sid_is_valid(user_identifier):
            if (username := context["by_sid"].get(user_identifier)) is None:
                resp = await self.middleware.call("idmap.convert_sids", [user_identifier])
                if entry := resp["mapped"].get(user_identifier):
                    username = entry["name"]
                    # Feed SID we looked up back into our extend context
                    # Because there may be multiple keys for same SID value
                    context["by_sid"][user_identifier] = username

            if username:
                data["username"] = username
        else:
            # Something wildly invalid got written, but we can't
            # write a log message here (queried too frequently).
            data["username"] = None
            data["local"] = True

        if data["username"] is None:
            # prevent keys we can't resolve from being written
            data["revoked"] = True
            data["revoked_reason"] = "User does not exist"

        match expiry:
            case -1:
                # key has been forcibly revoked
                data["revoked"] = True
            case 0 | None:
                # zero value indicates never expires
                pass
            case _:
                data["expires_at"] = datetime.fromtimestamp(expiry, UTC)

        return data

    def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        out = data.copy()
        if "expires_at" in out:
            if (expires_at := out.pop("expires_at")) is None:
                out["expiry"] = 0
            else:
                out["expiry"] = int(expires_at.timestamp())

        if out.get("revoked"):
            out["expiry"] = -1

        # extend() converts a digit user_identifier to int; coerce back to
        # str so the SQLA String column stays consistent on round trip.
        if isinstance(out.get("user_identifier"), int):
            out["user_identifier"] = str(out["user_identifier"])

        for key in ("username", "revoked", "local", "client_key"):
            out.pop(key, None)

        return out

    async def do_create(self, app: App | None, data: ApiKeyCreate) -> ApiKeyEntryWithKey:
        if (await self.middleware.call("system.security.config"))["enable_gpos_stig"]:
            raise CallError(
                "Changes to API keys are not permitted in GPOS STIG mode",
                errno.EACCES,
            )

        # Privilege errors come first so we don't leak information.
        api_key_privilege_check(app, data.username, "api_key.create")

        verrors = ValidationErrors()
        await validate_api_key_data(
            self,
            self._datastore,
            "api_key_create",
            data.model_dump(),
            verrors,
        )
        users = await self.middleware.call(
            "user.query",
            [["username", "=", data.username]],
        )
        if not users:
            verrors.add("api_key_create", "User does not exist.")
        elif not users[0]["roles"]:
            verrors.add("api_key_create", "User lacks privilege role membership.")

        verrors.check()

        user = users[0]
        if user["local"]:
            user_identifier = str(user["id"])
        elif user["sid"]:
            user_identifier = user["sid"]
        else:
            # DS but no SID; fall back to synthesized DB id (derived from UID)
            user_identifier = str(user["id"])

        raw_key = generate_string(string_size=RAW_KEY_SZ)
        auth_data = await self.to_thread(generate_api_key_auth_data, raw_key)

        ds_data: dict[str, Any] = {
            "name": data.name,
            "user_identifier": user_identifier,
            "created_at": utc_now(),
            "expires_at": data.expires_at,
            **auth_data,
        }
        entry = await self._create(ds_data)
        await self.middleware.call("etc.generate", "pam")

        with_key = ApiKeyEntryWithKey(
            **entry.model_dump(context={"expose_secrets": True}),
            key=f"{entry.id}-{raw_key}",
            client_key=auth_data["client_key"],
        )
        return with_key

    async def do_update(
        self,
        app: App | None,
        audit_callback: AuditCallback,
        id_: int,
        data: ApiKeyUpdate,
    ) -> ApiKeyEntryWithKey | ApiKeyEntry:
        if (await self.middleware.call("system.security.config"))["enable_gpos_stig"]:
            raise CallError(
                "Changes to API keys are not permitted in GPOS STIG mode",
                errno.EACCES,
            )

        old = await self.get_instance(id_)
        audit_callback(old.name)

        api_key_privilege_check(app, old.username or "", "api_key.update")

        update_dict = data.model_dump(exclude_unset=True)
        reset = update_dict.pop("reset", False)

        merged = old.model_dump(context={"expose_secrets": True})
        merged.update(update_dict)

        verrors = ValidationErrors()
        await validate_api_key_data(
            self,
            self._datastore,
            "api_key_update",
            merged,
            verrors,
            id_=id_,
        )
        verrors.check()

        if not reset:
            entry = await self._update(id_, merged)
            await self.middleware.call("etc.generate", "pam")
            return entry

        raw_key = generate_string(string_size=RAW_KEY_SZ)
        auth_data = await self.to_thread(generate_api_key_auth_data, raw_key)
        merged.update(auth_data)
        merged["revoked"] = False

        entry = await self._update(id_, merged)
        await self.middleware.call("etc.generate", "pam")
        await check_status(self)
        return ApiKeyEntryWithKey(
            **entry.model_dump(context={"expose_secrets": True}),
            key=f"{entry.id}-{raw_key}",
            client_key=auth_data["client_key"],
        )

    async def do_delete(
        self,
        app: App | None,
        audit_callback: AuditCallback,
        id_: int,
    ) -> None:
        entry = await self.get_instance(id_)
        audit_callback(entry.name)

        api_key_privilege_check(app, entry.username or "", "api_key.delete")

        await self._delete(id_)
        await self.middleware.call("etc.generate", "pam")
        await check_status(self)

    async def convert_raw_key(self, raw_key: str) -> ApiKeyScramData:
        verrors = ValidationErrors()
        key_id = 0
        key_data = ""
        salt: bytes | None = None

        # The plaintext is stripped before pattern matching to be tolerant of
        # paste artifacts.
        raw_key = raw_key.strip()
        try:
            key_id_str, key_data = raw_key.split("-", 1)
            key_id = int(key_id_str)
        except ValueError:
            verrors.add("api_key_convert_raw_key", "Not a valid raw API key")

        if not verrors:
            if key_id <= 0:
                verrors.add("api_key_convert_raw_key", "Invalid key id")

            if len(key_data) != RAW_KEY_SZ:
                verrors.add("api_key_convert_raw_key", "Unexpected key size.")

            key_info = await self.query([["id", "=", key_id]])
            if not key_info:
                verrors.add("api_key_convert_raw_key", "Key does not exist.")
            elif key_info[0].revoked:
                verrors.add("api_key_convert_raw_key", "Key is revoked.")
            else:
                salt = b64decode(key_info[0].salt.get_secret_value())

        verrors.check()

        scram = await self.to_thread(generate_api_key_auth_data, key_data, salt_in=salt)
        return ApiKeyScramData(api_key_id=key_id, **scram)
