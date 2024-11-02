from pathlib import Path


__all__ = ['FilePath', 'HostPath']


class HostPath(str):

    @classmethod
    def __get_validators__(cls):
        yield cls.validate_path

    @classmethod
    def validate_path(cls, value):
        path = Path(value)
        if not path.exists():
            raise ValueError(f'Path does not exist (underlying dataset may be locked or the path is just missing).')
        return str(value)


class FilePath(HostPath):

    @classmethod
    def validate_path(cls, value):
        path = Path(value)
        if not path.is_file():
            raise ValueError('This path is not a file.')
        return str(value)
