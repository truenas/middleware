import enum


class XmitHashChoices(enum.Enum):
    LAYER2 = 'LAYER2'
    LAYER23 = 'LAYER2+3'
    LAYER34 = 'LAYER3+4'


class LacpduRateChoices(enum.Enum):
    SLOW = 'SLOW'
    FAST = 'FAST'
