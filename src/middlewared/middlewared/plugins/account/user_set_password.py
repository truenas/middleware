from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Any

from truenas_pypam import PAMCode

from middlewared.api.current import QueryOptions, UserSetPassword
from middlewared.service import CallError, ValidationErrors
from middlewared.utils.account.authenticator import AccountFlag, UserPamAuthenticator
from middlewared.utils.privilege import credential_has_full_admin
from middlewared.utils.time_utils import utc_now

from .password import password_security_validate, set_password_hashes

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.service import ServiceContext

__all__ = ("set_password",)


async def set_password(context: ServiceContext, app: App, data: UserSetPassword) -> None:
    verrors = ValidationErrors()
    credentials = app.authenticated_credentials
    if credentials is None:
        raise CallError("An unauthenticated session may not reset a password", errno.EPERM)

    is_full_admin = credential_has_full_admin(credentials)
    is_otp_login = False
    authenticated_user = None
    password_aging_override = is_full_admin

    if credentials.is_user_session:
        credential_user: dict[str, Any] = credentials.user  # type: ignore[attr-defined]
        authenticated_user = credential_user["username"]
        if AccountFlag.OTPW in credential_user["account_attributes"]:
            is_otp_login = True

        if not password_aging_override:
            if AccountFlag.PASSWORD_CHANGE_REQUIRED in credential_user["account_attributes"]:
                password_aging_override = True

    username = data.username
    password = data.new_password.get_secret_value()

    if not is_full_admin and authenticated_user != username:
        raise CallError(
            f"{username}: currently authenticated credential may not reset password for this user.",
            errno.EPERM,
        )

    entries = await context.call2(
        context.s.user.query,
        [["username", "=", username]],
        QueryOptions(extra={"additional_information": ["DS"]}),
    )
    if not entries:
        # This only happens if authenticated user has FULL_ADMIN privileges,
        # and so we're not concerned about letting admin know that username is
        # bad.
        verrors.add("user.set_password.username", f"{username}: user does not exist.")
        verrors.check()

    entry = entries[0]
    if not entry.local:
        # We don't allow resetting passwords on remote directory service.
        verrors.add("user.set_password.username", f"{username}: user is not local to the TrueNAS server.")

    if entry.password_disabled:
        verrors.add("user.set_password.username", f"{username}: password authentication disabled for user")

    if entry.locked:
        verrors.add("user.set_password.username", f"{username}: user account is locked.")

    # Accounts rejected above (directory service entries, the synthetic container root) carry no
    # stored hash and no password history, so stop here rather than let the checks below read them.
    verrors.check()

    # Require submitting password twice if this is not a full admin session
    # and does not have a one-time password.
    if not is_full_admin and not is_otp_login:
        old_password = data.old_password.get_secret_value()
        if old_password is None:
            verrors.add(
                "user.set_password.old_password",
                "FULL_ADMIN role is required in order to bypass check for current password.",
            )
        else:
            # Create a temporary PAM authenticator to verify the old password.
            # We can't use the current session's authentication context as it would fail.
            pam_hdl = UserPamAuthenticator(username=username, origin=app.origin)
            pam_resp = await context.to_thread(pam_hdl.authenticate, username, old_password)
            if pam_resp.code != PAMCode.PAM_SUCCESS:
                verrors.add("user.set_password.old_password", f"{username}: failed to validate password.")

    history = (entry.password_history.get_secret_value() or []) + [entry.unixhash.get_secret_value()]
    await password_security_validate(context, "user.set_password", verrors, password, history, "new_password")
    min_password_age = (await context.call2(context.s.system.security.config)).min_password_age

    if (
        not password_aging_override
        and min_password_age
        and entry.password_age is not None
        and entry.password_age < min_password_age
    ):
        verrors.add(
            "user.set_password.username",
            f"{username}: password changed too recently. Minimum password age is: {min_password_age}",
        )

    verrors.check()

    row = entry.model_dump(expose_secrets=True) | {"password": password}
    set_password_hashes(row)
    row["last_password_change"] = utc_now(naive=False)

    await context.middleware.call(
        "datastore.update",
        "account.bsdusers",
        row["id"],
        {
            "bsdusr_unixhash": row["unixhash"],
            "bsdusr_smbhash": row["smbhash"],
            "bsdusr_password_history": ", ".join(history),
            "bsdusr_last_password_change": int(row["last_password_change"].timestamp()),
        },
    )
    await context.middleware.call("etc.generate", "shadow")

    if row["smb"]:
        await context.middleware.call("smb.update_passdb_user", row)
