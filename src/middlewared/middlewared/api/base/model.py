from collections.abc import Callable
import inspect
from types import NoneType
from typing import Annotated, Any, Literal, Self, get_args, get_origin

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, Secret, create_model, model_serializer
from pydantic._internal._decorators import Decorator, PydanticDescriptorProxy
from pydantic._internal._model_construction import ModelMetaclass
from pydantic.fields import FieldInfo
from pydantic.json_schema import SkipJsonSchema
from pydantic.main import IncEx, ModelT
from pydantic.types import SecretType
from pydantic_core import SchemaSerializer, core_schema

from middlewared.api.base.types.string import SECRET_VALUE
from middlewared.utils.lang import Undefined, undefined
from middlewared.utils.typing_ import is_union

__all__ = ["DumpableModel", "BaseModel", "ForUpdateMetaclass",
           "query_result", "query_result_from_item", "query_result_item",
           "added_event_model", "changed_event_model", "removed_event_model",
           "single_argument_args", "single_argument_result",
           "NotRequired", "model_subset",
           "convert_model"]


class _NotRequired:
    pass


NotRequired = _NotRequired()
"""Use as the default value for fields that may be excluded from the model."""
_SERIALIZER_NAME = "serializer"
"""Reserved name for model serializers `_not_required_serializer` and `_for_update_serializer`."""


def _serialize_secret(value: Secret[SecretType], info: core_schema.SerializationInfo) -> SecretType | str:
    """
    Return the hidden value if "expose_secrets" was passed to `model_dump`. Otherwise, return the redaction string.
    """
    if isinstance(info.context, dict) and info.context.get("expose_secrets") is True:
        return value.get_secret_value()
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
def _not_required_serializer(
    self: "BaseModel",
    serializer: core_schema.SerializerFunctionWrapHandler,
) -> dict[str, Any]:
    """Exclude all fields that are set to `NotRequired`."""
    return {
        k: v
        for k, v in serializer(self).items()
        if v is not NotRequired
    }


@model_serializer(mode="wrap")
def _for_update_serializer(
    self: "BaseModel",
    serializer: core_schema.SerializerFunctionWrapHandler,
) -> dict[str, Any] | Undefined:
    if self is undefined:  # type: ignore[comparison-overlap]
        # Can happen if `ForUpdateMetaclass` models are nestsed. Defer serialization to the outer model.
        return self  # type: ignore[return-value]

    aliases = {field.alias or name: name for name, field in self.model_fields.items()}

    return {
        k: v
        for k, v in serializer(self).items()
        if (
            (getattr(self, aliases[k]) != undefined) if k in aliases and hasattr(self, aliases[k])
            else v != undefined
        )
    }


def _apply_model_serializer(cls: type["BaseModel"], model_serializer: PydanticDescriptorProxy[Any]) -> None:
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
            info=model_serializer.decorator_info,  # type: ignore[arg-type]
        )
    }
    cls.model_rebuild(force=True)


def _annotate_not_required(annotation: Any | None, metadata: tuple[Any, ...] = ()) -> Any:
    if get_origin(annotation) is Secret:
        inner = get_args(annotation)[0]
        if metadata:
            inner = Annotated[inner, *metadata]
        new_annotation: Any = Secret[inner | _NotRequired]  # type: ignore[valid-type]
    else:
        if metadata:
            annotation = Annotated[annotation, *metadata]
        new_annotation = annotation | _NotRequired

    return new_annotation


class _BaseModelMetaclass(ModelMetaclass):
    """Any `BaseModel` subclass that uses the `NotRequired` default value on any of its fields receives the appropriate
    model serializer."""
    # FIXME: In the future we want to set defaults on all fields
    # that are not required. Remove this metaclass at that time.

    def __new__(mcls, name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any) -> type:
        cls = super().__new__(mcls, name, bases, namespace, **kwargs)

        has_not_required = False
        for field in cls.model_fields.values():  # type: ignore[attr-defined]
            if field.default is NotRequired:
                # Update annotation of any field with a default of `NotRequired` since fields
                # are serialized according to their annotation, not their value.
                # Field metadata (e.g. `MaxLen`) is folded into the inner annotation so the
                # constraint applies to the typed arm of the union rather than only to the
                # union as a whole — otherwise the model config's `str_max_length` wins for
                # the bare `str` arm.
                field.annotation = _annotate_not_required(field.annotation, field.metadata)
                field.metadata = []
                has_not_required = True

        if has_not_required:
            # If any field has a default of `NotRequired`, apply the serializer to the model.
            _apply_model_serializer(cls, _not_required_serializer)  # type: ignore[arg-type]

        return cls


