import pytest

from middlewared.service import job, Service, ServicePartBase
from middlewared.schema import accepts, Int


class SumServiceBase(ServicePartBase):
    @accepts(Int("a"), Int("b"))
    def sum(self, a, b):
        """
        Sum two numbers
        """
        pass


def test__method_not_defined():
    with pytest.raises(RuntimeError) as e:
        class SumServiceImpl(Service, SumServiceBase):
            def add(self, a, b):
                return a + b

    assert "does not define method 'sum'" in e.value.args[0], e.value.args[0]


def test__signatures_do_not_match():
    with pytest.raises(RuntimeError) as e:
        class SumServiceImpl(Service, SumServiceBase):
            def sum(self, a, b, c=0):
                return a + b

    assert "Signature for method" in e.value.args[0], e.value.args[0]


def test__ok():
    class SumServiceImpl(Service, SumServiceBase):
        def sum(self, a, b):
            return a + b

    assert SumServiceImpl.sum.__doc__ is not None


def test__schema_works():
    class SumServiceImpl(Service, SumServiceBase):
        def sum(self, a, b):
            return a + b

    assert SumServiceImpl(None).sum(1, "2") == 3


def test__job():
    class JobServiceBase(ServicePartBase):
        @accepts(Int("arg"))
        @job()
        def process(self, job, arg):
            pass

    class JobServiceImpl(Service, JobServiceBase):
        def process(self, job, arg):
            return arg * 2

    assert JobServiceImpl(None).process(None, 3) == 6
