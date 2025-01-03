from typing import Annotated

from pydantic import Field

__all__ = ["TcpPort"]

MIN_TCP_PORT = 1
MAX_TCP_PORT = 65535

TcpPort = Annotated[int, Field(ge=MIN_TCP_PORT, le=MAX_TCP_PORT)]
