from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.service import ValidationErrors
from middlewared.utils.crypto import check_unixhash, generate_nt_hash, sha512_crypt
from middlewared.utils.security import check_password_complexity

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

__all__ = (
    "crypted_password",
    "password_security_validate",
    "set_password_hashes",
    "unixhash_is_valid",
)


def crypted_password(cleartext: str) -> str:
    return sha512_crypt(cleartext)


def unixhash_is_valid(unixhash: str | None) -> bool:
    return unixhash not in ("x", "*")


def set_password_hashes(data: dict[str, Any]) -> None:
    """Replace the cleartext ``password`` key in `data` with the hashes the datastore stores."""
    if "password" not in data:
        return

    password = data.pop("password")
    if password:
        data["unixhash"] = crypted_password(password)
        data["smbhash"] = generate_nt_hash(password)
    else:
        data["unixhash"] = "*"
        data["smbhash"] = "*"


async def password_security_validate(
    context: ServiceContext,
    schema: str,
    verrors: ValidationErrors,
    password: str,
    password_history: list[str] | None,
    password_field: str = "password",
) -> None:
    # NOTE: min_password_age is *not* validated here because the system administator needs
    # to be able to reset passwords in case the user forgets theirs
    sec = await context.call2(context.s.system.security.config)
    field = f"{schema}.{password_field}"
    if sec.password_complexity_ruleset:
        unmet_rules = check_password_complexity(sec.password_complexity_ruleset, password)
        if unmet_rules:
            verrors.add(
                field,
                "The specified password does not meet minimum complexity requirements. "
                f"The following character types are absent: {', '.join(unmet_rules)}",
            )

    if sec.min_password_length and len(password) < sec.min_password_length:
        verrors.add(
            field,
            "The specified password is too short. The minimum password length "
            f"is {sec.min_password_length} characters.",
        )

    if password_history and sec.password_history_length:
        # the most recent hashes are at end of list and so we reverse order when evaluating whether there
        # is a repeat in the password history
        for idx, unix_hash in enumerate(reversed(password_history)):
            if idx >= sec.password_history_length:
                # History may be longer than currently configured history length
                break

            if check_unixhash(password, unix_hash):
                verrors.add(
                    field,
                    "The security configuration of the TrueNAS server requires a password "
                    f"that does not match any of the last {sec.password_history_length} "
                    "passwords for this account.",
                )
