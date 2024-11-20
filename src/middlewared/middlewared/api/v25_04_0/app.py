from middlewared.api.base import BaseModel, NonEmptyString

from .catalog import CatalogAppInfo


__all__ = [
    'AppCategoriesArgs', 'AppCategoriesResult', 'AppSimilarArgs', 'AppSimilarResult', 'AppAvailableResponse',
]


class AppAvailableResponse(CatalogAppInfo):
    catalog: NonEmptyString
    installed: bool
    train: NonEmptyString


class AppCategoriesArgs(BaseModel):
    pass


class AppCategoriesResult(BaseModel):
    result: list[NonEmptyString]


class AppSimilarArgs(BaseModel):
    app_name: NonEmptyString
    train: NonEmptyString


class AppSimilarResult(BaseModel):
    result: list[AppAvailableResponse]
