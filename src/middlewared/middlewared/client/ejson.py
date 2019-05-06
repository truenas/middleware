from datetime import date, datetime, time, timedelta, timezone

import json


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if type(obj) is date:
            return {'$type': 'date', '$value': obj.isoformat()}
        elif type(obj) is datetime:
            if obj.tzinfo:
                obj += obj.utcoffset()
                obj = obj.replace(tzinfo=None)
            # Total milliseconds since EPOCH
            return {'$date': int((obj - datetime(1970, 1, 1)).total_seconds() * 1000)}
        elif type(obj) is time:
            return {'$time': str(obj)}
        return super(JSONEncoder, self).default(obj)


def object_hook(obj):
    obj_len = len(obj)
    if obj_len == 1:
        if '$date' in obj:
            return datetime.fromtimestamp(obj['$date'] / 1000, tz=timezone.utc) + timedelta(milliseconds=obj['$date'] % 1000)
        if '$time' in obj:
            return time(*[int(i) for i in obj['$time'].split(':')])
    if obj_len == 2 and '$type' in obj and '$value' in obj:
        if obj['$type'] == 'date':
            return date(*[int(i) for i in obj['$value'].split('-')])
    return obj


def dump(obj, fp, **kwargs):
    return json.dump(obj, fp, cls=JSONEncoder, **kwargs)


def dumps(obj, **kwargs):
    return json.dumps(obj, cls=JSONEncoder, **kwargs)


def loads(obj, **kwargs):
    return json.loads(obj, object_hook=object_hook, **kwargs)
