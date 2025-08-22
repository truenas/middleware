import itertools

from .service import service_config, Service


class CompoundService(Service, no_config=True):
    def __init__(self, middleware, parts):
        self._register_models = []
        for part in parts:
            self._register_models += getattr(part, '_register_models', [])

        config_specified = {
            'events': [],
            'event_sources': {},
        }

        for part in parts:
            for event in part._config_specified.get('events', []):
                config_specified['events'].append(event)
            for name, klass in part._config_specified.get('event_sources', {}).items():
                if name in config_specified['event_sources']:
                    raise RuntimeError(f'More than one part defines event source {name!r}')

                config_specified['event_sources'][name] = klass

        for part1, part2 in itertools.combinations(parts, 2):
            config1 = part1._config_specified.copy()
            config2 = part2._config_specified.copy()
            for k in ['events', 'event_sources']:
                config1.pop(k, None)
                config2.pop(k, None)

            for key in set(config1.keys()) & set(config2.keys()):
                if config1[key] != config2[key]:
                    raise RuntimeError(f'{part1} has {key}={config1[key]!r}, but {part2} has {key}={config2[key]!r}')

            config_specified.update(config1)
            config_specified.update(config2)

        self._config = service_config(type(parts[0]).__name__, config_specified)
        super().__init__(middleware)
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
