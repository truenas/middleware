# -*- coding=utf-8 -*-
from middlewared.plugins.reporting.events import RealtimeEventSource


def test_1():
    m1 = list(map(int, "9523967 12436 7063445 166462800 54456276 0 650980 0 0 0".split()))
    m2 = list(map(int, "9523988 12436 7063483 166462923 54456890 0 650982 0 0 0".split()))
    assert 7 < RealtimeEventSource.get_cpu_usages([v - m1[i] for i, v in enumerate(m2)])["usage"] < 8
