import re

__all__ = ["RegexString"]


class RegexString:
    def __init__(self, *args):
        self.re = re.compile(*args)

    def __eq__(self, other):
        return isinstance(other, str) and self.re.fullmatch(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return f"<RegexString {self.re}>"
