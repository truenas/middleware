from .event import Event
from .method import Method


class API:
    def __init__(self, version: str, methods: list[Method], events: list[Event]):
        self.version = version
        self.methods = methods
        self.events = events