class ForUpdateMetaclass(_BaseModelMetaclass):
    """
    Using this metaclass on a model will change all of its fields default values to `undefined`.
    Such a model might be instantiated with any subset of its fields, which can be useful to validate request bodies
    for requests with PATCH semantics.
    """

    def __new__(mcls, name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any) -> type:
        cls = ModelMetaclass.__new__(mcls, name, bases, namespace, **kwargs)

        for field in cls.model_fields.values():  # type: ignore[attr-defined]
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

        _apply_model_serializer(cls, _for_update_serializer)  # type: ignore[arg-type]
        return cls

    @staticmethod
    def _default_factory(default: Any, default_factory: Any) -> Any:
        def f(data: Any = None, return_original_default: bool = False) -> Any:
            if return_original_default:
                return default, default_factory

            return undefined

        return f


class DumpableModel(PydanticBaseModel):
    def model_dump(  # type: ignore[override]
        self,
        *,
        mode: Literal["json", "python"] = "python",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: dict[str, Any] | None = None,
        by_alias: bool = True,  # pydantic default is `False`
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = False,  # pydantic default is `True`
        serialize_as_any: bool = False,
        expose_secrets: bool = False,
    ) -> dict[str, Any]:
        """
        Usage docs: https://docs.pydantic.dev/2.10/concepts/serialization/#modelmodel_dump

        Re-implementation of the original `model_dump` function to change some default values.

        `expose_secrets`: new parameter. If `False`, will replace `Secret` fields with a placeholder.
        """
        if isinstance(context, dict) and "expose_secrets" in context:
            raise ValueError(
                "Do not specify `expose_secrets` via `context`; use explicit `expose_secrets` parameter instead."
            )

        return super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            context={**(context or {}), "expose_secrets": expose_secrets},
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
            serialize_as_any=serialize_as_any,
        )


class BaseModel(DumpableModel, metaclass=_BaseModelMetaclass):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_max_length=1024,
        arbitrary_types_allowed=True,
        # FIXME: for pydantic 2.11 use:
        # validate_by_name=True,
        # validate_by_alias=True,
        populate_by_name=True,
    )

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        for k, v in cls.model_fields.items():
            if is_union(get_origin(v.annotation)):
                for option in get_args(v.annotation):
                    if get_origin(option) is Secret:
                        def dump(t: Any) -> str:
                            return str(t).replace("typing.", "").replace("middlewared.api.base.types.base.", "")

                        raise TypeError(
                            f"Model {cls.__name__} has field {k} defined as {dump(v.annotation)}. {dump(option)} "
                            "cannot be a member of an Optional or a Union, please make the whole field Private."
                        )
            if not v.description and (parent_field := cls.__base__.model_fields.get(k)):  # type: ignore[union-attr]
                v.description = parent_field.description

    @classmethod
    def schema_model_fields(cls) -> dict[str, FieldInfo]:
        return {
            field.alias or name: field
            for name, field in cls.model_fields.items()
            if not any(isinstance(metadata, SkipJsonSchema) for metadata in field.metadata)  # type: ignore[misc]
        }

    @classmethod
    def from_previous(cls, value: Any) -> Any:
        """
        Converts model value from a preceding API version to this API version. `value` can be modified in-place.
        :param value: value of the same model in the preceding API version.
        :return: value in this API version.
        """
        return value

    @classmethod
    def to_previous(cls, value: Any) -> Any:
        """
        Converts model value from this API version to a preceding API version. `value` can be modified in-place.
        :param value: value in this API version.
        :return: value of the same model in the preceding API version.
        """
        return value

    def model_dump(  # type: ignore[override]
        self,
        *,
        mode: Literal["json", "python"] = "python",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: dict[str, Any] | None = None,
        by_alias: bool = True,  # pydantic default is `False`
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = False,  # pydantic default is `True`
        serialize_as_any: bool = False,
        expose_secrets: bool = False,
    ) -> dict[str, Any]:
        """
        Usage docs: https://docs.pydantic.dev/2.10/concepts/serialization/#modelmodel_dump

        Re-implementation of the original `model_dump` function to change some default values.

        `expose_secrets`: new parameter. If `False`, will replace `Secret` fields with a placeholder.
        """
        if isinstance(context, dict) and "expose_secrets" in context:
            raise ValueError(
                "Do not specify `expose_secrets` via `context`; use explicit `expose_secrets` parameter instead."
            )

        return super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            context={**(context or {}), "expose_secrets": expose_secrets},
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
            serialize_as_any=serialize_as_any,
        )

    def updated(self, value: "BaseModel") -> Self:
        """
        Returns an updated version of this model using All the fields that are present in the `value` model and are not
        `undefined`.
        :param value: model to update from.
        :return: updated version of this model.
        """
        update = {}
        for field in value.model_fields.keys():
            if not hasattr(self, field):
                continue

            field_value = getattr(value, field)
            if field_value is undefined:
                continue

            update[field] = field_value

        return self.model_copy(update=update)


