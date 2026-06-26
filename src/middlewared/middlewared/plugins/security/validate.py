from typing import Any

from middlewared.api.current import SystemSecurityEntry
from middlewared.plugins.failover_.enums import DisabledReasonsEnum
from middlewared.service import ServiceContext, ValidationError
from middlewared.utils.security import (
    ENTERPRISE_OPTIONS,
    GPOS_STIG_MAX_PASSWORD_AGE,
    GPOS_STIG_MIN_PASSWORD_AGE,
    GPOS_STIG_PASSWORD_COMPLEXITY,
    GPOS_STIG_PASSWORD_LENGTH,
    GPOS_STIG_PASSWORD_REUSE_LIMIT,
)


async def validate_security(
    context: ServiceContext, is_ha: bool, new: SystemSecurityEntry, ha_disabled_reasons: list[str]
) -> None:
    schema = "system_security_update.enable_fips"

    if not await context.call2(context.s.system.security.info.fips_available):
        for key in ENTERPRISE_OPTIONS:
            if not getattr(new, key):
                continue

            raise ValidationError(
                f"system_security_update.{key}",
                "This feature can only be enabled on licensed TrueNAS Enterprise systems. "
                "Please contact TrueNAS sales for more information.",
            )

    if is_ha and ha_disabled_reasons:
        bad_reasons = set(ha_disabled_reasons) - {
            DisabledReasonsEnum.LOC_FIPS_REBOOT_REQ.name,
            DisabledReasonsEnum.REM_FIPS_REBOOT_REQ.name,
            DisabledReasonsEnum.LOC_GPOSSTIG_REBOOT_REQ.name,
            DisabledReasonsEnum.REM_GPOSSTIG_REBOOT_REQ.name,
        }
        if bad_reasons:
            formatted = "\n".join([DisabledReasonsEnum[i].value for i in bad_reasons])
            raise ValidationError(
                schema, f"Security settings cannot be updated while HA is in an unhealthy state: ({formatted})"
            )


async def validate_stig(context: ServiceContext, current_cred: Any) -> None:
    # The following validation steps ensure that users have the ability to
    # manage the TrueNAS server after enabling STIG compatibility.
    two_factor = await context.middleware.call("auth.twofactor.config")
    if not two_factor["enabled"]:
        raise ValidationError(
            "system_security_update.enable_gpos_stig",
            "Two factor authentication must be globally enabled before "
            "enabling General Purpose OS STIG compatibility mode.",
        )

    if two_factor["services"]["ssh"] is False:
        raise ValidationError(
            "system_security_update.enable_gpos_stig",
            "Two factor authentication for SSH access must be enabled before "
            "enabling General Purpose OS STIG compatibility mode.",
        )

    tc_config = await context.call2(context.s.truecommand.config)
    if tc_config.enabled:
        raise ValidationError(
            "system_security_update.enable_gpos_stig",
            "TrueCommand is not supported under General Purpose OS STIG compatibility mode.",
        )

    vms = await context.middleware.call("datastore.query", "vm.vm")
    if vms:
        raise ValidationError(
            "system_security_update.enable_gpos_stig",
            "Please remove all virtual machines, as they are not supported"
            " in General Purpose OS STIG compatibility mode.",
        )

    if (await context.middleware.call("docker.config")).pool:
        raise ValidationError(
            "system_security_update.enable_gpos_stig",
            "Please disable Apps as Apps are not supported under General Purpose OS STIG compatibility mode.",
        )

    if (await context.call2(context.s.tn_connect.config)).enabled:
        raise ValidationError(
            "system_security_update.enable_gpos_stig",
            "Please disable TrueNAS Connect as it is not supported under General Purpose OS STIG compatibility mode.",
        )

    # We want to make sure that at least one local user account is usable
    # and has 2fa auth configured.
    two_factor_users = await context.middleware.call(
        "user.query", [["twofactor_auth_configured", "=", True], ["locked", "=", False], ["local", "=", True]]
    )

    if not two_factor_users:
        raise ValidationError(
            "system_security_update.enable_gpos_stig",
            "Two factor authentication tokens must be configured for users "
            "prior to enabling General Purpose OS STIG compatibility mode.",
        )

    if not any([user for user in two_factor_users if "FULL_ADMIN" in user["roles"]]):
        raise ValidationError(
            "system_security_update.enable_gpos_stig",
            "At least one local user with full admin privileges must be "
            "configured with a two factor authentication token prior to enabling "
            "General Purpose OS STIG compatibility mode.",
        )

    if current_cred and current_cred.is_user_session and "2FA" not in current_cred.user["account_attributes"]:
        # We need to do everything we can to make sure that 2FA is _actually_ working for
        # an account to which admin has access.
        raise ValidationError(
            "system_security_update.enable_gpos_stig",
            "Credential used to enable General Purpose OS STIG compatibility "
            "must have two factor authentication enabled, and have used two factor "
            "authentication for the currently-authenticated session.",
        )

    excluded_admins = [
        user["username"]
        for user in await context.middleware.call(
            "user.query",
            [
                ["immutable", "=", True],
                ["password_disabled", "=", False],
                ["locked", "=", False],
                ["unixhash", "!=", "*"],
                ["local", "=", True],
            ],
        )
    ]

    if excluded_admins:
        # For STIG compatibility, all general purpose administrative accounts,
        # e.g. 'root' and 'truenas_admin', cannot use password login.  (SRG-OS-000109-GPOS-00056)
        raise ValidationError(
            "system_security_update.enable_gpos_stig",
            "General purpose administrative accounts with password authentication are "
            "not compatible with STIG compatibility mode.  "
            f"PLEASE DISABLE PASSWORD AUTHENTICATION ON THE FOLLOWING ACCOUNTS: {', '.join(excluded_admins)}.",
        )


