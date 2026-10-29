import logging

import pytest

from middlewared.api.current import SystemSecurityEntry
from middlewared.plugins.security.validate import validate_security
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ServiceContext, ValidationError

DEFAULTS = dict(
    id=1,
    enable_fips=False,
    enable_gpos_stig=False,
    min_password_age=None,
    max_password_age=None,
    password_complexity_ruleset=None,
    min_password_length=None,
    password_history_length=None,
)


@pytest.mark.parametrize(
    "key,old_value,new_value,refused",
    [
        ("min_password_length", 12, 10, False),
        ("min_password_length", 10, 12, True),
        ("enable_fips", True, True, False),
        ("enable_fips", False, True, True),
    ],
)
@pytest.mark.asyncio
async def test_loosening_passes_tightening_refused_unlicensed(key, old_value, new_value, refused):
    m = Middleware()
    m.services.system.security.info.fips_available = lambda: False
    old = SystemSecurityEntry.model_construct(**DEFAULTS | {key: old_value})
    new = SystemSecurityEntry.model_construct(**DEFAULTS | {key: new_value})
    context = ServiceContext(m, logging.getLogger("test"))

    if refused:
        with pytest.raises(ValidationError) as exc:
            await validate_security(context, False, old, new, [])
        assert exc.value.attribute == f"system_security_update.{key}"
    else:
        await validate_security(context, False, old, new, [])
