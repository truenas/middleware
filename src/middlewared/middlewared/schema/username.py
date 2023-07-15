import string

from .attribute import Attribute
from .exceptions import Error


class LocalUsername(Attribute):

    def to_json_schema(self, parent=None):
        return {**self._to_json_schema_common(parent), 'type': 'string'}

    def validate(self, value):
        # see man 8 useradd, specifically the CAVEATS section
        # NOTE: we are ignoring the man page's recommendation for insistence
        # upon the starting character of a username be a lower-case letter.
        # We aren't enforcing this for maximum backwards compatibility
        val = str(value)
        val_len = len(val)
        valid_chars = string.ascii_letters + string.digits + '_' + '-' + '$' + '.'
        valid_start = string.ascii_letters + '_'
        if val_len <= 0:
            raise Error(self.name, 'Username must be at least 1 character in length')
        elif val_len > 32:
            raise Error(self.name, 'Username cannot exceed 32 characters in length')
        elif val[0] not in valid_start:
            raise Error(self.name, 'Username must start with a letter or an underscore')
        elif '$' in val and val[-1] != '$':
            raise Error(self.name, 'Username must end with a dollar sign character')
        elif any((char not in valid_chars for char in val)):
            raise Error(self.name, f'Valid characters for a username are: {", ".join(valid_chars)!r}')

        return super().validate(val)
