from .method import Method


class API:
    def __init__(self, version: str, methods: list[Method]):
        self.version = version
        self.methods = methods
