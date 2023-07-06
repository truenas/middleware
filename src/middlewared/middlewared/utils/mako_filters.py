import json as _json
import textwrap

from markdown import markdown as _markdown
from markdown.extensions.codehilite import CodeHiliteExtension


def indent(value):
    return textwrap.indent(value, " " * 8)


def json(value):
    return _json.dumps(value, indent=True)


def markdown(value):
    if not value:
        return value
    return _markdown(value, extensions=[CodeHiliteExtension(noclasses=True)])
