from enum import Enum, unique


@unique
class ElementStatusesToIgnore(Enum):
    UNSUPPORTED = 'unsupported'


@unique
class ElementDescriptorsToIgnore(Enum):
    ADISE0 = 'arraydevicesinsubenclsr0'
    ADS = 'array device slot'
    EMPTY = '<empty>'
    AD = 'arraydevices'
    DS = 'drive slots'


@unique
class ControllerModels(Enum):
    F60 = 'F60'  # all nvme flash
    F100 = 'F100'  # all nvme flash
    F130 = 'F130'  # all nvme flash
    H10 = 'H10'
    H20 = 'H20'
    H30 = 'H30'
    M30 = 'M30'
    M40 = 'M40'
    M50 = 'M50'
    M60 = 'M60'
    MINI3E = 'MINI-3.0-E'
    MINI3EP = 'MINI-3.0-E+'
    MINI3X = 'MINI-3.0-X'
    MINI3XP = 'MINI-3.0-X+'
    MINI3XLP = 'MINI-3.0-XL+'
    MINIR = 'MINI-R'
    R10 = 'R10'
    R20 = 'R20'
    R20A = 'R20A'
    R20B = 'R20B'
    R30 = 'R30'  # all nvme flash
    R40 = 'R40'
    R50 = 'R50'
    R50B = 'R50B'
    R50BM = 'R50BM'
    R60 = 'R60'  # all nvme flash
    X10 = 'X10'
    X20 = 'X20'
    V140 = 'V140'
    V160 = 'V160'
    V260 = 'V260'
    V280 = 'V280'


@unique
class JbodModels(Enum):
    ES12 = 'ES12'
    ES24 = 'ES24'
    ES24F = 'ES24F'
    ES60 = 'ES60'
    ES60G2 = 'ES60G2'
    ES60G3 = 'ES60G3'
    ES102 = 'ES102'
    ES102G2 = 'ES102G2'


@unique
class JbofModels(Enum):
    # name is iX's model (ES24N)
    # while the value (VDS2249R2) is the OEM's model
    ES24N = 'VDS2249R2'


# See SES-4 7.2.3 Status element format, Table 74 — ELEMENT STATUS CODE field
@unique
class ElementStatus(Enum):
    UNSUPPORTED = 'Unsupported'
    OK = 'OK'
    CRITICAL = 'Critical'
    NONCRITICAL = 'Noncritical'
    UNRECOVERABLE = 'Unrecoverable'
    NOT_INSTALLED = 'Not installed'
    UNKNOWN = 'Unknown'
    NOT_AVAILABLE = 'Not available'
    NO_ACCESS_ALLOWED = 'No access allowed'


# See SES-4 7.1 Element definitions overview, Table 71 — Element type codes
@unique
class ElementType(Enum):
    UNSPECIFIED = 'Unspecified'
    DEVICE_SLOT = 'Device Slot'
    POWER_SUPPLY = 'Power Supply'
    COOLING = 'Cooling'
    TEMPERATURE_SENSORS = 'Temperature Sensors'
    DOOR_LOCK = 'Door Lock'
    AUDIBLE_ALARM = 'Audible Alarm'
    ENCLOSURE_SERVICES_CONTROLLER_ELECTRONICS = 'Enclosure Services Controller Electronics'
    SCC_CONTROLLER_ELECTRONICS = 'SCC Controller Electronics'
    NONVOLATILE_CACHE = 'Nonvolatile Cache'
    INVALID_OPERATION_REASON = 'Invalid Operation Reason'
    UNINTERRUPTIBLE_POWER_SUPPLY = 'Uninterruptible Power Supply'
    DISPLAY = 'Display'
    KEY_PAD_ENTRY = 'Key Pad Entry'
    ENCLOSURE = 'Enclosure'
    SCSI_PORT_TRANSCEIVER = 'SCSI Port/Transciever'
    LANGUAGE = 'Language'
    COMMUNICATION_PORT = 'Communication Port'
    VOLTAGE_SENSOR = 'Voltage Sensor'
    CURRENT_SENSOR = 'Current Sensor'
    SCSI_TARGET_PORT = 'SCSI Target Port'
    SCSI_INITIATOR_PORT = 'SCSI Initiator Port'
    SIMPLE_SUBENCLOSURE = 'Simple Subenclosure'
    ARRAY_DEVICE_SLOT = 'Array Device Slot'
    SAS_EXPANDER = 'SAS Expander'
    SAS_CONNECTOR = 'SAS Connector'


# See DSP0268_2023.1 4.16.3.1 Health (https://www.dmtf.org/dsp/DSP0268)
@unique
class RedfishStatusHealth(Enum):
    CRITICAL = 'Critical'
    OK = 'OK'
    WARNING = 'Warning'


# See DSP0268_2023.1 4.16.3.4 State (https://www.dmtf.org/dsp/DSP0268)
@unique
class RedfishStatusState(Enum):
    ABSENT = 'Absent'
    DEFERRING = 'Deferring'
    DISABLED = 'Disabled'
    ENABLED = 'Enabled'
    INTEST = 'InTest'
    QUALIFIED = 'Qualified'
    QUIESCED = 'Quiesced'
    STANDBY_OFFLINE = 'StandbyOffline'
    STANDBY_SPARE = 'StandbySpare'
    STARTING = 'Starting'
    UNAVAILABLE_OFFLINE = 'UnavailableOffline'
    UPDATING = 'Updating'
