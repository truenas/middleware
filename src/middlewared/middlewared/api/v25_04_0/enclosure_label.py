from middlewared.api.base import (
    BaseModel,
    ForUpdateMetaclass,
    NonEmptyString,
    single_argument_args
)


class EnclosureLabelEntry(BaseModel):
    id: NonEmptyString
    """The enclosure's `id` key (returned from enclosure2.query) that this label is associated to."""
    label: NonEmptyString
    """The human readable label for the enclosure."""


class EnclosureLabelUpdate(EnclosureLabelEntry, metaclass=ForUpdateMetaclass):
    pass


class EnclosureLabelUpdateArgs(BaseModel):
    data: EnclosureLabelUpdate


class EnclosureLabelUpdateResult(BaseModel):
    result: EnclosureLabelEntry


@single_argument_args("enclosure_label_delete")
class EnclosureLabelDeleteArgs(BaseModel):
    id: NonEmptyString


class EnclosureLabelDeleteResult(BaseModel):
    result: None
