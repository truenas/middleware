import logging
from unittest.mock import AsyncMock

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import S3Entry, S3Update
from middlewared.plugins.truenas_s3 import config as s3_config
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ServiceContext, ValidationErrors


class _Validated(Exception):
    def __init__(self, attributes):
        super().__init__(attributes)
        self.attributes = attributes


async def _stop_after_validation(middleware, field, grants, verrors):
    raise _Validated([error.attribute for error in verrors.errors])


@pytest.mark.parametrize(
    "default_audit,errors",
    [
        (["PutObject"], []),
        (["PutObject", "GetObject"], ["s3_update.default_audit"]),
    ],
)
@pytest.mark.asyncio
async def test_s3_update_audit_unchanged_passes_widened_refused(monkeypatch, default_audit, errors):
    m = Middleware()
    install_entitlements_for_column(m, LicenseFeature.S3_AUDIT, "CE+L")
    m["port.validate_port"] = lambda *args: ValidationErrors()
    part = s3_config.S3ConfigPart(ServiceContext(m, logging.getLogger("test")))
    old = S3Entry.model_construct(
        id=1,
        listeners=[],
        certificate=None,
        servers=1,
        managed_root_dataset=None,
        global_grants=[],
        default_audit=["PutObject"],
        default_audit_overflow="DROP",
    )
    monkeypatch.setattr(part, "config", AsyncMock(return_value=old))
    monkeypatch.setattr(part, "bindip_choices", AsyncMock(return_value={}))
    monkeypatch.setattr(s3_config, "validate_grants", _stop_after_validation)

    with pytest.raises(_Validated) as validated:
        await part.do_update(S3Update(default_audit=default_audit))

    assert validated.value.attributes == errors
