import copy
import functools
import inspect
from types import NoneType
import typing

from pydantic import BaseModel as PydanticBaseModel, ConfigDict, create_model, Field, model_serializer, Secret
from pydantic._internal._model_construction import ModelMetaclass
from pydantic.json_schema import SkipJsonSchema
from pydantic.main import IncEx

from middlewared.api.base.types.string import SECRET_VALUE, LongStringWrapper
from middlewared.utils.lang import undefined


__all__ = ["BaseModel", "ForUpdateMetaclass", "query_result", "query_result_item", "added_event_model",
           "changed_event_model", "removed_event_model", "single_argument_args", "single_argument_result",
           "NotRequired"]


class _NotRequired:...


"""Use as the default value for fields that may be excluded from the model."""
NotRequired = _NotRequired()


class _NotRequiredMixin(PydanticBaseModel):
    @model_serializer(mode="wrap")
    def serialize_basemodel(self, serializer):
        return {
            k: v
            for k, v in serializer(self).items()
            if v is not NotRequired
        }


def _not_required_field(field):
    annotation_ = field.annotation

    if typing.get_origin(annotation_) is Secret:
        annotation_ = Secret[typing.get_args(annotation_)[0] | _NotRequired]
    else:
        annotation_ |= _NotRequired

    return (annotation_, field)


class _BaseModelMetaclass(ModelMetaclass):
    """Any BaseModel subclass that uses the NotRequired default value on any of its fields receives the appropriate
    model serializer."""
    # FIXME: In the future we want to set defaults on all fields that are not required. Remove this metaclass,
    # `_NotRequiredMixin`, and `NotRequired` at that time.

    def __new__(mcls, name, bases, namespaces, **kwargs):
        skip_patching = kwargs.pop("__BaseModelMetaclass_skip_patching", False)

        cls = super().__new__(mcls, name, bases, namespaces, **kwargs)

        if skip_patching or name == "BaseModel":
            return cls

        has_not_required = False
        updated_fields = {}
        for name, field in cls.model_fields.items():
            if getattr(field, "default", None) is NotRequired:
                has_not_required = True
                updated_fields[name] = _not_required_field(field)
            else:
                updated_fields[name] = (field.annotation, field)

        if has_not_required:
            return create_model(
                cls.__name__,
                __base__=(cls, _NotRequiredMixin),
                __module__=cls.__module__,
                __cls_kwargs__={"__BaseModelMetaclass_skip_patching": True},
                **updated_fields
            )

        return cls


class BaseModel(PydanticBaseModel, metaclass=_BaseModelMetaclass):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_max_length=1024,
        use_attribute_docstrings=True,
        arbitrary_types_allowed=True,
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
        serialize_as_any: bool = False
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
                value = value.get_secret_value()

                if isinstance(value, LongStringWrapper):
                    value = value.value

                return value
            else:
                return SECRET_VALUE

        return value

    @classmethod
    def schema_model_fields(cls):
        return {
            name: field
            for name, field in cls.model_fields.items()
            if not any(isinstance(metadata, SkipJsonSchema) for metadata in field.metadata)
        }

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


class ForUpdateMetaclass(_BaseModelMetaclass):
    """
    Using this metaclass on a model will change all of its fields default values to `undefined`.
    Such a model might be instantiated with any subset of its fields, which can be useful to validate request bodies
    for requests with PATCH semantics.
    """

    def __new__(mcls, name, bases, namespaces, **kwargs):
        skip_patching = kwargs.pop("__ForUpdateMetaclass_skip_patching", False)

        cls = ModelMetaclass.__new__(mcls, name, bases, namespaces, **kwargs)

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
    
    def mro(mcls):
        return [cls for cls in super().mro() if cls is not _NotRequiredMixin]


class _ForUpdateSerializerMixin(PydanticBaseModel):
    @model_serializer(mode="wrap")
    def serialize_model(self, serializer):
        if self is undefined:
            # Can happen if ForUpdateMetaclass models are nestsed. Defer serialization to the outer model.
            return self

        aliases = {field.alias or name: name for name, field in self.model_fields.items()}

        return {
            k: v
            for k, v in serializer(self).items()
            if (
                (getattr(self, aliases[k]) != undefined) if k in aliases and hasattr(self, aliases[k])
                else v != undefined
            )
        }


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
            **{name: typing.Annotated[klass, Field()]},
        )
        model.from_previous = klass.from_previous
        model.to_previous = klass.to_previous
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

    module = inspect.getmodule(inspect.stack()[1][0])
    if module:
        module_name = module.__name__
    else:
        module_name = None

    model = create_model(
        klass_name,
        __base__=(BaseModel,),
        __module__=module_name,
        result=typing.Annotated[klass, Field()],
    )
    if issubclass(klass, BaseModel):
        model.from_previous = klass.from_previous
        model.to_previous = klass.to_previous
    return model


def query_result(item):
    result_item = query_result_item(item)
    return create_model(
        item.__name__.removesuffix("Entry") + "QueryResult",
        __base__=(BaseModel,),
        __module__=item.__module__,
        result=typing.Annotated[list[result_item] | result_item | int, Field()],
    )


def query_result_item(item):
    # All fields must be non-required since we can query subsets of fields
    return create_model(
        item.__name__.removesuffix("Entry") + "QueryResultItem",
        __base__=(item,),
        __module__=item.__module__,
        __cls_kwargs__={"metaclass": ForUpdateMetaclass},
    )


def added_event_model(item):
    return create_model(
        item.__name__.removesuffix("Entry") + "AddedEvent",
        __base__=(BaseModel,),
        __module__=item.__module__,
        id=typing.Annotated[item.model_fields["id"].annotation, Field()],
        fields=typing.Annotated[item, Field()],
    )


def changed_event_model(item):
    return create_model(
        item.__name__.removesuffix("Entry") + "ChangedEvent",
        __base__=(BaseModel,),
        __module__=item.__module__,
        id=typing.Annotated[item.model_fields["id"].annotation, Field()],
        fields=typing.Annotated[item, Field()],
    )


def removed_event_model(item):
    return create_model(
        item.__name__.removesuffix("Entry") + "RemovedEvent",
        __base__=(BaseModel,),
        __module__=item.__module__,
        id=typing.Annotated[item.model_fields["id"].annotation, Field()],
    )