def single_argument_args(name: str) -> Callable[[type[BaseModel]], type[BaseModel]]:
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

        model = create_model(  # type: ignore[call-overload]
            klass.__name__,
            __base__=(BaseModel,),
            __module__=klass.__module__,
            **{
                name: Annotated[
                    klass,
                    Field(
                        default_factory=factory,  # type: ignore[arg-type]
                        description=f"{klass.__name__} parameters.",
                    ),
                ]
            },
        )
        model.from_previous = klass.from_previous
        model.to_previous = klass.to_previous
        return model  # type: ignore[no-any-return]

    return wrapper


def single_argument_result(klass: type | None, klass_name: str | None = None) -> type[BaseModel]:
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
        __module__=module_name,  # type: ignore[arg-type]
        result=Annotated[klass, Field(description=f"{klass_name} return fields.")],
    )
    if issubclass(klass, BaseModel):
        model.from_previous = klass.from_previous  # type: ignore[method-assign]
        model.to_previous = klass.to_previous  # type: ignore[method-assign]
    return model


def query_result(item: type[PydanticBaseModel], name: str | None = None) -> type[BaseModel]:
    return query_result_from_item(query_result_item(item), name or item.__name__.removesuffix("Entry") + "QueryResult")


def query_result_from_item(item: type[PydanticBaseModel], name: str) -> type[BaseModel]:
    if item.__normalize_as__ != item:  # type: ignore[attr-defined]
        result = Annotated[
            list[item.__normalize_as__] |  # type: ignore[name-defined]
            item.__normalize_as__ |  # type: ignore[name-defined]
            list[item] |  # type: ignore[valid-type]
            item |  # type: ignore[valid-type]
            int,
            Field()
        ]
    else:
        result = Annotated[  # type: ignore[assignment,misc]
            list[item] |  # type: ignore[valid-type]
            item |
            int,
            Field()
        ]


    return create_model(
        name,
        __base__=(BaseModel,),
        __module__=item.__module__,
        result=result,
    )


def query_result_item(item: type[ModelT]) -> type[ModelT]:
    # All fields must be non-required since we can query subsets of fields
    result = create_model(
        item.__name__.removesuffix("Entry") + "QueryResultItem",
        __base__=(item,),
        __module__=item.__module__,
        __cls_kwargs__={"metaclass": ForUpdateMetaclass},
    )
    result.__normalize_as__ = item  # type: ignore[attr-defined]
    item.__query_result_item__ = result  # type: ignore[attr-defined]
    return result


def added_event_model(item: type[BaseModel]) -> type[BaseModel]:
    return create_model(
        item.__name__.removesuffix("Entry") + "AddedEvent",
        __base__=(BaseModel,),
        __module__=item.__module__,
        id=Annotated[item.model_fields["id"].annotation, Field()],
        fields=Annotated[item, Field()],
    )


def changed_event_model(item: type[BaseModel]) -> type[BaseModel]:
    return create_model(
        item.__name__.removesuffix("Entry") + "ChangedEvent",
        __base__=(BaseModel,),
        __module__=item.__module__,
        id=Annotated[item.model_fields["id"].annotation, Field()],
        fields=Annotated[item, Field()],
    )


def removed_event_model(item: type[BaseModel]) -> type[BaseModel]:
    return create_model(
        item.__name__.removesuffix("Entry") + "RemovedEvent",
        __base__=(BaseModel,),
        __module__=item.__module__,
        id=Annotated[item.model_fields["id"].annotation, Field()],
    )


def model_subset(base: type[BaseModel], fields: list[str]) -> type[BaseModel]:
    """Create a model that is a copy of `base` but only has `fields` fields."""
    model = create_model(  # type: ignore[call-overload]
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

    return model  # type: ignore[no-any-return]


def convert_model[E: BaseModel](src: BaseModel, type_: type[E]) -> E:
    return type_.model_validate({name: getattr(src, name) for name in type_.model_fields})
