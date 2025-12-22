import inspect
from types import NoneType
from typing import Annotated, Any, Self, Union, get_args, get_origin

from pydantic import BaseModel as PydanticBaseModel, ConfigDict, Secret, create_model, Field, model_serializer
from pydantic._internal._decorators import Decorator, PydanticDescriptorProxy
from pydantic._internal._model_construction import ModelMetaclass
from pydantic.json_schema import SkipJsonSchema
from pydantic.main import ModelT
from pydantic.types import SecretType
from pydantic_core import SchemaSerializer, core_schema

from middlewared.api.base.types.string import SECRET_VALUE, LongStringWrapper
from middlewared.utils.lang import undefined


__all__ = ["BaseModel", "ForUpdateMetaclass", "query_result", "query_result_item", "added_event_model",
           "changed_event_model", "removed_event_model", "single_argument_args", "single_argument_result",
           "NotRequired", "model_subset"]


class _NotRequired:...


NotRequired = _NotRequired()
"""Use as the default value for fields that may be excluded from the model."""
_SERIALIZER_NAME = "serializer"
"""Reserved name for model serializers `_not_required_serializer` and `_for_update_serializer`."""


def _serialize_secret(value: Secret[SecretType], info: core_schema.SerializationInfo) -> SecretType | str:
    """
    Return the hidden value if "expose_secrets" was passed to `model_dump`. Otherwise, return the redaction string.
    """
    if isinstance(info.context, dict) and info.context.get("expose_secrets") is True:
        return_val = value.get_secret_value()
        if isinstance(return_val, LongStringWrapper):
            return_val = return_val.value
        return return_val
    else:
        # always serialize Secret as if info.mode="json" (never return a Secret object)
        return SECRET_VALUE


# Lifted from `pydantic.Secret`. We only change the serializer function, `_serialize_secret`.
Secret.__pydantic_serializer__ = SchemaSerializer(
    core_schema.any_schema(
        serialization=core_schema.plain_serializer_function_ser_schema(
            _serialize_secret,
            info_arg=True,
            when_used='always',
        )
    )
)


@model_serializer(mode="wrap")
def _not_required_serializer(self: "BaseModel", serializer: core_schema.SerializerFunctionWrapHandler):
    """Exclude all fields that are set to `NotRequired`."""
    return {
        k: v
        for k, v in serializer(self).items()
        if v is not NotRequired
    }


@model_serializer(mode="wrap")
def _for_update_serializer(self: "BaseModel", serializer: core_schema.SerializerFunctionWrapHandler):
    if self is undefined:
        # Can happen if `ForUpdateMetaclass` models are nestsed. Defer serialization to the outer model.
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


def _apply_model_serializer(cls: type["BaseModel"], model_serializer: PydanticDescriptorProxy):
    """Update a model's custom model serializer.

    As per pydantic's current implementation, it is not possible for a model to have more than one functional model
    serializer. If `cls` already has a functional model serializer, it will be replaced with the new one.

    """
    setattr(cls, _SERIALIZER_NAME, model_serializer.wrapped)
    cls.__pydantic_decorators__.model_serializers = {
        _SERIALIZER_NAME: Decorator.build(
            cls,
            cls_var_name=_SERIALIZER_NAME,
            shim=model_serializer.shim,
            info=model_serializer.decorator_info
        )
    }
    cls.model_rebuild(force=True)


def _annotate_not_required(annotation: type[Any] | None):
    if get_origin(annotation) is Secret:
        new_annotation = Secret[get_args(annotation)[0] | _NotRequired]
    else:
        new_annotation = annotation | _NotRequired

    return new_annotation


