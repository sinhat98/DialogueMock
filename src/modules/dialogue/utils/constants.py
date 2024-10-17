
from datetime import time as dt_time
from dataclasses import dataclass

INITIAL_UTTERANCE = "INITIAL_UTTERANCE"
FALLBACK = "FALLBACK"
BACK_SCENE = "BACK_SCENE"
SCENE_INITIAL = "SCENE_INITIAL"
COMPLETED = "COMPLETED"
CONVERSATION_END = "CONVERSATION_END"
BACK_PREV_SCENE = "BACK_PREV_SCENE"
CONVERSATION_CONTINUE = "CONVERSATION_CONTINUE"
SWITCH_SCENE = "SWITCH_SCENE"
UNREQUITED_SLOT = "UNREQUITED_SLOT"
USE_AS_IS = "USE_AS_IS"
FILLER = "FILLER"
APPLOGIZE = "APPLOGIZE"



# 営業時間を表すデータクラス
@dataclass
class TimeSegment:
    start: dt_time
    end: dt_time
    
BUSINESS_HOURS = [
    TimeSegment(start=dt_time(11, 0), end=dt_time(15, 0)),
    TimeSegment(start=dt_time(17, 0), end=dt_time(23, 0)),
]