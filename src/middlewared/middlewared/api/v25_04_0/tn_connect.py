from middlewared.api.base import BaseModel, NonEmptyString


__all__ = [
    'TNCGetRegistrationURIArgs', 'TNCGetRegistrationURIResult',
]


class TNCGetRegistrationURIArgs(BaseModel):
    pass


class TNCGetRegistrationURIResult(BaseModel):
    result: NonEmptyString
