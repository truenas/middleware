import pytest

from middlewared.plugins.smart import smart_test_schedules_intersect_at


DEFAULTS = {"hour": "*", "month": "*", "dom": "*", "dow": "*"}


@pytest.mark.parametrize("a,b,result", [
    ({"hour": "1"}, {"hour": "2"}, None),
    ({"hour": "*"}, {"hour": "2"}, "02:00"),
    ({"hour": "*/3"}, {"hour": "1,7,15,16,21"}, "15:00"),

    ({"dom": "1,3,5", "hour": "2"}, {"dom": "2,4,6", "hour": "2"}, None),
    ({"dom": "1,3,6", "hour": "2"}, {"dom": "2,4,6", "hour": "2"}, "Day 6th of every month, 02:00"),
    ({"dom": "1,3,6", "month": "*/2"}, {"dom": "2,4,6", "month": "1"}, None),
    ({"dom": "1,3,6", "month": "*/2"}, {"dom": "2,4,6", "month": "3,8"}, "Aug, 6th, 00:00"),
    ({"hour": "2"}, {"dow": "4", "hour": "2"}, "Thu, 02:00"),
])
def test__smart_test_schedules_intersect_at(a, b, result):
    assert smart_test_schedules_intersect_at({**DEFAULTS, **a}, {**DEFAULTS, **b}) == result
