from datetime import time

def isTimeBetween(time_to_test, begin_time, end_time):
    if end_time == time(0, 0):
        return ((begin_time <= time_to_test) or (time_to_test == end_time))
    elif begin_time < end_time:
        return ((begin_time <= time_to_test) and (time_to_test <= end_time))
    else:
        return ((begin_time >= time_to_test) or (time_to_test >= end_time))
