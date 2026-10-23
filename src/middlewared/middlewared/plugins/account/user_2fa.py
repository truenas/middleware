from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Any

import pyotp

from middlewared.api.base import BaseModel
from middlewared.api.current import (
    QueryOptions,
    TwofactorOptions,
    UserEntry,
    UserGetUserObj,
    UserRenew2faSecret,
    UserTwofactorConfigEntry,
)
from middlewared.service import CallError
from middlewared.service.ha_synchronization import (
    ControlServiceAction,
    HaSynchronizationActions,
    HaSynchronizationBaseAction,
    ha_synchronization,
)
from middlewared.utils import ProductName
from middlewared.utils.privilege import app_credential_full_admin_or_user

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.service import ServiceContext

__all__ = (
    "UserProvisioningUriArgs",
    "UserProvisioningUriResult",
    "UserTwofactorConfigArgs",
    "UserTwofactorConfigResult",
    "provisioning_uri",
    "renew_2fa_secret",
    "translate_username",
    "twofactor_config",
    "unset_2fa_secret",
)


class UserProvisioningUriArgs(BaseModel):
    username: str


class UserProvisioningUriResult(BaseModel):
    result: str


class UserTwofactorConfigArgs(BaseModel):
    username: str


class UserTwofactorConfigResult(BaseModel):
    result: UserTwofactorConfigEntry


async def translate_username(context: ServiceContext, username: str) -> UserEntry:
    """Translate `username` to a user object."""
    try:
        user = await context.call2(context.s.user.get_user_obj, UserGetUserObj(username=username))
    except KeyError:
        raise CallError(f"User {username!r} does not exist", errno.ENOENT)

    return await context.call2(
        context.s.user.query,
        [["username", "=", user.pw_name]],
        QueryOptions(get=True),
    )


async def _get_user_config(context: ServiceContext, user: UserEntry) -> dict[str, Any]:
    config: dict[str, Any] = await context.middleware.call(
        "auth.twofactor.get_user_config",
        user.id if user.local else user.sid,
        user.local,
    )
    return config


async def _provisioning_uri(context: ServiceContext, username: str, user_twofactor_config: dict[str, Any]) -> str:
    uri: str = pyotp.totp.TOTP(
        user_twofactor_config["secret"],
        interval=user_twofactor_config["interval"],
        digits=user_twofactor_config["otp_digits"],
    ).provisioning_uri(
        f"{username}-{await context.middleware.call('system.hostname')}@{ProductName.PRODUCT_NAME}",
        "TrueNAS",
    )
    return uri


async def provisioning_uri(context: ServiceContext, username: str) -> str:
    user = await translate_username(context, username)
    user_twofactor_config = await _get_user_config(context, user)
    if not user_twofactor_config["secret"]:
        raise CallError(f"{user.username!r} user does not have two factor authentication configured")

    return await _provisioning_uri(context, username, user_twofactor_config)


async def twofactor_config(context: ServiceContext, username: str) -> UserTwofactorConfigEntry:
    user = await translate_username(context, username)
    user_twofactor_config = await _get_user_config(context, user)
    uri: str | None
    if user_twofactor_config["secret"]:
        uri = await _provisioning_uri(context, username, user_twofactor_config)
    else:
        uri = None

    return UserTwofactorConfigEntry(
        provisioning_uri=uri,
        secret_configured=bool(user_twofactor_config["secret"]),
        interval=user_twofactor_config["interval"],
        otp_digits=user_twofactor_config["otp_digits"],
    )


async def unset_2fa_secret(context: ServiceContext, username: str, force: bool) -> None:
    user = await translate_username(context, username)
    twofactor_auth = await _get_user_config(context, user)
    if not twofactor_auth["exists"]:
        # This will only happen for AD users and we don't have a db record for them until they configure 2fa
        # in this case we don't do anything and the secret is already unset
        return

    async with ha_synchronization(
        # We need to regenerate the users.oath file in order to remove 2FA requirement for the user
        HaSynchronizationActions(context, [ControlServiceAction("RELOAD", "user")]),
        force,
    ):
        await context.middleware.call(
            "datastore.update",
            "account.twofactor_user_auth",
            twofactor_auth["id"],
            {
                "secret": None,
            },
        )


async def renew_2fa_secret(
    context: ServiceContext,
    app: App,
    username: str,
    twofactor_options: TwofactorOptions,
    force: bool,
) -> UserRenew2faSecret:
    if not app_credential_full_admin_or_user(app, username):
        raise CallError(
            f"{username}: currently authenticated credential may not renew two-factor authentication for this user.",
            errno.EPERM,
        )

    user = await translate_username(context, username)
    twofactor_auth = await _get_user_config(context, user)

    # Add some sanity checks here
    # The sanity check is only for local users because they should always have a db record in our 2fa
    # table. For AD users, we don't have a db record for them until they configure 2fa explicitly.
    if user.local and not twofactor_auth["exists"]:
        raise CallError(f"Unable to locate two factor authentication configuration for {username!r} user")

    secret = await context.middleware.call("auth.twofactor.generate_base32_secret")

    actions: list[HaSynchronizationBaseAction] = []
    if (await context.middleware.call("auth.twofactor.config"))["services"]["ssh"]:
        # This needs to be reloaded so that user's new secret can be reflected in sshd configuration
        actions.append(ControlServiceAction("RELOAD", "ssh"))

    actions.append(ControlServiceAction("RELOAD", "user"))

    options = twofactor_options.model_dump()
    async with ha_synchronization(HaSynchronizationActions(context, actions), force):
        if twofactor_auth["exists"]:
            await context.middleware.call(
                "datastore.update",
                "account.twofactor_user_auth",
                twofactor_auth["id"],
                {
                    "secret": secret,
                    **options,
                },
            )
        else:
            await context.middleware.call(
                "datastore.insert",
                "account.twofactor_user_auth",
                {
                    "secret": secret,
                    "user": None,
                    "user_sid": user.sid,
                    **options,
                },
            )

    user_entry = await translate_username(context, username)
    return UserRenew2faSecret(
        **user_entry.model_dump(expose_secrets=True),
        twofactor_config=await twofactor_config(context, username),
    )
