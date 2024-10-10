from enum import IntEnum

class TurnTakingStatus(IntEnum):
    END_OF_TURN = 0
    BACKCHANNEL = 1
    CONTINUE = 2
