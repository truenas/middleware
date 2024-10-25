import copy
import functools
import inspect
from types import NoneType
import typing

from pydantic import BaseModel as PydanticBaseModel, ConfigDict, create_model, Field, model_serializer, Secret
from pydantic._internal._model_construction import ModelMetaclass
from pydantic.main import IncEx
from typing_extensions import Annotated

from middlewared.api.base.types.base import SECRET_VALUE
from middlewared.utils.lang import undefined


__all__ = ["BaseModel", "ForUpdateMetaclass", "query_result", "single_argument_args", "single_argument_result"]


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
                    if typing.get_origin(option) is Secret:
                        def dump(t):
                            return str(t).replace("typing.", "").replace("middlewared.api.base.types.base.", "")

                        raise TypeError(
                            f"Model {cls.__name__} has field {k} defined as {dump(v.annotation)}. {dump(option)} "
                            "cannot be a member of an Optional or a Union, please make the whole field Private."
                        )

    def model_dump(
        self,
        *,
        mode: typing.Literal['json', 'python'] | str = 'python',
        include: IncEx = None,
        exclude: IncEx = None,
        context: dict[str, typing.Any] | None = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool | typing.Literal['none', 'warn', 'error'] = True,
        serialize_as_any: bool = False,
    ) -> dict[str, typing.Any]:
        return self.__pydantic_serializer__.to_python(
            self,
            mode=mode,
            by_alias=by_alias,
            include=include,
            exclude=exclude,
            context=context,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
            serialize_as_any=serialize_as_any,
            fallback=functools.partial(self._model_dump_fallback, context),
        )

    def _model_dump_fallback(self, context, value):
        if isinstance(value, Secret):
            if context["expose_secrets"]:
                return value.get_secret_value()
            else:
                return SECRET_VALUE

        return value

    @classmethod
    def from_previous(cls, value):
        """
        Converts model value from a preceding API version to this API version. `value` can be modified in-place.
        :param value: value of the same model in the preceding API version.
        :return: value in this API version.
        """
        return value

    @classmethod
    def to_previous(cls, value):
        """
        Converts model value from this API version to a preceding API version. `value` can be modified in-place.
        :param value: value in this API version.
        :return: value of the same model in the preceding API version.
        """
        return value


class AllowExtraBaseModel(BaseModel):
    model_config = ConfigDict(
        extra="allow",  # Allow extra fields
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


def single_argument_args(name: str):
    """
    Model class decorator used to define an arguments model for a method that accepts a single dictionary argument.

    :param name: name for that single argument.
    :return: a model class that consists of unique `name` field that is represented by a class being decorated.
        Class name will be preserved.
    """
    def wrapper(klass):
        model = create_model(
            klass.__name__,
            __base__=(BaseModel,),
            __module__=klass.__module__,
            **{name: Annotated[klass, Field()]},
        )
        model.from_previous = classmethod(klass.from_previous)
        model.to_previous = classmethod(klass.to_previous)
        return model

    return wrapper


def single_argument_result(klass, klass_name=None):
    """
    Can be used as:
    * Decorator for a class. In that case, it will create a class that represents a return value for a function that
      returns a single dictionary, represented by the decorated class.
    * Standalone model generator. Will return a model class named `klass_name` that consists of a single field
      represented by `klass` (in that case, `klass` can be a primitive type).

    :param klass: class or a primitive type to create model from.
    :param klass_name: required, when being called as a standalone model generator. Returned class will have that name.
        (otherwise, the decorated class name will be preserved).
    :return: a model class that consists of unique `result` field that corresponds to `klass`.
    """
    if klass is None:
        klass = NoneType

    if klass.__module__ == "builtins":
        if klass_name is None:
            raise TypeError("You must specify class name when using `single_argument_result` for built-in types")
    else:
        klass_name = klass_name or klass.__name__

    model = create_model(
        klass_name,
        __base__=(BaseModel,),
        __module__=inspect.getmodule(inspect.stack()[1][0]),
        **{"result": Annotated[klass, Field()]},
    )
    if issubclass(klass, BaseModel):
        model.from_previous = classmethod(klass.from_previous)
        model.to_previous = classmethod(klass.to_previous)
    return model


def query_result(item):
    return create_model(
        item.__name__.removesuffix("Entry") + "QueryResult",
        __base__=(BaseModel,),
        __module__=item.__module__,
        result=Annotated[list[item] | item | int, Field()],
    )
