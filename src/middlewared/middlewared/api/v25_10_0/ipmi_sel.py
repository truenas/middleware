from middlewared.api.base import BaseModel


__all__ = ["IpmiSelElistEntry", "IpmiSelClearArgs", "IpmiSelClearResult", "IpmiSelInfoArgs", "IpmiSelInfoResult",]


class IpmiSelElistEntry(BaseModel):
    id: str
    date: str
    time: str
    name: str
    type: str
    event_direction: str
    event: str


class IPMISELInfo(BaseModel):
    sel_version: str
    number_of_log_entries: str
    free_space_remaining: str
    recent_erase_timestamp: str
    get_sel_allocation_information_command: str
    reserve_sel_command: str
    partial_add_sel_entry_command: str
    delete_sel_command: str
    events_dropped_due_to_lack_of_space: str
    number_of_possible_allocation_units: str
    allocation_unit_size: str
    number_of_free_allocation_units: str
    largest_free_block: str
    maximum_record_size: str


class IpmiSelClearArgs(BaseModel):
    pass


class IpmiSelClearResult(BaseModel):
    result: None


class IpmiSelInfoArgs(BaseModel):
    pass


class IpmiSelInfoResult(BaseModel):
    result: IPMISELInfo | dict
