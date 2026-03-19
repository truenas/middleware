from __future__ import annotations

from middlewared.async_validators import check_path_resides_within_volume
from middlewared.service import ServiceContext, ValidationErrors


async def validate_path_field(context: ServiceContext, verrors: ValidationErrors, schema: str, path: str) -> None:
    await check_path_resides_within_volume(verrors, context.middleware, schema, path)
