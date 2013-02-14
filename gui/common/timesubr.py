from datetime import time

def isTimeBetween(time_to_test, begin_time, end_time):
    if begin_time <= end_time:
        # e.g. from 9:00 to 18:00.  This also covers e.g. 18:00 to 18:00
        # which means the event happens on exactly 18:00.
        return ((time_to_test >= begin_time) and (time_to_test <= end_time))
    else:
        # e.g. from 18:00 to 9:00
        return ((time_to_test >= begin_time) or (time_to_test <= end_time))
