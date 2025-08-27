from typing import Iterable

from middlewared.api.base import BaseModel, IPvAnyAddress, UUID


class AuditEventVersion(BaseModel):
    major: int
    minor: int


class AuditEvent(BaseModel):
    """Mirrors `middlewared.api.current.AuditQueryResultItem`."""
    event: str
    event_data: BaseModel
    audit_id: UUID
    message_timestamp: int
    timestamp: dict
    address: IPvAnyAddress
    username: str
    session: UUID
    service: str
    success: bool


def convert_schema_to_set(schema_list: Iterable[dict]) -> set[str]:
    """Generate a set of all dot-notated field names contained in the JSON schema."""

    def add_to_set(val: dict, current_name: str, skip_title: bool = False):
        if not skip_title:
            if current_name:
                current_name += '.'

            current_name += val['title']
            schema_set.add(current_name)

        if any_of := val.get('anyOf'):
            for subval in any_of:
                # The titles of objects contained in "anyOf" are model names. Don't use those.
                add_to_set(subval, current_name, skip_title=True)
        elif val['type'] == 'object':
            for subval in val.get('properties', {}).values():  # Fields with type `dict` do not have properties.
                add_to_set(subval, current_name)

    schema_set = set()
    for entry in schema_list:
        for val in entry['properties'].values():
            add_to_set(val, '')

    return schema_set