class _BaseModelMetaclass(ModelMetaclass):
    """Any `BaseModel` subclass that uses the `NotRequired` default value on any of its fields receives the appropriate
    model serializer."""
    # FIXME: In the future we want to set defaults on all fields
    # that are not required. Remove this metaclass at that time.

    def __new__(mcls, name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        cls = super().__new__(mcls, name, bases, namespace, **kwargs)

        has_not_required = False
        for field in cls.model_fields.values():
            if field.default is NotRequired:
                # Update annotation of any field with a default of `NotRequired` since fields
                # are serialized according to their annotation, not their value.
                field.annotation = _annotate_not_required(field.annotation)
                has_not_required = True

        if has_not_required:
            # If any field has a default of `NotRequired`, apply the serializer to the model.
            _apply_model_serializer(cls, _not_required_serializer)

        return cls


class ForUpdateMetaclass(_BaseModelMetaclass):
    """
    Using this metaclass on a model will change all of its fields default values to `undefined`.
    Such a model might be instantiated with any subset of its fields, which can be useful to validate request bodies
    for requests with PATCH semantics.
    """

    def __new__(mcls, name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        cls = ModelMetaclass.__new__(mcls, name, bases, namespace, **kwargs)

        for field in cls.model_fields.values():
            # We want to back `default` and `default_factory` so that `model_subset` can later use them.
            # However, `field` (an instance of `FieldInfo`) has `__slots__` which prevents us from adding new
            # attributes like `_original_default` and `_original_default_factory`.
            # What we do instead is create a hackish `default_factory` function that returns `undefined` as it should,
            # but if a second argument is passed, and it is `True` (only `model_subset` does that) then we return
            # the original `default` and `default_factory` values.
            default_factory = ForUpdateMetaclass._default_factory(field.default, field.default_factory)
            # Set defaults of all fields to `undefined`.
            # New defaults do not apply until model is rebuilt in `_apply_model_serializer`.
            field.default = undefined
            field.default_factory = default_factory

        _apply_model_serializer(cls, _for_update_serializer)
        return cls

    @staticmethod
    def _default_factory(default, default_factory):
        def f(data=None, return_original_default=False):
            if return_original_default:
                return default, default_factory

            return undefined

        return f


class BaseModel(PydanticBaseModel, metaclass=_BaseModelMetaclass):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_max_length=1024,
        use_attribute_docstrings=True,
        arbitrary_types_allowed=True,
    )

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        for k, v in cls.model_fields.items():
            if get_origin(v.annotation) is Union:
                for option in get_args(v.annotation):
                    if get_origin(option) is Secret:
                        def dump(t):
                            return str(t).replace("typing.", "").replace("middlewared.api.base.types.base.", "")

                        raise TypeError(
                            f"Model {cls.__name__} has field {k} defined as {dump(v.annotation)}. {dump(option)} "
                            "cannot be a member of an Optional or a Union, please make the whole field Private."
                        )
            if not v.description and (parent_field := cls.__base__.model_fields.get(k)):
                v.description = parent_field.description

    @classmethod
    def schema_model_fields(cls):
        return {
            field.alias or name: field
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

    def updated(self, value: "BaseModel") -> Self:
        """
        Returns an updated version of this model using All the fields that are present in the `value` model and are not
        `undefined`.
        :param value: model to update from.
        :return: updated version of this model.
        """
        update = {}
        for field in value.model_fields.keys():
            field_value = getattr(value, field)
            if field_value is undefined:
                continue

            update[field] = field_value

        return self.model_copy(update=update)


def single_argument_args(name: str):
    """
    Model class decorator used to define an arguments model for a method that accepts a single dictionary argument.

    :param name: name for that single argument.
    :return: a model class that consists of unique `name` field that is represented by a class being decorated.
        Class name will be preserved.
    """
    def wrapper(klass: type[BaseModel]) -> type[BaseModel]:
        if any(field.is_required() for field in klass.model_fields.values()):
            factory = None
        else:
            # All fields have defaults so we don't have to require the single argument
            factory = klass

        model = create_model(
            klass.__name__,
            __base__=(BaseModel,),
            __module__=klass.__module__,
            **{name: Annotated[klass, Field(default_factory=factory, description=f"{klass.__name__} parameters.")]},
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
        result=Annotated[klass, Field(description=f"{klass_name} return fields.")],
    )
    if issubclass(klass, BaseModel):
        model.from_previous = klass.from_previous
        model.to_previous = klass.to_previous
    return model


def query_result(item: type[PydanticBaseModel], name: str | None = None) -> type[BaseModel]:
    ResultItem = query_result_item(item)
    return create_model(
        name or item.__name__.removesuffix("Entry") + "QueryResult",
        __base__=(BaseModel,),
        __module__=item.__module__,
        result=Annotated[list[ResultItem] | ResultItem | int, Field()],
    )


def query_result_item(item: type[ModelT]) -> type[ModelT]:
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
        id=Annotated[item.model_fields["id"].annotation, Field()],
        fields=Annotated[item, Field()],
    )


def changed_event_model(item):
    return create_model(
        item.__name__.removesuffix("Entry") + "ChangedEvent",
        __base__=(BaseModel,),
        __module__=item.__module__,
        id=Annotated[item.model_fields["id"].annotation, Field()],
        fields=Annotated[item, Field()],
    )


def removed_event_model(item):
    return create_model(
        item.__name__.removesuffix("Entry") + "RemovedEvent",
        __base__=(BaseModel,),
        __module__=item.__module__,
        id=Annotated[item.model_fields["id"].annotation, Field()],
    )


def model_subset(base: type[BaseModel], fields: list[str]) -> type[BaseModel]:
    """Create a model that is a copy of `base` but only has `fields` fields."""
    model = create_model(
        base.__name__ + "Subset",
        __base__=(BaseModel,),
        __module__=base.__module__,
        **{
            field.alias or field_name: Annotated[field.annotation, field]
            for field_name, field in [
                (field, base.model_fields[field])
                for field in fields
            ]
        }
    )

    rebuild = False
    for field in model.model_fields.values():
        # Restore values backed up by `ForUpdateMetaclass` (if it was present)
        try:
            field.default, field.default_factory = field.default_factory({}, True)
        except TypeError:
            pass
        else:
            rebuild = True

    if rebuild:
        model.model_rebuild(force=True)

    return model
