import importlib.abc
import importlib.util
import sys
import types
from unittest.mock import MagicMock


class FakeModule(types.ModuleType):
    def __getattr__(self, name):
        mock = MagicMock(name=f"{self.__name__}.{name}")
        setattr(self, name, mock)
        return mock


class FakeImporter(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path, target=None):
        if fullname.startswith(("truenas_pylibzfs",)):
            return importlib.util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec):
        return FakeModule(spec.name)

    def exec_module(self, module):
        pass


def pytest_configure():
    sys.meta_path.insert(0, FakeImporter())
