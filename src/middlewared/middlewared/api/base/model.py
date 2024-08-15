import copy
import inspect
from types import NoneType
import typing

from pydantic import BaseModel as PydanticBaseModel, ConfigDict, create_model, Field, model_serializer
from pydantic._internal._model_construction import ModelMetaclass
from typing_extensions import Annotated

from middlewared.utils.lang import undefined
from .types.base import Private

__all__ = ["BaseModel", "ForUpdateMetaclass", "single_argument_args", "single_argument_result"]


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_max_length=1024,
    )

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: typing.Any) -> None:
        for k, v in cls.model_fields.items():
            if typing.get_origin(v.annotation) is typing.Union:
                for option in typing.get_args(v.annotation):
                    if typing.get_origin(option) is Private:
                        def dump(t):
                            return str(t).replace("typing.", "").replace("middlewared.api.base.types.base.", "")

                        raise TypeError(
                            f"Model {cls.__name__} has field {k} defined as {dump(v.annotation)}. {dump(option)} "
                            "cannot be a member of an Optional or a Union, please make the whole field Private."
                        )



class ForUpdateMetaclass(ModelMetaclass):
    """
    Using this metaclass on a model will change all of its fields default values to `undefined`.
    Such a model might be instantiated with any subset of its fields, which can be useful to validate request bodies
    for requests with PATCH semantics.
    """

    def __new__(mcls, name, bases, namespaces, **kwargs):
        skip_patching = kwargs.pop("__ForUpdateMetaclass_skip_patching", False)

        cls = super().__new__(mcls, name, bases, namespaces, **kwargs)

        if skip_patching:
            return cls

        return create_model(
            cls.__name__,
            __base__=(cls, _ForUpdateSerializerMixin),
            __module__=cls.__module__,
            __cls_kwargs__={"__ForUpdateMetaclass_skip_patching": True},
            **{
                k: _field_for_update(v)
                for k, v in cls.model_fields.items()
            },
        )


class _ForUpdateSerializerMixin(PydanticBaseModel):
    @model_serializer(mode="wrap")
    def serialize_model(self, serializer):
        return {k: v for k, v in serializer(self).items() if v != undefined}


def _field_for_update(field):
    new = copy.deepcopy(field)
    new.default = undefined
    new.default_factory = None
    return new.annotation, new


def single_argument_args(name):
    def wrapper(klass):
        return create_model(
            klass.__name__,
            __base__=(BaseModel,),
            __module__=klass.__module__,
            **{name: Annotated[klass, Field()]},
        )

    return wrapper


def single_argument_result(klass, klass_name=None):
    if klass is None:
        klass = NoneType

    if klass.__module__ == "builtins":
        if klass_name is None:
            raise TypeError("You must specify class name when using `single_argument_result` for built-in types")
    else:
        klass_name = klass_name or klass.__name__

    return create_model(
        klass_name,
        __base__=(BaseModel,),
        __module__=inspect.getmodule(inspect.stack()[1][0]),
        **{"result": Annotated[klass, Field()]},
    )
