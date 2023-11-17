from enum import Enum, unique


@unique
class ControllerModels(Enum):
    F60 = 'F60'  # all nvme flash
    F100 = 'F100'  # all nvme flash
    F130 = 'F130'  # all nvme flash
    H10 = 'H10'
    H20 = 'H20'
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
    X10 = 'X10'
    X20 = 'X20'


@unique
class JbodModels(Enum):
    ES12 = 'ES12'
    ES24 = 'ES24'
    ES24F = 'ES24F'
    ES60 = 'ES60'
    ES60G2 = 'ES60G2'
    ES102 = 'ES102'
    ES102G2 = 'ES102G2'
