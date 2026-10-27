from __future__ import annotations

from middlewared.async_validators import check_path_resides_within_volume
from middlewared.service import ServiceContext, ValidationErrors
from middlewared.utils.service.path import check_path_service_write_allowed


async def validate_path_field(context: ServiceContext, verrors: ValidationErrors, schema: str, path: str) -> None:
    await check_path_resides_within_volume(verrors, context.middleware, schema, path)
    await check_path_service_write_allowed(verrors, context.middleware, schema, path, beneath=False)
