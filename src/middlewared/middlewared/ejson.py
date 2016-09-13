import json
from datetime import datetime


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if type(obj) is datetime:
            return str(obj)
        return super(JsonEncoder, self).default(obj)


def dumps(obj, **kwargs):
    return json.dumps(obj, cls=JSONEncoder, **kwargs)
