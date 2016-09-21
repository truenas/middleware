from datetime import datetime
from dateutil.parser import parse

import json


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if type(obj) is datetime:
            return {'$date': str(obj)}
        return super(JSONEncoder, self).default(obj)


def object_hook(obj):
    if len(obj) == 1:
        if '$date' in obj:
            return parse(obj['$date'])
    return obj


def dump(obj, fp, **kwargs):
    return json.dump(obj, fp, cls=JSONEncoder, **kwargs)


def dumps(obj, **kwargs):
    return json.dumps(obj, cls=JSONEncoder, **kwargs)


def loads(obj, **kwargs):
    return json.loads(obj, object_hook=object_hook, **kwargs)
