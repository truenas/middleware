import enum


class Mode(enum.Enum):
    SERVER = 'SERVER'
    PEER = 'PEER'
    LOCAL = 'LOCAL'

    @staticmethod
    def from_str(strval):
        if strval in ('SERVER', '^'):
            return Mode.SERVER
        elif strval in ('PEER', '='):
            return Mode.PEER
        elif strval in ('LOCAL', '#'):
            return Mode.LOCAL
        else:
            raise NotImplementedError(f'Invalid mode: {strval}')

    def __str__(self):
        return str(self.value)


class State(enum.Enum):
    BEST = 'BEST'
    SELECTED = 'SELECTED'
    SELECTABLE = 'SELECTABLE'
    FALSE_TICKER = 'FALSE_TICKER'
    TOO_VARIABLE = 'TOO_VARIABLE'
    NOT_SELECTABLE = 'NOT_SELECTABLE'

    @staticmethod
    def from_str(strval):
        if strval in ('BEST', '*'):
            return State.BEST
        elif strval in ('SELECTED', '+'):
            return State.SELECTED
        elif strval in ('SELECTABLE', '-'):
            return State.SELECTABLE
        elif strval in ('FALSE_TICKER', 'x'):
            return State.FALSE_TICKER
        elif strval in ('TOO_VARIABLE', '~'):
            return State.TOO_VARIABLE
        elif strval in ('NOT_SELECTABLE', '?'):
            return State.NOT_SELECTABLE
        else:
            raise NotImplementedError(f'Invalid state: {strval}')

    def is_active(self):
        return self in [State.BEST, State.SELECTED]

    @staticmethod
    def is_active_qq(val):
        if type(val) == str:
            val = State.from_str(val)
        return val in [State.BEST, State.SELECTED]

    def __str__(self):
        return str(self.value)
