from pydantic_core import ValidationError

from middlewared.service_exception import CallError, ValidationErrors


def accept_params(model, args, *, exclude_unset=False, expose_secrets=True, validate=True):
    if len(args) > len(model.model_fields):
        raise CallError(f"Too many arguments (expected {len(model.model_fields)}, found {len(args)})")

    args_as_dict = {
        field: value
        for field, value in zip(model.model_fields.keys(), args)
    }

    if validate:
        try:
            instance = model(**args_as_dict)
        except ValidationError as e:
            verrors = ValidationErrors()
            for error in e.errors():
                verrors.add(".".join(map(str, error["loc"])), error["msg"])

            raise verrors from None
    else:
        instance = model.model_construct(**args_as_dict)

    if expose_secrets:
        mode = "python"
    else:
        mode = "json"

    dump = instance.model_dump(mode=mode, exclude_unset=exclude_unset, warnings=False)

    fields = list(model.model_fields)
    if exclude_unset:
        fields = fields[:len(args)]

    return [dump[field] for field in fields]
