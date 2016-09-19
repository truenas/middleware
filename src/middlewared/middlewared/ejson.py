import json
from datetime import datetime


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if type(obj) is datetime:
            return str(obj)
        return super(JSONEncoder, self).default(obj)


def dump(obj, fp, **kwargs):
    return json.dump(obj, fp, cls=JSONEncoder, **kwargs)


def dumps(obj, **kwargs):
    return json.dumps(obj, cls=JSONEncoder, **kwargs)


def loads(obj, **kwargs):
    return json.loads(obj, **kwargs)
