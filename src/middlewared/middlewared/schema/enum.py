from .exceptions import Error


class EnumMixin:

    def __init__(self, *args, **kwargs):
        self.enum = kwargs.pop('enum', None)
        super(EnumMixin, self).__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if self.enum is None:
            return value
        if value is None and self.null:
            return value
        if not isinstance(value, (list, tuple)):
            tmp = [value]
        else:
            tmp = value
        for v in tmp:
            if v not in self.enum:
                raise Error(self.name, f'Invalid choice: {value}')
        return value
