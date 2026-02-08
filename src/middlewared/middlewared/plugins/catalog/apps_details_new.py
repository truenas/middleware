from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from middlewared.api.current import (
    AppCertificateChoices, AppIpChoices, SystemGeneralEntry, SystemGeneralTimezoneChoices,
)
from middlewared.service import ServiceContext


class NormalizedQuestions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    timezones: SystemGeneralTimezoneChoices
    general_config: SystemGeneralEntry = Field(alias='system.general.config')
    certificates: AppCertificateChoices
    ip_choices: AppIpChoices
    gpu_choices: list[dict[str, Any]]


async def get_normalized_questions_context(context: ServiceContext) -> NormalizedQuestions:
    return NormalizedQuestions.model_validate({
        'timezones': await context.middleware.call('system.general.timezone_choices'),
        'system.general.config': await context.middleware.call('system.general.config'),
        'certificates': await context.middleware.call('app.certificate_choices'),
        'ip_choices': await context.middleware.call('app.ip_choices'),
        'gpu_choices': await context.middleware.call('app.gpu_choices_internal'),
    })
