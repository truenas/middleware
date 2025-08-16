from middlewared.api.base import BaseModel

__all__ = [
    "NVMeHostEntry",
]

class NVMeHostEntry(BaseModel):
    id: int
    hostid_a: str
    hostnqn_a: str
    hostid_b: str
    hostnqn_b: str
