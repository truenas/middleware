from datetime import datetime, time, timedelta

import json


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if type(obj) is datetime:
            # Total milliseconds since EPOCH
            return {'$date': int((obj.now() - datetime(1970, 1, 1)).total_seconds() * 1000)}
        elif type(obj) is time:
            return {'$time': str(obj)}
        return super(JSONEncoder, self).default(obj)


def object_hook(obj):
    if len(obj) == 1:
        if '$date' in obj:
            return datetime.utcfromtimestamp(obj['$date'] / 1000) + timedelta(milliseconds=obj['$date'] % 1000)
        if '$time' in obj:
            return time(*[int(i) for i in obj['$time'].split(':')])
    return obj


def dump(obj, fp, **kwargs):
    return json.dump(obj, fp, cls=JSONEncoder, **kwargs)


def dumps(obj, **kwargs):
    return json.dumps(obj, cls=JSONEncoder, **kwargs)


def loads(obj, **kwargs):
    return json.loads(obj, object_hook=object_hook, **kwargs)
