import inspect

from middlewared.utils.type import copy_function_metadata

from .base import ServiceBase


class ServicePartBaseMeta(ServiceBase):
    def __new__(cls, name, bases, attrs):
        klass = super().__new__(cls, name, bases, attrs)

        if name == 'ServicePartBase':
            return klass

        if len(bases) == 1 and bases[0].__name__ == 'ServicePartBase':
            return klass

        for base in bases:
            if any(b.__name__ == 'ServicePartBase' for b in base.__bases__):
                break
        else:
            raise RuntimeError(f'Could not find ServicePartBase among bases of these classes: {bases!r}')

        for name, original_method in inspect.getmembers(base, predicate=inspect.isfunction):
            new_method = attrs.get(name)
            if new_method is None:
                raise RuntimeError(f'{klass!r} does not define method {name!r} that is defined in it\'s base {base!r}')

            if hasattr(original_method, 'wraps'):
                original_argspec = inspect.getfullargspec(original_method.wraps)
            else:
                original_argspec = inspect.getfullargspec(original_method)
            if original_argspec != inspect.getfullargspec(new_method):
                raise RuntimeError(f'Signature for method {name!r} does not match between {klass!r} and it\'s base '
                                   f'{base!r}')

            copy_function_metadata(original_method, new_method)

            if hasattr(original_method, 'wrap'):
                new_method = original_method.wrap(new_method)
                setattr(klass, name, new_method)

        return klass


class ServicePartBase(metaclass=ServicePartBaseMeta):
    pass