def validate_password_security(old: SystemSecurityEntry, new: SystemSecurityEntry) -> bool:
    """
    Performs validation of global local account security settings.

    Returns boolean indicating that we need to reload local users after applying settings.
    """
    if new.enable_gpos_stig:
        # For convenience we'll override defaults when GPOS STIG is enabled

        # SRG-OS-000073-GPOS-00041
        # GPOS STIG requires a min_password_age to be set to 1 day
        # Increasing beyond this represents a stricter standard.
        new.min_password_age = new.min_password_age or GPOS_STIG_MIN_PASSWORD_AGE

        # SRG-OS-000076-GPOS-00044
        # Operating systems must enforce a 60-day maximum password lifetime restriction.
        # Decreasing below this represents a stricter standard.
        new.max_password_age = new.max_password_age or GPOS_STIG_MAX_PASSWORD_AGE
        if new.max_password_age > GPOS_STIG_MAX_PASSWORD_AGE:
            raise ValidationError(
                "system_security_update.max_password_age",
                f"{new.max_password_age}: Maximum password age must be less than or equal to "
                f"{GPOS_STIG_MAX_PASSWORD_AGE} days in GPOS STIG compatibility mode.",
            )

        # SRG-OS-000077-GPOS-00045
        # Prohibit reuse for minimum of 5 generations
        # Increasing beyond this represents a stricter standard
        new.password_history_length = new.password_history_length or GPOS_STIG_PASSWORD_REUSE_LIMIT
        if new.password_history_length < GPOS_STIG_PASSWORD_REUSE_LIMIT:
            raise ValidationError(
                "system_security_update.password_history_length",
                "GPOS STIG compatibility requires that password reuse be limited for a minimum of five generations.",
            )

        # SRG-OS-000069-GPOS-00037
        # SRG-OS-000070-GPOS-00038
        # SRG-OS-000071-GPOS-00039
        # SRG-OS-000266-GPOS-00101
        # Passwords must contain at least one lowercase character, one lowercase character,
        # one number, and one special character.
        new.password_complexity_ruleset = new.password_complexity_ruleset or set(GPOS_STIG_PASSWORD_COMPLEXITY)
        if missing := GPOS_STIG_PASSWORD_COMPLEXITY - new.password_complexity_ruleset:
            raise ValidationError(
                "system_security_update.password_complexity_ruleset",
                f"GPOS STIG compatibility requires the following password complexity rules: {', '.join(missing)}",
            )

        new.min_password_length = new.min_password_length or GPOS_STIG_PASSWORD_LENGTH
        if new.min_password_length < GPOS_STIG_PASSWORD_LENGTH:
            raise ValidationError(
                "system_security_update.min_password_length",
                "GPOS STIG compatibility requires password lengths of at least 15 characters.",
            )

    # The following keys determine whether we need to rewrite our shadow file
    # At some point if we decide to plumb through password changes via pam / middleware
    # we can add password warn and password inactivity fields
    if old.min_password_age == new.min_password_age and old.max_password_age == new.max_password_age:
        return False

    if new.min_password_age is not None and new.max_password_age is not None:
        if new.min_password_age >= new.max_password_age:
            raise ValidationError(
                "system_security_update.min_password_age",
                "Minimum password age must be lower than the maximum password age in "
                "order to allow users to change their passwords.",
            )

    if new.max_password_age is not None and new.max_password_age < 7:
        # Setting max password age to less than 7 days runs very high risk
        # of admins accidentally locking themselves out
        raise ValidationError(
            "system_security_update.max_password_age",
            "Maximum password age may not be set to a value of less than 7 days.",
        )

    return True
