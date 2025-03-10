from middlewared.service import ValidationErrors


class SettingsHelper:
    def __init__(self):
        self.fields_validators = []

    def fields_validator(self, *names):
        def wrapper(func):
            self.fields_validators.append((names, func))
            return func

        return wrapper

    async def validate(self, plugin, schema_name, old, new):
        verrors = ValidationErrors()
        for field_names, validator in self.fields_validators:
            if any(old[k] != new[k] for k in field_names):
                child_verrors = ValidationErrors()
                await validator(plugin, child_verrors, *[new[k] for k in field_names])
                verrors.add_child(schema_name, child_verrors)

        verrors.check()
