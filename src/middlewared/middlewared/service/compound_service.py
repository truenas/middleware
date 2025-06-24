import itertools

from .base import service_config
from .service import Service


class CompoundService(Service):
    def __init__(self, middleware, parts):
        super().__init__(middleware)

        self._register_models = []
        for part in parts:
            self._register_models += getattr(part, '_register_models', [])

        config_specified = {}
        for part1, part2 in itertools.combinations(parts, 2):
            for key in set(part1._config_specified.keys()) & set(part2._config_specified.keys()):
                if part1._config_specified[key] != part2._config_specified[key]:
                    raise RuntimeError(f'{part1} has {key}={part1._config_specified[key]!r}, but '
                                       f'{part2} has {key}={part2._config_specified[key]!r}')
            config_specified.update(part1._config_specified)
            config_specified.update(part2._config_specified)

        self._config = service_config(parts[0].__class__, config_specified)

        self.parts = parts

        methods_parts = {}
        for part in self.parts:
            for name in dir(part):
                if name.startswith('_'):
                    continue

                meth = getattr(part, name)
                if not callable(meth):
                    continue

                if hasattr(self, name):
                    raise RuntimeError(
                        f'Duplicate method name {name} for service parts {methods_parts[name]} and {part}',
                    )

                setattr(self, name, meth)
                methods_parts[name] = part

        for part in self.parts:
            if part.__doc__:
                self.__doc__ = part.__doc__
                break

    def __repr__(self):
        return f'<CompoundService: {", ".join([repr(part) for part in self.parts])}>'
