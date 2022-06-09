from middlewared.plugins.smart_.schedule import smartd_schedule_piece


def test__smartd_schedule_piece__every_day_of_week():
    assert smartd_schedule_piece("1,2,3,4,5,6,7", 1, 7) == "."


def test__smartd_schedule_piece__every_day_of_week_wildcard():
    assert smartd_schedule_piece("*", 1, 7) == "."


def test__smartd_schedule_piece__specific_day_of_week():
    assert smartd_schedule_piece("1,2,3", 1, 7) == "(1|2|3)"


def test__smartd_schedule_piece__every_month():
    assert smartd_schedule_piece("1,2,3,4,5,6,7,8,9,10,11,12", 1, 12) == ".."


def test__smartd_schedule_piece__each_month_wildcard():
    assert smartd_schedule_piece("*", 1, 12) == ".."


def test__smartd_schedule_piece__each_month():
    assert smartd_schedule_piece("*/1", 1, 12) == ".."


def test__smartd_schedule_piece__every_fifth_month():
    assert smartd_schedule_piece("*/5", 1, 12) == "(05|10)"


def test__smartd_schedule_piece__every_specific_month():
    assert smartd_schedule_piece("1,5,11", 1, 12) == "(01|05|11)"


def test__smartd_schedule_piece__at_midnight():
    assert smartd_schedule_piece("0", 1, 23) == "(00)"


def test__smartd_schedule_piece__range_with_divisor():
    assert smartd_schedule_piece("3-30/10", 1, 31) == "(10|20|30)"


def test__smartd_schedule_piece__range_without_divisor():
    assert smartd_schedule_piece("10-15", 1, 31) == "(10|11|12|13|14|15)"


def test__smartd_schedule_piece__malformed_range_without_divisor():
    assert smartd_schedule_piece("10-1", 1, 31) == "(10)"
