from typing import Any, Awaitable, Callable, Concatenate

from middlewared.service import ValidationErrors

FieldsValidator = Callable[Concatenate[Any, ValidationErrors, ...], Awaitable[None]]


class SettingsHelper:
    def __init__(self) -> None:
        self.fields_validators: list[tuple[tuple[str, ...], FieldsValidator]] = []

    def fields_validator(self, *names: str) -> Callable[[FieldsValidator], FieldsValidator]:
        def wrapper(func: FieldsValidator) -> FieldsValidator:
            self.fields_validators.append((names, func))
            return func

        return wrapper

    async def validate(self, plugin: Any, schema_name: str, old: dict[str, Any], new: dict[str, Any]) -> None:
        verrors = ValidationErrors()
        for field_names, validator in self.fields_validators:
            if any(old[k] != new[k] for k in field_names):
                child_verrors = ValidationErrors()
                await validator(plugin, child_verrors, *[new[k] for k in field_names])
                verrors.add_child(schema_name, child_verrors)

        verrors.check()
