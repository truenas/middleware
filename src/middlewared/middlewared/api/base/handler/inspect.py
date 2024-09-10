import typing

from middlewared.api.base import BaseModel


def model_field_is_model(model) -> type[BaseModel] | None:
    """
    Return` model` if it is an API model. Otherwise, returns `None`.
    :param model: potentially, API model.
    :return: `model` or `None`
    """
    if isinstance(model, type) and issubclass(model, BaseModel):
        return model


def model_field_is_list_of_models(model) -> type[BaseModel] | None:
    """
    If` model` represents a list of API models X, then it will return that model X. Otherwise, returns `None`.
    :param model: potentially,  a model that represents a list of API models.
    :return: nested API model or `None`
    """
    if typing.get_origin(model) is list and len(args := typing.get_args(model)) == 1:
        return args[0]
