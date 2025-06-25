import errno

from pydantic_core import ValidationError

from middlewared.api.base.model import BaseModel
from middlewared.service_exception import ValidationErrors


def accept_params(model: type[BaseModel], args: list, *, exclude_unset=False, expose_secrets=True) -> list:
    """
    Accepts a list of `args` for a method call and validates it using `model`.

    Parameters are accepted in the order they are defined in the `model`.

    Returns the list of valid parameters (or raises `ValidationErrors`).

    :param model: `BaseModel` that defines method args.
    :param args: a list of method args.
    :param exclude_unset: if true, will not append default parameters to the list.
    :param expose_secrets: if false, will replace `Secret` parameters with a placeholder.
    :return: a validated list of method args.
    """
    args_as_dict = model_dict_from_list(model, args)

    dump = validate_model(model, args_as_dict, exclude_unset=exclude_unset, expose_secrets=expose_secrets)

    fields = list(model.model_fields)
    if exclude_unset:
        fields = fields[:len(args)]

    return [dump[field] for field in fields]


def model_dict_from_list(model: type[BaseModel], args: list) -> dict:
    """
    Converts a list of `args` for a method call to a dictionary using `model`.

    Parameters are accepted in the order they are defined in the `model`.

    For example, given the model that has fields `b` and `a`, and `args` equal to `[1, 2]`, it will return
    `{"b": 1, "a": 2"}`.

    :param model: `BaseModel` that defines method args.
    :param args: a list of method args.
    :return: a dictionary of method args.
    """
    if len(args) > len(model.model_fields):
        verrors = ValidationErrors()
        verrors.add("", f"Too many arguments (expected {len(model.model_fields)}, found {len(args)})", errno.EINVAL)
        raise verrors

    return {
        field: value
        for field, value in zip(model.model_fields.keys(), args)
    }


def validate_model(model: type[BaseModel], data: dict, *, exclude_unset=False, expose_secrets=True) -> dict:
    """
    Validates `data` against the `model`, sanitizes values, sets defaults.

    Raises `ValidationErrors` if any validation errors occur.

    :param model: `BaseModel` subclass.
    :param data: provided data.
    :param exclude_unset: if true, will not add default values.
    :param expose_secrets: if false, will replace `Secret` fields with a placeholder.
    :return: validated data.
    """
    try:
        instance = model(**data)
    except ValidationError as e:
        verrors = ValidationErrors()
        for error in e.errors():
            loc = list(map(str, error["loc"]))
            msg = error["msg"]

            if error["type"] == "union_tag_not_found":
                loc.append(error["ctx"]["discriminator"].strip("'"))
                msg = "Field required"

            verrors.add(".".join(loc), msg)

        raise verrors from None

    return instance.model_dump(
        context={"expose_secrets": expose_secrets},
        exclude_unset=exclude_unset,
        warnings=False,
        by_alias=True,
    )
